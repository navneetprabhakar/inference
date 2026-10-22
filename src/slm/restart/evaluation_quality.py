"""Atomic verified evaluation evidence and persistent quality-monitor history.

Use this barrier in the candidate path. Base EvaluationBarrier tests sequencing
only. Verifiers here must return freshly recomputed metric dictionaries, not bool.
"""
import copy
import hashlib
from pathlib import Path
import json
from .evaluation_barrier import EvaluationBarrier,EvaluationPending
from .monitor import Monitor,StopRun
from .numerical_monitor_comparison import exact

FIELDS=('dev','diagnostics','dev_streak','grammar_streak','grounded_streak')


def projection(monitor):
    # JSON is the checkpoint representation (diagnostic tuples become lists).
    return json.loads(json.dumps({key:getattr(monitor,key) for key in FIELDS},allow_nan=False))


class EvaluationQualityBarrier(EvaluationBarrier):
    def __init__(self,path,*,identity,schedule):
        super().__init__(path,identity=identity,schedule=schedule)
        self.db.execute('CREATE TABLE IF NOT EXISTS clean_stop (id INTEGER PRIMARY KEY CHECK(id=1),receipt TEXT NOT NULL,copy_raw BLOB,copy_pin TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS quality (id INTEGER PRIMARY KEY CHECK(id=1),state TEXT NOT NULL)')
        if self.db.execute('SELECT 1 FROM quality').fetchone() is None:
            if self.db.execute('SELECT count(*) FROM evidence').fetchone()[0] or self.position()!=0:
                self.close();raise ValueError('Cannot invent quality history for existing progress')
            self.db.execute('INSERT INTO quality VALUES (1,?)',(json.dumps(projection(Monitor()),sort_keys=True),))

    def evaluation_state(self):
        self.position()  # Terminal failures cannot be recovered by overlay.
        row=self.db.execute('SELECT state FROM quality WHERE id=1').fetchone()
        if row is None:raise ValueError('Missing durable quality state')
        state=json.loads(row[0])
        if set(state)!=set(FIELDS):raise ValueError('Changed quality state fields')
        return state

    def require_monitor(self,monitor):
        monitor.alive()
        if not exact(projection(monitor),self.evaluation_state()):
            raise EvaluationPending('Checkpoint/live evaluation history differs from durable history')

    def overlay(self,monitor):
        """Recover committed evaluation history, retaining charged-update history.

        Caller must validate checkpoint/update cursor first. This does not rewind
        barrier position or forgive a terminal failure.
        """
        monitor.alive();result=copy.deepcopy(monitor)
        for key,value in self.evaluation_state().items():setattr(result,key,value)
        return result

    def accept(self,event,path,*,checkpoint_sha256,verify):
        def verified_transition(raw,context):
            metrics=verify(raw,context)
            if not isinstance(metrics,dict):raise ValueError('Recomputed quality metrics required')
            m=Monitor()
            for key,value in self.evaluation_state().items():setattr(m,key,value)
            if event=='dev_loss_checkpoint':
                if set(metrics)!={'nll'}:raise ValueError('Development metric inventory mismatch')
                try:m.development(nll=metrics['nll'],after_pilot=context['targets']>2000000)
                except StopRun:
                    if m.terminal!='development plateau':raise
                    # Commit the triggering evidence and stop atomically. Never
                    # clear terminal state to permit diagnostics or another update.
                    receipt={'reason':m.terminal,'context':context,'evidence_sha256':hashlib.sha256(raw).hexdigest()}
                    self.db.execute('INSERT INTO clean_stop VALUES (1,?,NULL,NULL)',(json.dumps(receipt,sort_keys=True),))
                    self.db.execute('UPDATE barrier SET terminal=? WHERE id=1',(m.terminal,))
            elif event=='full_development_diagnostics':
                expected={'train_nll','dev_nll','grammar','grounded','degenerate_outputs'}
                if set(metrics)!=expected:raise ValueError('Diagnostic metric inventory mismatch')
                if not m.dev or metrics['dev_nll']!=m.dev[-1]:raise ValueError('Diagnostic loss differs from latest dev check')
                # At 2M multiples, loss must already be accepted at this boundary.
                if not self.db.execute("SELECT 1 FROM evidence WHERE step=? AND event='dev_loss_checkpoint'",(context['step'],)).fetchone():
                    raise ValueError('Current development loss must precede diagnostics')
                m.diagnostic(**metrics)
            elif event=='copying_probes':
                if set(metrics)!={'train_copies','heldout_copies'}:raise ValueError('Copy metric inventory mismatch')
                m.copying(**metrics)
            else:raise ValueError('Unknown quality event')
            self.db.execute('UPDATE quality SET state=? WHERE id=1',(json.dumps(projection(m),sort_keys=True),))
            return True
        # The quality write and raw evidence INSERT share this single transaction.
        super().accept(event,path,checkpoint_sha256=checkpoint_sha256,verify=verified_transition)
        if self.clean_stop() is not None:raise StopRun('development plateau')

    def clean_stop(self):
        row=self.db.execute('SELECT receipt FROM clean_stop WHERE id=1').fetchone()
        if row is None:return None
        receipt=json.loads(row[0]);step,terminal=self.db.execute('SELECT step,terminal FROM barrier WHERE id=1').fetchone()
        if terminal not in ('development plateau','work budget exhausted') or receipt['reason']!=terminal or receipt['context']['step']!=step:
            raise ValueError('Invalid clean-stop state')
        context=receipt['context']
        targets=0 if step==0 else self.schedule.updates[step-1].cumulative_targets
        if context['identity']!=self.identity or context['schedule_sha256']!=self.schedule.sha256 or context['targets']!=targets:
            raise ValueError('Unbound clean-stop context')
        if terminal=='work budget exhausted':
            if context['event']!='work_budget_end':raise ValueError('Invalid work-budget stop event')
            return receipt
        evidence=self.db.execute("SELECT raw,sha256 FROM evidence WHERE step=? AND event='dev_loss_checkpoint'",(step,)).fetchone()
        if (evidence is None or hashlib.sha256(evidence[0]).hexdigest()!=evidence[1]
                or receipt['evidence_sha256']!=evidence[1] or json.loads(evidence[0])['context']!=receipt['context']):
            raise ValueError('Changed clean-stop evidence')
        return receipt

    def stop_work_budget(self,ledger,proof,*,checkpoint_sha256):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            step=self.position()
            if self.pending() or step>=len(self.schedule.updates):raise ValueError('Not an unevaluated next-update refusal')
            ledger.verify_exhaustion(proof)
            update=self.schedule.updates[step]
            if proof['spans']!=[list(span) for micro in update.microbatches for span in micro]:
                raise ValueError('Refusal differs from next scheduled update')
            if len(checkpoint_sha256)!=64 or any(x not in '0123456789abcdef' for x in checkpoint_sha256):raise ValueError('Invalid stop checkpoint pin')
            context=dict(identity=self.identity,schedule_sha256=self.schedule.sha256,step=step,
                targets=0 if step==0 else self.schedule.updates[step-1].cumulative_targets,
                checkpoint_sha256=checkpoint_sha256,event='work_budget_end')
            receipt={'reason':'work budget exhausted','context':context,'exhaustion':proof}
            self.db.execute('INSERT INTO clean_stop VALUES(1,?,NULL,NULL)',(json.dumps(receipt,sort_keys=True),))
            self.db.execute("UPDATE barrier SET terminal='work budget exhausted' WHERE id=1")
            self.db.execute('COMMIT');return receipt
        except BaseException:
            self.db.execute('ROLLBACK');raise

    def accept_terminal_copy(self,path,*,verify):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            stop=self.clean_stop()
            if stop is None:raise ValueError('Verified clean stop required')
            if self.db.execute('SELECT copy_pin FROM clean_stop WHERE id=1').fetchone()[0] is not None:
                raise ValueError('Termination copying already recorded')
            raw=Path(path).read_bytes();context=dict(stop['context'],event='copying_probes')
            if not exact(json.loads(raw).get('context'),context):raise ValueError('Unbound termination copying')
            metrics=verify(raw,context)
            if not isinstance(metrics,dict) or set(metrics)!={'train_copies','heldout_copies'}:raise ValueError('Invalid copying metrics')
            # A fresh pure copying check does not replace or revive the stopped
            # training monitor; failure permanently invalidates clean termination.
            Monitor().copying(**metrics)
            self.db.execute('UPDATE clean_stop SET copy_raw=?,copy_pin=? WHERE id=1',(raw,hashlib.sha256(raw).hexdigest()))
            self.db.execute('COMMIT')
        except BaseException as error:
            self.db.execute('ROLLBACK')
            self.db.execute('UPDATE barrier SET terminal=? WHERE id=1',('Termination copying failed: '+str(error),))
            raise
