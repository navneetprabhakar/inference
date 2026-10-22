import copy
import pytest
from slm.restart.pilot_gate import assess,PilotRejected


def evidence():
    return dict(targets=2000000,dev_records=[{'targets':n,'evaluated_targets':200000,'nll':v} for n,v in zip([0,500000,1000000,1500000,2000000],[4.,3.9,3.85,3.8,3.7])],
        diagnostics={'grammar_items':200,'grounded_items':100,'narrative_items':100,'smoke_items':20,'evaluation_errors':0,'degenerate_smoke_items':0},
        throughput={'start_targets':250000,'end_targets':2000000,'start_active_seconds':100,'end_active_seconds':2100},active_seconds=2200,elapsed_seconds=10000)


def test_passing_metric_rules_do_not_authorize_training():
    r=assess(**evidence());assert r['status']=='PILOT_METRIC_RULES_PASS' and not r['training_authorized_by_this_check']
    assert r['measured_targets_per_second']==875
    assert r['projected_remaining_seconds_with_overhead']==pytest.approx((43409847-2000000)/875*1.25)


@pytest.mark.parametrize('fault',['short_pilot','long_pilot','slow_pilot','expired','less_improvement','regression','missing_eval','wrong_eval_count','errors','missing_narrative','collapse','short_window','prewarmup','future_window','nan','terminal','projection'])
def test_failed_or_missing_evidence_rejects_continuation(fault):
    e=evidence()
    if fault=='short_pilot':e['targets']-=1
    if fault=='long_pilot':e['targets']+=1
    if fault=='slow_pilot':e['active_seconds']=7201
    if fault=='expired':e['elapsed_seconds']=259200
    if fault=='less_improvement':e['dev_records'][-1]['nll']=3.8001
    if fault=='regression':e['dev_records'][1]['nll']=3.;e['dev_records'][2]['nll']=3.2;e['dev_records'][3]['nll']=3.3
    if fault=='missing_eval':e['dev_records'].pop(3)
    if fault=='wrong_eval_count':e['dev_records'][1]['evaluated_targets']=199999
    if fault=='errors':e['diagnostics']['evaluation_errors']=1
    if fault=='missing_narrative':e['diagnostics']['narrative_items']=99
    if fault=='collapse':e['diagnostics']['degenerate_smoke_items']=5
    if fault=='short_window':e['throughput']['end_active_seconds']=699
    if fault=='prewarmup':e['throughput']['start_targets']=249999
    if fault=='future_window':e['throughput']['end_active_seconds']=2201
    if fault=='nan':e['dev_records'][0]['nll']=float('nan')
    if fault=='terminal':e['terminal_reason']='resource stop'
    if fault=='projection':e['elapsed_seconds']=250000
    with pytest.raises(PilotRejected):assess(**e)


def test_exact_five_percent_and_ten_minute_thresholds():
    e=evidence();e['dev_records'][-1]['nll']=3.8;e['throughput']['end_active_seconds']=700
    assert assess(**e)['status']=='PILOT_METRIC_RULES_PASS'
