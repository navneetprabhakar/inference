"""Finite continuation campaigns; original base controller remains frozen.

SHA-256 receipts detect accidental corruption and pin local checkpoint lineage.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import uuid
import time

import checkpoint
from guards import Guard, ResourceStop


class CampaignStop(ResourceStop):
    def __init__(self, state, reason):
        super().__init__(reason)
        self.state = state


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _write(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('wb') as stream:
        stream.write(_canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    checkpoint.sync_dir(path.parent)


class LanguageCampaign:
    TERMINAL = {'completed','diverged','failed','budget-exhausted'}
    PAUSED = {'paused-resource','paused-lease','paused-milestone','interrupted'}
    def __init__(self, path, identity, *, training_goal, token_limit, evaluation_limit,
                 active_seconds, calendar_seconds, lease_seconds, resume=False, guard_factory=Guard):
        for name, value in [('active_seconds',active_seconds),('calendar_seconds',calendar_seconds),('lease_seconds',lease_seconds)]:
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value <= 0:
                raise ValueError('finite positive '+name+' required')
        if lease_seconds > 4*3600 or lease_seconds > active_seconds or active_seconds > calendar_seconds:
            raise ValueError('bounded four-hour leases within active/calendar caps required')
        for name,value in [('training_goal',training_goal),('token_limit',token_limit),('evaluation_limit',evaluation_limit)]:
            if type(value) is not int or value <= 0:raise ValueError('explicit positive '+name+' required')
        if training_goal > token_limit or training_goal % 8192 or token_limit % 8192:
            raise ValueError('whole-update committed goal and attempted ceiling required')
        required = {'seed', 'model', 'tokenizer', 'corpus', 'scheduler'}
        initialization = identity.get('initialization')
        own_parent = (isinstance(initialization, dict) and initialization.get('mode') == 'own_pretraining'
                      and {'path', 'sha256', 'random_lineage_root'} <= initialization.keys())
        if not required <= identity.keys() or not (initialization == 'random' or own_parent):
            raise ValueError('identity must pin own initialization, seed, model, tokenizer, corpus and scheduler')
        self.path = Path(path)
        self.identity = json.loads(_canonical(identity))
        self.spec = dict(schema=1, identity=self.identity, token_limit=token_limit,
                         active_seconds=active_seconds, calendar_seconds=calendar_seconds,
                         lease_seconds=lease_seconds,training_goal=training_goal,evaluation_limit=evaluation_limit)
        self.guard = guard_factory(self.path, calendar_seconds, resume=resume)
        self.closed = False
        self.pending = 0
        self.needs_load = resume
        try:
            self.spec_sha256 = hashlib.sha256(_canonical(self.spec)).hexdigest()
            if resume:
                frozen = json.loads((self.path/'campaign-spec.json').read_bytes())
                if frozen != self.spec:
                    raise ValueError('immutable campaign specification changed')
                self.ledger = json.loads((self.path/'campaign.json').read_bytes())
                signature = self.ledger.pop('sha256')
                if signature != self._sign(self.ledger):
                    raise ValueError('campaign ledger checksum failed')
                if self.ledger['spec'] != self.spec:
                    raise ValueError('campaign identity or original budgets changed')
                if self.ledger['state'] in self.TERMINAL:
                    raise ValueError('terminal campaign cannot resume')
                if self.ledger['state'] == 'running':
                    # A dead worker may have used its entire remaining lease.
                    # Charge this bounded exposure, never the subsequent downtime.
                    self.ledger['active_seconds'] = self.ledger['lease_active_base'] + self.ledger['lease_allowance']
                elif self.ledger['state'] not in self.PAUSED:
                    raise ValueError('invalid campaign state')
            else:
                with (self.path/'campaign-spec.json').open('xb') as stream:
                    stream.write(_canonical(self.spec)); stream.flush(); os.fsync(stream.fileno())
                self.ledger = dict(spec=self.spec, campaign_id=uuid.uuid4().hex,
                                   started=time.time(), active_seconds=0., reserved_tokens=0,
                                   step=0, trained_tokens=0, reserved_evaluation_targets=0, checkpoints=[], state='running')
            if type(self.ledger.get('reserved_evaluation_targets')) is not int or not 0 <= self.ledger['reserved_evaluation_targets'] <= evaluation_limit:
                raise ValueError('invalid durable evaluation accounting')
            self.started = time.monotonic()
            self.active_base = self.ledger['active_seconds']
            self.allowance = min(lease_seconds, active_seconds-self.active_base)
            if self.allowance <= 0:
                raise CampaignStop('paused-resource', 'cumulative active budget exhausted')
            self.ledger.update(state='running', reason='', lease_active_base=self.active_base,
                               lease_allowance=self.allowance, lease_started=time.time())
            self._publish()
            self.check()
        except BaseException:
            self.guard.close()
            self.closed = True
            raise

    def _sign(self, value):
        return hashlib.sha256(_canonical(value)).hexdigest()

    def _publish(self):
        record = dict(self.ledger)
        record['sha256'] = self._sign(record)
        _write(self.path/'campaign.json', record)

    def snapshot(self):
        active = (self.active_base + max(0., time.monotonic()-self.started)
                  if self.ledger['state'] == 'running' else self.ledger['active_seconds'])
        return dict(state=self.ledger['state'], step=self.ledger['step'],
                    trained_tokens=self.ledger['trained_tokens'],
                    reserved_tokens=self.ledger['reserved_tokens'], active_seconds=active,
                    remaining_tokens=self.spec['token_limit']-self.ledger['reserved_tokens'],
                    remaining_active_seconds=max(0., self.spec['active_seconds']-active),
                    remaining_lease_seconds=max(0., self.allowance-(active-self.active_base)))

    def check(self):
        if self.closed or self.ledger['state'] != 'running':
            raise RuntimeError('campaign is not running')
        try:
            self.guard.check()
        except ResourceStop as error:
            raise CampaignStop('paused-resource', str(error)) from error
        age = time.monotonic()-self.started
        if time.time()-self.ledger['started'] >= self.spec['calendar_seconds']:
            raise CampaignStop('paused-resource', 'calendar budget exhausted')
        if self.active_base+age >= self.spec['active_seconds']:
            raise CampaignStop('paused-resource', 'cumulative active budget exhausted')
        if age >= self.allowance:
            raise CampaignStop('paused-lease', 'lease exhausted')

    def reserve(self, target_tokens):
        self.check()
        if self.needs_load:
            raise ValueError("resume must load its verified optimizer checkpoint before work")
        if self.pending or type(target_tokens) is not int or target_tokens <= 0:
            raise ValueError('reserve exactly one positive update before work')
        if self.ledger['reserved_tokens']+target_tokens > self.spec['token_limit']:
            raise CampaignStop('paused-resource', 'target token ceiling exhausted')
        self.ledger['reserved_tokens'] += target_tokens
        self.pending = target_tokens
        self._publish()

    def reserve_evaluation(self, targets):
        self.check()
        if self.needs_load or self.pending or type(targets) is not int or targets <= 0:
            raise ValueError('evaluation requires verified optimizer boundary and positive targets')
        if self.ledger['reserved_evaluation_targets'] + targets > self.spec['evaluation_limit']:
            raise CampaignStop('budget-exhausted','evaluation attempt ceiling exhausted')
        self.ledger['reserved_evaluation_targets'] += targets
        self._publish()

    def commit(self, step, trained_tokens):
        if self.closed or self.ledger['state'] != 'running':
            raise RuntimeError('campaign is not running')
        if not self.pending or step != self.ledger['step']+1 or trained_tokens != self.ledger['trained_tokens']+self.pending:
            raise ValueError('optimizer commit differs from reserved update')
        self.ledger.update(step=step, trained_tokens=trained_tokens)
        self.pending = 0
        self._publish()

    def save(self, state):
        if self.pending:
            raise ValueError('checkpoint requires optimizer boundary')
        if state.get('step') != self.ledger['step']:
            raise ValueError('checkpoint step differs from committed step')
        payload = dict(state, identity=self.identity,
                       campaign_id=self.ledger['campaign_id'], spec_sha256=self.spec_sha256,
                       trained_tokens=self.ledger['trained_tokens'])
        checkpoint.save(self.path, payload)
        entry = json.loads((self.path/'latest.json').read_bytes())[0]
        self.ledger['checkpoints'] = [entry] + self.ledger['checkpoints'][:1]
        self._publish()

    def load(self):
        if not self.ledger['checkpoints']:
            raise ValueError('no verified own checkpoint exists')
        # The last SHA-pinned receipt can precede an interrupted checkpoint publication.
        entry = self.ledger['checkpoints'][0]
        latest = json.loads((self.path/'latest.json').read_bytes())
        if entry == latest[0]:
            payload = checkpoint.load(self.path, self.identity)
        else:
            import torch
            file = self.path/entry['file']
            if file.stat().st_size != entry['bytes'] or checkpoint.checksum(file) != entry['sha256']:
                raise ValueError('SHA-pinned checkpoint bytes changed')
            payload = torch.load(file, map_location='cpu', weights_only=True, mmap=True)
        if (payload['identity'] != self.identity or payload['campaign_id'] != self.ledger['campaign_id']
                or payload['spec_sha256'] != self.spec_sha256):
            raise ValueError('checkpoint is outside this random-initialized campaign')
        if payload['trained_tokens'] > self.ledger['reserved_tokens']:
            raise ValueError('checkpoint exceeds consumed budget')
        if entry != latest[0]:
            # Preserve the unreceipted file, but restore the accepted pointer so
            # an immediate checkpoint of the resumed optimizer is legal.
            with checkpoint._lock(self.path, True):
                checkpoint._atomic_json(self.path/'latest.json', [entry])
        self.ledger.update(step=payload['step'], trained_tokens=payload['trained_tokens'])
        self.needs_load = False
        self._publish()
        return payload

    def finish(self, state, reason=''):
        if state not in self.TERMINAL | self.PAUSED:
            raise ValueError('invalid final state')
        if state == 'completed' and (self.pending or self.ledger['trained_tokens'] != self.spec['training_goal']):
            raise ValueError('completion requires exact committed goal and optimizer boundary')
        self.ledger.update(state=state, reason=reason,
                           active_seconds=self.snapshot()['active_seconds'])
        self._publish()

    def close(self):
        if not self.closed:
            if self.ledger['state'] == 'running':
                self.finish('interrupted', 'worker closed without explicit completion')
            self.guard.close()
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        try:
            if self.ledger['state'] == 'running' and error is not None:
                state = error.state if isinstance(error, CampaignStop) else 'interrupted' if isinstance(error, KeyboardInterrupt) else 'failed'
                self.finish(state, str(error))
        finally:
            self.close()
