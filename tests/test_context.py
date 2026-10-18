import json
import pytest
from slm.common.config import Config,initialize
from slm.common.checkpoint import save
from slm.eval.context import probe


def test_context_boundary_and_reference_identity(tmp_path):
    config=Config(max_seq_len=16)
    save(tmp_path/'model',config,initialize(config))
    first=probe(tmp_path/'model',tmp_path/'first','torch')
    second=probe(tmp_path/'model',tmp_path/'second','torch',reference=tmp_path/'first')
    assert first['passed'] and second['passed'] and second['cross_backend_reference']
    assert first['positions']==[0,8,15] and first['length']==16
    assert first['parameters']==config.parameter_count
    with pytest.raises(ValueError):probe(tmp_path/'model',tmp_path/'bad','torch',length=17)
    save(tmp_path/'different',config,initialize(config,seed=43))
    with pytest.raises(ValueError,match='identity differs'):
        probe(tmp_path/'different',tmp_path/'mismatch','torch',reference=tmp_path/'first')
    failed=json.loads((tmp_path/'mismatch/report.json').read_text())
    assert not failed['passed']
    with (tmp_path/'first/context-probes.safetensors').open('ab') as f:f.write(b'corrupt')
    with pytest.raises(ValueError,match='checksum'):
        probe(tmp_path/'model',tmp_path/'corrupt','torch',reference=tmp_path/'first')


def test_mlx_context_reference_matches_torch(tmp_path):
    pytest.importorskip('mlx.core')
    c=Config(max_seq_len=32)
    save(tmp_path/'model',c,initialize(c))
    probe(tmp_path/'model',tmp_path/'mlx','mlx')
    result=probe(tmp_path/'model',tmp_path/'torch','torch',reference=tmp_path/'mlx')
    assert result['passed'] and 'layer:1' in result['checks']


def test_nonfinite_unsampled_position_is_not_hidden(tmp_path,monkeypatch):
    from slm.backends import torch_backend as impl
    c=Config(max_seq_len=16);save(tmp_path/'model',c,initialize(c))
    original=impl.forward
    def broken(*args,**kwargs):
        logits,cache,layers=original(*args,**kwargs)
        logits[0,1,0]=float('nan')  # Position 1 is outside the exported sample grid.
        return logits,cache,layers
    monkeypatch.setattr(impl,'forward',broken)
    with pytest.raises(FloatingPointError,match='Nonfinite full-context'):
        probe(tmp_path/'model',tmp_path/'out','torch')
    assert json.loads((tmp_path/'out/report.json').read_text())['passed'] is False
