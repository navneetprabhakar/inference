import pytest
from slm.eval.portability import create
from slm.eval.state_transfer import audit


def test_state_transfer_hashes_values_and_keeps_counters(tmp_path):
    create(tmp_path/'fixture','torch')
    result=audit(tmp_path/'fixture/initial',tmp_path/'fixture',tmp_path/'audit.json','torch')
    assert result['passed'] and result['updates_performed']==0
    assert result['values_checked']==3*20640
    assert result['counters']['step']==2
    assert result['source_content_sha256']==result['imported_content_sha256']
    with pytest.raises(FileExistsError):audit(tmp_path/'fixture/initial',tmp_path/'fixture',tmp_path/'audit.json','torch')
