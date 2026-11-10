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
