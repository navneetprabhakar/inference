import copy
import pytest
from slm.restart.pilot_barrier import PilotBarrier
from slm.restart.pilot_gate import PilotRejected
from test_restart_pilot_gate import evidence


def open_barrier(path,run='fixture'):
    return PilotBarrier(path,run_identity=run,schedule_hash='bound-schedule',evaluation_hash='bound-evaluation')


def test_undecided_barrier_stops_exact_pilot_crossing(tmp_path):
    b=open_barrier(tmp_path/'gate.sqlite')
    b.require_update(start_targets=1999000,end_targets=2000000)
    with pytest.raises(PilotRejected):b.require_update(start_targets=2000000,end_targets=2001000)
    with pytest.raises(ValueError):b.require_update(start_targets=1999999,end_targets=2000001)
    b.close()


def test_pass_persists_and_cannot_be_replaced(tmp_path):
    p=tmp_path/'gate.sqlite';b=open_barrier(p);r=b.decide(evidence(),checkpoint_sha256='a'*64);b.close()
    b=open_barrier(p);assert b.decision()==r
    b.require_update(start_targets=2000000,end_targets=2008192)
    with pytest.raises(ValueError,match='already decided'):b.decide(evidence(),checkpoint_sha256='b'*64)
    b.close()


def test_failed_pilot_blocks_checkpoint_rollback_and_replacement(tmp_path):
    p=tmp_path/'gate.sqlite';b=open_barrier(p);e=evidence();e['dev_records'][-1]['nll']=4.
    assert b.decide(e,checkpoint_sha256='a'*64)['result']['status']=='PILOT_REJECTED';b.close()
    b=open_barrier(p)
    for first,last in [(0,8192),(1000000,1008192),(2000000,2008192)]:
        with pytest.raises(PilotRejected):b.require_update(start_targets=first,end_targets=last)
    with pytest.raises(ValueError):b.decide(evidence(),checkpoint_sha256='a'*64)
    b.close()


def test_changed_identity_or_decision_rejected(tmp_path):
    p=tmp_path/'gate.sqlite';b=open_barrier(p);b.decide(evidence(),checkpoint_sha256='a'*64)
    with pytest.raises(ValueError,match='contract'):open_barrier(p,'other-run')
    b.db.execute("UPDATE pilot_decision SET result='{}'")
    with pytest.raises(ValueError,match='inconsistent'):b.require_update(start_targets=2000000,end_targets=2008192)
    b.close()


def test_missing_required_metric_is_persisted_failure(tmp_path):
    b=open_barrier(tmp_path/'gate.sqlite');e=evidence();del e['diagnostics']
    assert b.decide(e,checkpoint_sha256='a'*64)['result']['status']=='PILOT_REJECTED'
    with pytest.raises(PilotRejected):b.require_update(start_targets=0,end_targets=3)
    b.close()


def test_nonfinite_evidence_is_durable_failure(tmp_path):
    p=tmp_path/'gate.sqlite';b=open_barrier(p);e=evidence();e['dev_records'][0]['nll']=float('nan')
    assert b.decide(e,checkpoint_sha256='a'*64)['result']['status']=='PILOT_REJECTED';b.close()
    b=open_barrier(p)
    with pytest.raises(PilotRejected):b.require_update(start_targets=0,end_targets=1)
    b.close()
