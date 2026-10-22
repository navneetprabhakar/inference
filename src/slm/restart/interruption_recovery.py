"""One bounded recovery from a positively identified host reboot.

Unknown process exits/SIGKILL are not evidence of an OS interruption. No terminal
quality/resource/user/budget stop is cleared. This does not launch any worker.
"""
import json
import platform
import re
import sqlite3
import subprocess
import time
from pathlib import Path
from . import checkpoint_binding,state


def boot_identity():
    result=subprocess.run(['/usr/sbin/sysctl','-n','kern.boottime'],check=True,capture_output=True,text=True,timeout=5)
    match=re.fullmatch(r'\{ sec = (\d+), usec = (\d+) \}.*\n?',result.stdout)
    if not match:raise ValueError('Unavailable boot identity')
    return {'host':platform.node(),'boot_seconds':int(match[1]),'boot_microseconds':int(match[2])}


def register(barrier,*,boot_reader=boot_identity):
    """Before the original candidate worker starts; no replacement allowed."""
    if barrier.position()!=0:raise ValueError('Recovery registration must precede updates')
    boot=boot_reader()
    barrier.db.execute('CREATE TABLE IF NOT EXISTS interruption (id INTEGER PRIMARY KEY CHECK(id=1),original_boot TEXT NOT NULL,recovery TEXT)')
    barrier.db.execute('INSERT INTO interruption VALUES (1,?,NULL)',(json.dumps(boot,sort_keys=True),))


def recover(barrier,*,checkpoint,checkpoint_root,manifest_sha256,shapes,schedule,ledger,identity,expected,time_budget,
            boot_reader=boot_identity,now=None):
    """Consume recovery and rewind only schedule position; never refund ledgers.

    A complete checkpoint is mandatory. Accepted evaluations beyond its step
    would make replay ambiguous and are refused. Evaluations at the same saved
    step remain committed and overlay onto restored monitor state.
    """
    now=time.time() if now is None else now
    barrier.db.execute('BEGIN IMMEDIATE')
    try:
        current_step=barrier.position()
        row=barrier.db.execute('SELECT original_boot,recovery FROM interruption WHERE id=1').fetchone()
        if row is None or row[1] is not None:raise ValueError('Missing or already consumed interruption recovery')
        before=json.loads(row[0]);after=boot_reader()
        if (set(before)!= {'host','boot_seconds','boot_microseconds'} or set(after)!=set(before)
                or not before['host'] or before['host']!=after['host']
                or any(type(b[k]) is not int or b[k]<0 for b in (before,after) for k in ('boot_seconds','boot_microseconds'))
                or (after['boot_seconds'],after['boot_microseconds'])<=(before['boot_seconds'],before['boot_microseconds'])
                or after['boot_seconds']>now):
            raise ValueError('No verified host reboot; unknown exits cannot resume')
        if (time_budget.terminal() is not None or not 0<time_budget.charged()<time_budget.cap
                or not 0<now<time_budget.deadline):raise ValueError('Terminal or exhausted time budget')
        path=Path(checkpoint).absolute();root=Path(checkpoint_root).absolute()
        if root.resolve(strict=True)!=root or path.resolve(strict=True)!=path or path.parent!=root:
            raise ValueError('Unowned recovery checkpoint')
        if state.digest(path/'manifest.json')!=manifest_sha256:raise ValueError('Changed recovery checkpoint pin')
        restored=checkpoint_binding.restore(path,shapes=shapes,schedule=schedule,ledger=ledger,identity=identity,expected=expected)
        step=restored['metadata']['step']
        if step>current_step:raise ValueError('Checkpoint ahead of durable update position')
        if barrier.db.execute('SELECT 1 FROM evidence WHERE step>?',(step,)).fetchone():
            raise ValueError('Cannot rewind past accepted evaluation')
        # Overlay evaluation state, but retain checkpoint update/gradient histories.
        restored['monitor']=barrier.overlay(restored['monitor'])
        receipt={'reason':'verified_host_reboot','original_boot':before,'new_boot':after,
                 'checkpoint_sha256':manifest_sha256,'from_step':current_step,'restored_step':step,
                 'work_after_checkpoint':restored['charged_work_after_checkpoint'],
                 'active_seconds_retained':time_budget.charged(),'deadline_retained':time_budget.deadline,
                 'refunds':0,'remaining_automatic_resumes':0,
                 'checkpoint_ledger_sequence':restored['metadata']['ledger_snapshot']['last_sequence'],
                 'ledger_at_recovery':ledger.snapshot(),
                 'abandoned_reservations':[list(row) for row in ledger.db.execute(
                     'SELECT rowid,id,targets,completed FROM reservations WHERE rowid>? ORDER BY rowid',
                     (restored['metadata']['ledger_snapshot']['last_sequence'],))]}
        barrier.db.execute('UPDATE interruption SET recovery=? WHERE id=1',(json.dumps(receipt,sort_keys=True),))
        barrier.db.execute('UPDATE barrier SET step=? WHERE id=1',(step,))
        barrier.db.execute('COMMIT')
        return restored,receipt
    except BaseException as error:
        barrier.db.execute('ROLLBACK')
        barrier.db.execute('UPDATE barrier SET terminal=coalesce(terminal,?) WHERE id=1',(str(error),))
        raise


def validate_abandoned_work(ledger,quality,*,checkpoint_step):
    """Accept only unchanged unfinished reservations covered by consumed recovery.

    This neither completes nor refunds historical work. New unfinished work is
    always rejected, even when an earlier recovery exists.
    """
    if quality is None:raise ValueError('Current quality cursor required for recovered evaluation')
    stop=quality.clean_stop() if hasattr(quality,'clean_stop') else None
    position=stop['context']['step'] if stop is not None else quality.position()
    if position!=checkpoint_step:raise ValueError('Current quality cursor required for recovered evaluation')
    contract=json.loads(ledger.db.execute("SELECT value FROM contract WHERE key='run'").fetchone()[0])
    if quality.identity!=contract['identity']:raise ValueError('Recovery/ledger identity mismatch')
    try:row=quality.db.execute('SELECT recovery FROM interruption WHERE id=1').fetchone()
    except sqlite3.OperationalError as error:raise ValueError('Missing recovery evidence') from error
    if row is None or row[0] is None:raise ValueError('Missing consumed recovery evidence')
    receipt=json.loads(row[0])
    if (receipt.get('reason')!='verified_host_reboot' or receipt.get('refunds')!=0
            or receipt.get('remaining_automatic_resumes')!=0):raise ValueError('Invalid recovery accounting')
    prefix=receipt['ledger_at_recovery'];ledger.verify_snapshot(prefix)
    expected=[list(r) for r in ledger.db.execute(
        'SELECT rowid,id,targets,completed FROM reservations WHERE rowid>? AND rowid<=? ORDER BY rowid',
        (receipt['checkpoint_ledger_sequence'],prefix['last_sequence']))]
    if expected!=receipt['abandoned_reservations']:raise ValueError('Changed abandoned reservation inventory')
    allowed={r[1] for r in expected if r[3]==0}
    unfinished={r[0] for r in ledger.db.execute('SELECT id FROM reservations WHERE completed=0')}
    if not unfinished<=allowed:raise ValueError('New or unaccounted unfinished work')
    return {'historical_unfinished_reservations':len(unfinished),'refunds':0}
