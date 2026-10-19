# Creator: Navneet Prabhakar
from copy import deepcopy
from pathlib import Path
import numpy as np
import pytest
from slm.common import checkpoint
from slm.common.training import Trainer
from slm.data.tokenized import ShardBatches,build_shards,sha
from slm.data.review import prepare,release
from slm.eval.fitting_control import ReviewedReplay,ControlInputs
from slm.train import save_checkpoint,verify_checkpoint,synchronize
from test_stage_transition import setup
from test_resume import compare
from test_review import approved_packet


def prepared(tmp_path,passes=8):
    spec,origin,source,report=setup(tmp_path)
    packet=tmp_path/'control-review.json'
    prepare(tmp_path/'raw',packet,8)
    approved_packet(packet)
    released=tmp_path/'control-release'
    release(tmp_path/'raw',packet,released)
    tokens=tmp_path/'control-tokens'
    built=build_shards(released,spec['tokenizer'],tokens,'sft',64,80)
    spec['data']=dict(kind='tokens',path=str(tokens),fingerprint=built['dataset_hash'])
    spec['releases']={sha(released/'manifest.json'):str(released)}
    spec['recipe']['accumulation_steps']=1
    with ShardBatches(spec['data']['path'],spec['tokenizer']) as base:
        spec['limits']=dict(updates=len(base)*passes,processed_positions=base.counts(len(base))[0]*passes)
    return spec,origin,source,report


def test_explicit_replay_counts_identity_and_immutable_batches(tmp_path):
    s=prepared(tmp_path);inp=ControlInputs(*s)
    try:
        base=inp.base.data;n=len(base)
        assert len(inp.data.items)==n*8
        assert inp.data.counts(n*8)==tuple(x*8 for x in base.counts(n))
        for i,batch in enumerate(inp.data.items):
            assert all(np.array_equal(a,b) for a,b in zip(batch,base[i%n]))
            assert all(not a.flags.writeable for a in batch)
        assert inp.data.schedule[-1]==dict(pass_number=8,source_batch=n-1)
        assert inp.identity!=inp.base.identity and inp.plan['initialization']==inp.base.origin
        with pytest.raises(ValueError):ReviewedReplay(base,9)
        with pytest.raises(ValueError):ReviewedReplay(base,True)
    finally:inp.close()


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_control_zero_import_and_actual_same_backend_resume(tmp_path,backend):
    if backend=='mlx':pytest.importorskip('mlx.core')
    s=prepared(tmp_path);inp=ControlInputs(*s)
    try:
        cfg,weights=checkpoint.load(inp.source_model);device='default' if backend=='mlx' else 'cpu'
        trainer=Trainer(cfg,weights,inp.data,backend,device,inp.recipe,inp.data.tokenizer_hash)
        exported=trainer.impl.export(trainer.params)
        for key in weights:np.testing.assert_array_equal(exported[key].view(np.uint32),weights[key].view(np.uint32))
        output=tmp_path/'control';output.mkdir()
        zero=save_checkpoint(output,trainer,inp,{})
        _,state=verify_checkpoint(zero,inp);assert state['step']==0
        trainer.update();synchronize(backend,device)
        first=save_checkpoint(output,trainer,inp,{})
        restored=Trainer.resume(first/'state',inp.data,backend,device,inp.data.tokenizer_hash)
        trainer.update();restored.update();synchronize(backend,device)
        compare(trainer,restored,True)
        _,final=verify_checkpoint(save_checkpoint(output,trainer,inp,{}),inp)
        assert final['cursor']==2 and final['tokens']==inp.data.counts(2)[0]
        inp.check()
    finally:inp.close()


def test_control_refuses_wrong_accumulation_or_inexact_limits(tmp_path):
    s=prepared(tmp_path)
    for key in ('accumulation','limits'):
        target=deepcopy(s[0])
        if key=='accumulation':target['recipe']['accumulation_steps']=2
        else:target['limits']['updates']+=1
        with pytest.raises(ValueError):ControlInputs(target,*s[1:])


def test_frozen_location_rejects_copied_experiment(tmp_path,monkeypatch):
    import json
    import shutil
    from slm.eval import fitting_control as control
    root=tmp_path/'first';root.mkdir();(root/'spec.json').write_text('{}\n')
    p=dict(execution_root=str((root/'training').resolve()),spec_sha256=sha(root/'spec.json'),
        source_sha256={},prior_physical_evidence={},full_step_resource_evidence={},adoptable_prior_baseline={})
    (root/'protocol.json').write_text(json.dumps(p))
    (root/'freeze.json').write_text(json.dumps(dict(protocol_sha256=sha(root/'protocol.json'))))
    monkeypatch.setattr(control,'ROOT',root)
    assert control.checked()==p
    copied=tmp_path/'copied';shutil.copytree(root,copied)
    monkeypatch.setattr(control,'ROOT',copied)
    with pytest.raises(ValueError,match='location'):control.checked()
