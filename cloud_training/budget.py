"""Conservative reservation ledger. Billing alerts are not a spending interlock."""
from pathlib import Path
import fcntl
import math
from cloud_training.runtime import atomic_json
import json

CAP_USD=100.  # User approved total project cap on 2026-11-10
RESERVE_USD=10.  # storage, network, operations and invoice contingency
HOURLY_ENVELOPE_USD=6.  # single A2-1g in selected US region incl disk/IP headroom


def reserve(path, allocation_id, hours):
    path=Path(path)
    if not isinstance(hours,(int,float)) or not math.isfinite(hours) or not 0<hours<=3:
        raise ValueError('VM lease must be <=3 hours')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.with_suffix('.lock').open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX)
        state=json.loads(path.read_text()) if path.exists() else {'cap_usd':CAP_USD,'ancillary_reserve_usd':RESERVE_USD,'allocations':[]}
        if state['cap_usd']!=CAP_USD or state['ancillary_reserve_usd']!=RESERVE_USD:raise ValueError('budget policy changed')
        if any(a['id']==allocation_id for a in state['allocations']):raise ValueError('allocation already reserved; inspect existing VM instead of retrying')
        cost=hours*HOURLY_ENVELOPE_USD
        if sum(a['reserved_usd'] for a in state['allocations'])+cost+RESERVE_USD>CAP_USD:
            raise ValueError('explicit approval required beyond total budget')
        state['allocations'].append({'id':allocation_id,'hours':hours,'reserved_usd':cost,'state':'reserved_before_provisioning'})
        state['total_including_ancillary_reserve_usd']=sum(a['reserved_usd'] for a in state['allocations'])+RESERVE_USD
        state['remaining_unallocated_usd']=CAP_USD-state['total_including_ancillary_reserve_usd']
        atomic_json(path,state)
        return state
