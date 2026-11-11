"""Whole-campaign affordability gate plus bounded, single-GPU lease reservations."""
from pathlib import Path
import fcntl,json,math
from cloud_training.runtime import atomic_json

CAP_USD=100.0
A100_FLEX_ENVELOPE_USD_PER_HOUR=2.5  # $2 listed VM + 25% provision; verify price before every launch.
FINISH_RESERVE_USD=10.0

def forecast(*,remaining_tokens,tokens_per_second,overhead_fraction,setup_hours=0):
    values=(remaining_tokens,tokens_per_second,overhead_fraction,setup_hours)
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in values):raise ValueError('Finite numeric forecast required')
    if remaining_tokens<0 or tokens_per_second<=0 or not 0<=overhead_fraction<=1 or setup_hours<0:raise ValueError('Invalid forecast')
    hours=remaining_tokens/tokens_per_second/3600*(1+overhead_fraction)+setup_hours
    return {'remaining_hours':hours,'remaining_compute_envelope_usd':hours*A100_FLEX_ENVELOPE_USD_PER_HOUR,'rate_envelope_usd_per_hour':A100_FLEX_ENVELOPE_USD_PER_HOUR,'not_an_invoice':True}

def reserve(path,allocation_id,*,hours,projection,price_receipt,admission_receipt):
    if not isinstance(hours,(int,float)) or isinstance(hours,bool) or not math.isfinite(hours) or not 0<hours<=12:raise ValueError('Lease must be positive and <=12h')
    if not price_receipt or not admission_receipt:raise ValueError('Price and admission receipts required')
    cost=hours*A100_FLEX_ENVELOPE_USD_PER_HOUR
    if not isinstance(projection,dict) or not math.isfinite(projection.get('remaining_compute_envelope_usd',float('nan'))) or projection['remaining_compute_envelope_usd']<cost:raise ValueError('Whole campaign forecast must cover the lease')
    p=Path(path)
    with p.with_suffix('.lock').open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX);v=json.loads(p.read_text())
        if v['cap_usd']!=CAP_USD:raise ValueError('Unexpected approved cap')
        if any(a['state'].startswith(('reserved','running','queued')) for a in v['allocations']):raise ValueError('Outstanding GPU lease/request')
        if any(a['id']==allocation_id for a in v['allocations']):raise ValueError('Allocation already exists')
        spent=sum(a['reserved_usd'] for a in v['allocations'])
        protected=v['ancillary_reserve_usd']+FINISH_RESERVE_USD
        if spent+protected+projection['remaining_compute_envelope_usd']>CAP_USD:raise ValueError('Remaining campaign plus protected finish exceeds approved100USD')
        v['allocations'].append({'id':allocation_id,'hours':hours,'reserved_usd':cost,'state':'reserved_before_provisioning','purpose':'admitted_base_training','forecast':projection,'price_receipt':str(price_receipt),'admission_receipt':str(admission_receipt)})
        v['total_including_ancillary_reserve_usd']=spent+cost+v['ancillary_reserve_usd']
        v['remaining_unallocated_usd']=CAP_USD-v['total_including_ancillary_reserve_usd']
        atomic_json(p,v)
        return v


def retained_cost(ledger, *, hours, finish_hours):
    """Hard lifetime envelope. Finish is protected *inside* the same allocation.

    This is a spend limit, not a promise that10B tokens or quality gates fit.
    The controller must stop base work before the protected finish window.
    """
    for value in (hours, finish_hours):
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('Finite retained lifetime and finish window required')
    if not 0 < finish_hours < hours <=32 or finish_hours*A100_FLEX_ENVELOPE_USD_PER_HOUR<FINISH_RESERVE_USD:
        raise ValueError('Retained lifetime <=32h must include at least10USD for finishing')
    if ledger.get('cap_usd')!=CAP_USD:raise ValueError('Unexpected approved cap')
    amounts=[ledger.get('ancillary_reserve_usd'),*[a['reserved_usd'] for a in ledger['allocations']]]
    if any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<0 for x in amounts):
        raise ValueError('Invalid financial ledger')
    if any(a['state'].startswith(('reserved','running','queued')) for a in ledger['allocations']):
        raise ValueError('Outstanding GPU lease/request')
    total=sum(amounts)+hours*A100_FLEX_ENVELOPE_USD_PER_HOUR
    if total>CAP_USD:raise ValueError('Retained lifetime exceeds approved100USD')
    return {'lifetime_hours':hours,'finish_hours_within_lifetime':finish_hours,
            'base_and_setup_hours_max':hours-finish_hours,
            'reserved_compute_usd':hours*A100_FLEX_ENVELOPE_USD_PER_HOUR,
            'total_envelope_usd':round(total,6),'not_an_invoice':True}


def reserve_retained(path, allocation_id, *, hours, finish_hours, price_receipt,
                     admission_receipt, budget_review):
    """Reserve one fully bounded retained allocation; cannot stack GPU reservations."""
    receipts={}
    import hashlib
    for label, name in [('price_receipt',price_receipt),('admission_receipt',admission_receipt),('budget_review',budget_review)]:
        data=Path(name).read_bytes();receipts[label]={'path':str(name),'sha256':hashlib.sha256(data).hexdigest()}
    p=Path(path)
    with p.with_suffix('.lock').open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX);v=json.loads(p.read_text())
        cost=retained_cost(v,hours=hours,finish_hours=finish_hours)
        if any(a['id']==allocation_id for a in v['allocations']):raise ValueError('Allocation already exists')
        v['allocations'].append({'id':allocation_id,'hours':hours,'reserved_usd':cost['reserved_compute_usd'],
            'state':'reserved_before_provisioning','purpose':'retained_base_sft_assessment',
            'finish_hours_within_lifetime':finish_hours,'budget':cost,'receipts':receipts})
        v['total_including_ancillary_reserve_usd']=cost['total_envelope_usd']
        v['remaining_unallocated_usd']=round(CAP_USD-cost['total_envelope_usd'],6)
        atomic_json(p,v)
        return v
