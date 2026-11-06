"""Atomic multidimensional budgets for a prospective own-base SFT campaign.

No default SFT budget or launch authorization. Frozen Campaign remains unchanged.
"""
from copy import deepcopy
from base_run_control import Campaign, CampaignStop

WORK=('assistant_targets','input_tokens','padded_tokens','attention_cells','evaluation_targets')


def valid_work(value):
    if set(value)!=set(WORK) or any(type(n)!=int or n<0 for n in value.values()):
        raise ValueError('complete nonnegative integer work vector required')
    if value['input_tokens']>value['padded_tokens'] or value['padded_tokens']>value['attention_cells']:
        raise ValueError('invalid compute accounting')


class SFTCampaign(Campaign):
    def __init__(self,path,identity,*,limits,active_seconds,calendar_seconds,lease_seconds,resume=False,guard_factory=None):
        valid_work(limits)
        if any(n<=0 for n in limits.values()):raise ValueError('all work ceilings must be explicit and positive')
        if identity.get('work_limits')!=limits:raise ValueError('work limits must be immutable identity')
        kwargs={} if guard_factory is None else dict(guard_factory=guard_factory)
        super().__init__(path,identity,token_limit=limits['assistant_targets'],active_seconds=active_seconds,
                         calendar_seconds=calendar_seconds,lease_seconds=lease_seconds,resume=resume,**kwargs)
        self.limits=deepcopy(limits);self.pending_work=None
        self.source_limits=deepcopy(identity.get('source_work_limits',{}))
        for value in self.source_limits.values():valid_work(value)
        try:
            if 'reserved_work' not in self.ledger:
                if self.ledger['reserved_tokens'] or self.ledger['trained_tokens']:raise ValueError('missing historical compute accounting')
                self.ledger['reserved_work']={k:0 for k in WORK};self.ledger['committed_work']={k:0 for k in WORK}
                self.ledger['reserved_by_source']={name:{k:0 for k in WORK} for name in self.source_limits}
            valid_work(self.ledger['reserved_work']);valid_work(self.ledger['committed_work'])
            if self.ledger['reserved_work']['assistant_targets']!=self.ledger['reserved_tokens']:raise ValueError('target/accounting mismatch')
            if any(self.ledger['reserved_work'][k]>limits[k] for k in WORK):raise ValueError('original work ceiling exceeded')
            if set(self.ledger.get('reserved_by_source',{}))!=set(self.source_limits):raise ValueError('source accounting inventory mismatch')
            for name,values in self.ledger.get('reserved_by_source',{}).items():
                valid_work(values)
                if any(values[k]>self.source_limits[name][k] for k in WORK):raise ValueError('source ceiling exceeded')
            if self.source_limits and any(sum(v[k] for v in self.ledger['reserved_by_source'].values())!=self.ledger['reserved_work'][k] for k in WORK):raise ValueError('source/global accounting differs')
            self._publish()
        except BaseException:
            self.close();raise

    def _charge(self,work,source):
        self.check();valid_work(work)
        if self.needs_load or self.pending:raise ValueError('verified boundary required before reservation')
        if any(self.ledger['reserved_work'][k]+work[k]>self.limits[k] for k in WORK):
            raise CampaignStop('paused-resource','SFT cumulative work ceiling exhausted')
        if self.source_limits:
            if source not in self.source_limits:raise ValueError('explicit known source required')
            if any(self.ledger['reserved_by_source'][source][k]+work[k]>self.source_limits[source][k] for k in WORK):
                raise CampaignStop('paused-resource','source work ceiling exhausted')
            for k in WORK:self.ledger['reserved_by_source'][source][k]+=work[k]
        # One signed atomic publication charges every dimension before computation.
        for k in WORK:self.ledger['reserved_work'][k]+=work[k]
        self.ledger['reserved_tokens']=self.ledger['reserved_work']['assistant_targets']

    def reserve_work(self,work,source=None):
        if work['assistant_targets']<=0 or work['evaluation_targets']:raise ValueError('training reservation requires only supervised training targets')
        self._charge(work,source);self.pending=work['assistant_targets'];self.pending_work=deepcopy(work);self._publish()

    def reserve_evaluation(self,work,source=None):
        if work['assistant_targets'] or work['evaluation_targets']<=0:raise ValueError('invalid evaluation reservation')
        self._charge(work,source);self._publish()

    def commit_work(self,step):
        if self.closed or self.ledger['state']!='running' or not self.pending_work or step!=self.ledger['step']+1:
            raise ValueError('invalid optimizer commit')
        for k in WORK:self.ledger['committed_work'][k]+=self.pending_work[k]
        self.ledger.update(step=step,trained_tokens=self.ledger['committed_work']['assistant_targets'])
        self.pending=0;self.pending_work=None;self._publish()

    def save(self,state):
        if 'committed_work' in state:raise ValueError('campaign owns committed counters')
        super().save(dict(state,committed_work=deepcopy(self.ledger['committed_work'])))

    def load(self):
        payload=super().load();work=payload['committed_work'];valid_work(work)
        if work['assistant_targets']!=payload['trained_tokens'] or work['evaluation_targets']:
            raise ValueError('checkpoint committed accounting mismatch')
        if any(work[k]>self.ledger['reserved_work'][k] for k in WORK):raise ValueError('checkpoint exceeds reserved work')
        # Only committed progress rolls back. Attempted compute remains charged.
        self.ledger['committed_work']=deepcopy(work);self._publish();return payload

    def reserve(self,*args):raise ValueError('use atomic reserve_work')
    def commit(self,*args):raise ValueError('use atomic commit_work')
