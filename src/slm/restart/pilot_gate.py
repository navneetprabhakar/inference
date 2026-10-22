"""Pure pilot acceptance arithmetic; not authorization or an execution receipt.

The launcher must supply hash-bound evaluation/supervisor evidence. A returned
PASS cannot replace correctness, resource, identity or numerical-suite checks.
"""
import math


class PilotRejected(ValueError):pass


def assess(*,targets,dev_records,diagnostics,throughput,active_seconds,elapsed_seconds,
           target_cap=43409847,terminal_reason=None):
    def finite(value):return type(value) in (int,float) and math.isfinite(value)
    def reject(reason):raise PilotRejected(reason)
    if terminal_reason is not None:reject('Existing terminal stop')
    if type(targets) is not int or targets!=2000000:reject('Pilot must end at exactly 2M targets')
    if type(target_cap) is not int or not targets<target_cap<=48000000:reject('Invalid full target cap')
    if not finite(active_seconds) or not 0<active_seconds<=7200:reject('Pilot active-time limit')
    if not finite(elapsed_seconds) or not active_seconds<=elapsed_seconds<259200:reject('Execution elapsed-time limit')
    required=(0,500000,1000000,1500000,2000000)
    if not isinstance(dev_records,list) or len(dev_records)!=len(required):reject('Incomplete pilot development history')
    best=None;streak=0;losses=[]
    for row,at in zip(dev_records,required):
        if (type(row.get('targets')) is not int or row['targets']!=at
                or row.get('evaluated_targets')!=200000 or type(row.get('evaluated_targets')) is not int
                or not finite(row.get('nll')) or row['nll']<=0):reject('Invalid development record')
        value=row['nll'];losses.append(value)
        streak=streak+1 if best is not None and value>best*1.05 else 0
        if streak>=2:reject('Two consecutive pilot development regressions')
        best=value if best is None else min(best,value)
    improvement=1-losses[-1]/losses[0]
    if losses[-1]>.95*losses[0]:reject('Pilot loss improved less than 5%')
    expected={'grammar_items':200,'grounded_items':100,'narrative_items':100,'smoke_items':20,'evaluation_errors':0}
    if not isinstance(diagnostics,dict) or any(type(diagnostics.get(k)) is not int or diagnostics[k]!=v for k,v in expected.items()):
        reject('Incomplete/erroring development diagnostics')
    bad=diagnostics.get('degenerate_smoke_items')
    if type(bad) is not int or not 0<=bad<=20:reject('Invalid generation diagnostic')
    if bad>=5:reject('Generation collapse')
    keys=('start_targets','end_targets','start_active_seconds','end_active_seconds')
    if not isinstance(throughput,dict) or any(k not in throughput for k in keys):reject('Missing throughput window')
    start,end=throughput['start_targets'],throughput['end_targets']
    a,b=throughput['start_active_seconds'],throughput['end_active_seconds']
    if (type(start) is not int or type(end) is not int or not 250000<=start<end<=targets
            or not finite(a) or not finite(b) or not 0<=a<b<=active_seconds or b-a<600):
        reject('Need >=10 minutes of measured post-warmup throughput')
    rate=(end-start)/(b-a)
    projected=(target_cap-targets)/rate*1.25
    active_remaining=129600-active_seconds;elapsed_remaining=259200-elapsed_seconds
    if projected>min(active_remaining,elapsed_remaining):reject('Remaining work plus 25% overhead does not fit time budget')
    return {'status':'PILOT_METRIC_RULES_PASS','relative_nll_improvement':improvement,
            'measured_targets_per_second':rate,'projected_remaining_seconds_with_overhead':projected,
            'remaining_active_seconds':active_remaining,'remaining_elapsed_seconds':elapsed_remaining,
            'training_authorized_by_this_check':False}
