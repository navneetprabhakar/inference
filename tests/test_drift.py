from slm.eval.portability import create
from slm.eval.drift import diagnose


def test_diagnostics_do_not_approve_and_continue_past_failed_probe(tmp_path,monkeypatch):
    import slm.eval.drift as module
    create(tmp_path/'fixture','torch')
    def fail(*args):raise AssertionError('Injected comparison failure')
    monkeypatch.setattr(module,'compare',fail)
    report=diagnose(tmp_path/'fixture',tmp_path/'fixture/initial',tmp_path/'report.json','torch')
    assert report['diagnostic_only'] and not report['accepted_for_training_portability']
    assert report['completed_update_step']==4 and report['all_probes_finite']
    assert set(report['checks'])=={'2','4'}
    assert all(not c['policy_checks_passed'] and c['failed_tensors'] for c in report['checks'].values())
