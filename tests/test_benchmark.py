import pytest
from slm.common.config import Config
from slm.eval.benchmark import run


def test_timing_excludes_warmup_and_keeps_reference_scope(tmp_path):
    r=run(Config(),tmp_path/'result.json','torch','cpu',length=8,warmup=1,steps=2)
    assert r['passed'] and r['synthetic_only']
    assert r['measured_token_positions']==16 and r['history'][-1]['tokens']==24
    assert r['history'][0]['step']==2 and r['history'][-1]['step']==3
    assert r['token_positions_per_second']>0 and 'host gradient' in r['scope']
    with pytest.raises(FileExistsError):run(Config(),tmp_path/'result.json','torch','cpu',length=8)
    with pytest.raises(ValueError):run(Config(),tmp_path/'bad','torch','cpu',length=65)
