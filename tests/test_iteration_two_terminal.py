"""Partial or fresh terminal runs cannot impersonate the selected continuation."""
# Creator: Navneet Prabhakar
from types import SimpleNamespace
import pytest
from slm.eval.iteration_two_terminal import verify_terminal


class Data:
    def __len__(self):return 9984
    def counts(self,cursor):
        assert cursor==9984
        return 10223491,10223491


def fixture():
    inputs=SimpleNamespace(data=Data(),recipe=SimpleNamespace(accumulation_steps=1),identity='plan',plan={})
    report=dict(plan_hash='plan',status='data_exhausted_before_target',initial=dict(step=256,cursor=256,tokens=262144,supervised_tokens=262144),
        final=dict(step=9984,cursor=9984,tokens=10223491,supervised_tokens=10223491),
        executed_this_invocation=dict(updates=9728,processed_positions=9961347,supervised_positions=9961347))
    launch=dict(plan_hash='plan',logical_plan={},resume_manifest_sha256='selected-checkpoint')
    selection=dict(selected=dict(checkpoint_manifest_sha256='selected-checkpoint'),maximum_physical_positions_after_continuation=10485635,continuation_reserved_positions=9961347)
    return report,launch,inputs,selection


def test_complete_verified_resume_counts_both_chains_physical_work():
    report,launch,inputs,selection=fixture()
    assert verify_terminal(report,launch,inputs,selection)==report['final']


@pytest.mark.parametrize('defect',['partial','fresh','wrong_checkpoint','extra_budget','wrong_plan','wrong_executed','wrong_final'])
def test_terminal_refuses_incomplete_or_mismatched_training_chain(defect):
    report,launch,inputs,selection=fixture()
    if defect=='partial':report['status']='soft_wall_limit'
    elif defect=='fresh':report['initial']=dict(step=0,cursor=0,tokens=0,supervised_tokens=0)
    elif defect=='wrong_checkpoint':launch['resume_manifest_sha256']='other-checkpoint'
    elif defect=='extra_budget':selection['maximum_physical_positions_after_continuation']+=1024
    elif defect=='wrong_plan':launch['logical_plan']={'wrong':True}
    elif defect=='wrong_executed':report['executed_this_invocation']['processed_positions']+=1024
    else:report['final']['step']-=1
    with pytest.raises(ValueError,match='Complete selected-chain'):verify_terminal(report,launch,inputs,selection)
