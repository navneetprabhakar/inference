import pytest
from slm.common.config import Config
from slm.eval.overfit import run


def test_learning_smoke_does_not_claim_success_before_learning(tmp_path):
    report=run(Config(vocab_size=16,max_seq_len=8),tmp_path/'short','torch',updates=1)
    assert report['synthetic_only'] is True and report['updates']==1
    assert report['passed'] is False
    assert report['processed_tokens']==16 and report['supervised_tokens']==10
    assert report['unique_batch_positions']==16 and report['repeated_exposures']==1
    assert (tmp_path/'short/checkpoint/state.json').exists()
    with pytest.raises(FileExistsError):run(Config(),tmp_path/'short','torch')
    with pytest.raises(ValueError):run(Config(),tmp_path/'zero','torch',updates=0)
