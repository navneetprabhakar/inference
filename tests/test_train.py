"""Reviewed-data pilot execution with synthetic source decisions only."""
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
import pytest
from slm.train import run,Inputs,verify_checkpoint
from slm.common.config import Config
from slm.common.training import Recipe,Trainer
from slm.data.tokenized import sha
from test_tokenized import setup
from test_resume import compare


def spec(tmp_path,objective='sft'):
    release,tok,report=setup(tmp_path,objective)
    from slm.common.tokenizer import BPE
    return {'version':1,'config':Config(vocab_size=BPE.load(tok).vocab_size,max_seq_len=64).to_dict(),
        'recipe':asdict(Recipe(accumulation_steps=2,embedding_implementation='dense-onehot-v1')),'seed':19,
        'tokenizer':str(tok),'data':{'kind':'tokens','path':str(tmp_path/'tokens'),'fingerprint':report['dataset_hash']},
        'releases':{sha(release/'manifest.json'):str(release)},'limits':{'updates':3,'processed_positions':10000},
        'checkpoint':{'every_updates':1,'keep':2},'scope':'synthetic_mechanics'}


def restore(report,s,backend,device=None):
    inp=Inputs(s)
    try:return Trainer.resume(Path(report['latest_checkpoint'])/'state',inp.data,backend,device or ('default' if backend=='mlx' else 'cpu'),inp.data.tokenizer_hash),inp
    except BaseException:inp.close();raise


@pytest.mark.parametrize('backend',['torch','mlx','cuda'])
@pytest.mark.parametrize('objective',['foundation','sft'])
def test_exact_resumed_pilot_and_new_invocation_counts(tmp_path,backend,objective):
    if backend=='mlx':pytest.importorskip('mlx.core')
    if backend=='cuda':
        import torch
        if not torch.cuda.is_available():pytest.skip('Actual NVIDIA wrapper validation unavailable locally')
    device='cuda' if backend=='cuda' else 'default' if backend=='mlx' else 'cpu'
    backend='torch' if backend=='cuda' else backend
    s=spec(tmp_path,objective)
    full=run(s,tmp_path/'full',backend=backend,device=device)
    first=run(s,tmp_path/'first',backend=backend,device=device,max_new_updates=1)
    second=run(s,tmp_path/'second',backend=backend,device=device,resume=first['latest_checkpoint'])
    assert first['status']=='invocation_update_limit' and second['completed_update_target']
    assert second['executed_this_invocation']['updates']==2 and second['initial']['step']==1
    assert second['executed_this_invocation']['processed_positions']==second['final']['tokens']-first['final']['tokens']
    a,ai=restore(full,s,backend,device);b,bi=restore(second,s,backend,device)
    try:compare(a,b,True)
    finally:ai.close();bi.close()
    assert full['final']==second['final'] and not full['production_accepted']
    assert len(list((tmp_path/'full/checkpoints').iterdir()))==2
    pointer=json.loads((tmp_path/'full/latest.json').read_text());assert (tmp_path/'full'/pointer['checkpoint']).is_dir()


def test_atomic_group_budget_and_no_wraparound(tmp_path):
    s=spec(tmp_path);inputs=Inputs(s)
    try:next_positions=inputs.data.counts(2)[0]
    finally:inputs.close()
    s['limits']['processed_positions']=next_positions-1
    r=run(s,tmp_path/'small');assert r['status']=='position_ceiling_before_next_atomic_update'
    assert r['final']['tokens']==0 and r['executed_this_invocation']['updates']==0
    s['limits']={'updates':1000,'processed_positions':100000}
    r=run(s,tmp_path/'exhaust');assert r['status']=='data_exhausted_before_target' and not r['completed_update_target']
    inputs=Inputs(s)
    try:assert r['final']['cursor']==len(inputs.data) and r['final']['tokens']==inputs.data.counts(len(inputs.data))[0]
    finally:inputs.close()


@pytest.mark.parametrize('defect',['vocab','context','sample_only','unapproved_lineage','payload','recipe_bool','seed','limits'])
def test_bad_data_settings_fail_before_output_and_initialization(tmp_path,monkeypatch,defect):
    s=spec(tmp_path)
    if defect=='vocab':s['config']['vocab_size']+=1
    elif defect=='context':s['config']['max_seq_len']=1
    elif defect=='recipe_bool':s['recipe']['lr']=True
    elif defect=='seed':s['seed']=True
    elif defect=='limits':s['limits']['processed_positions']=0
    else:
        p=tmp_path/'tokens/manifest.json';m=json.loads(p.read_text())
        if defect=='sample_only':
            s['releases']={sha(tmp_path/'raw/manifest.json'):str(tmp_path/'raw')};m['release_manifest_sha256']=next(iter(s['releases']))
        elif defect=='unapproved_lineage':
            f=tmp_path/'tokens/lineage.jsonl';rows=[json.loads(v) for v in f.read_text().splitlines()];rows[0]['example_id']='unapproved'
            f.write_text(''.join(json.dumps(v)+'\n' for v in rows));m['files']['lineage.jsonl']=sha(f)
        else:
            paths=m['shards'][0]['files'];x=np.fromfile(tmp_path/'tokens'/paths['x'],dtype='<u4');y=np.fromfile(tmp_path/'tokens'/paths['y'],dtype='<u4')
            index=next(i for i,v in enumerate(x) if i>0 and v>=10);x[index]=10 if x[index]!=10 else 11;y[index-1]=x[index]
            x.tofile(tmp_path/'tokens'/paths['x']);y.tofile(tmp_path/'tokens'/paths['y'])
            for name in ('x','y'):m['files'][paths[name]]=sha(tmp_path/'tokens'/paths[name])
        p.write_text(json.dumps(m));s['data']['fingerprint']=sha(p)
    monkeypatch.setattr('slm.train.initialize',lambda *a:(_ for _ in ()).throw(AssertionError('Model must not initialize')))
    with pytest.raises(ValueError):run(s,tmp_path/'output')
    assert not (tmp_path/'output').exists()


def test_resume_rejects_plan_change_and_rehashed_bad_optimizer_before_allocation(tmp_path,monkeypatch):
    s=spec(tmp_path);r=run(s,tmp_path/'first',max_new_updates=1)
    changed=deepcopy(s);changed['seed']+=1
    with pytest.raises(ValueError,match='resume plan'):run(changed,tmp_path/'wrong',resume=r['latest_checkpoint'])
    bad=tmp_path/'corrupt';shutil.copytree(r['latest_checkpoint'],bad)
    from safetensors.numpy import load_file,save_file
    raw=load_file(str(bad/'state/optimizer.safetensors'));key=next(k for k in raw if k.startswith('v:'));raw[key].flat[0]=-1
    save_file(raw,str(bad/'state/optimizer.safetensors'))
    manifest=json.loads((bad/'state/manifest.json').read_text());manifest['optimizer.safetensors']=sha(bad/'state/optimizer.safetensors');(bad/'state/manifest.json').write_text(json.dumps(manifest))
    wrapper=json.loads((bad/'manifest.json').read_text());wrapper['state/manifest.json']=sha(bad/'state/manifest.json');(bad/'manifest.json').write_text(json.dumps(wrapper))
    monkeypatch.setattr(Trainer,'__init__',lambda *a,**k:(_ for _ in ()).throw(AssertionError('No model allocation')))
    with pytest.raises(ValueError,match='Invalid optimizer'):run(s,tmp_path/'bad',resume=bad)
    assert not (tmp_path/'bad').exists()


def test_update_failure_retains_committed_checkpoint_and_orphan_log_is_not_state(tmp_path,monkeypatch):
    s=spec(tmp_path);original=Trainer.update;calls=0
    def fail(self):
        nonlocal calls
        calls+=1
        if calls==2:raise RuntimeError('Injected update failure')
        return original(self)
    monkeypatch.setattr(Trainer,'update',fail)
    with pytest.raises(RuntimeError):run(s,tmp_path/'failed')
    failure=json.loads((tmp_path/'failed/failure.json').read_text());checkpoint=Path(failure['latest_checkpoint']);assert checkpoint.is_dir()
    with (tmp_path/'failed/events.jsonl').open('a') as f:f.write('{"event":"update","step":999,"tokens":999999}\n')
    monkeypatch.setattr(Trainer,'update',original)
    r=run(s,tmp_path/'recover',resume=checkpoint)
    assert r['initial']['step']==1 and r['final']['step']==3
    assert not (tmp_path/'failed/report.json').exists()


def test_input_mutation_and_unrelated_checkpoint_paths_are_not_silently_accepted(tmp_path,monkeypatch):
    s=spec(tmp_path);original=Trainer.update;count=0
    def mutate(self):
        nonlocal count
        result=original(self);count+=1
        if count==1:(tmp_path/'reviewed/report.json').write_text('changed')
        return result
    monkeypatch.setattr(Trainer,'update',mutate)
    with pytest.raises(ValueError,match='changed during pilot'):run(s,tmp_path/'mutated')
    assert not (tmp_path/'mutated/report.json').exists()


def test_output_cannot_overlap_inputs_and_mlx_device_is_explicit(tmp_path):
    s=spec(tmp_path)
    with pytest.raises(ValueError,match='overlaps'):run(s,tmp_path/'tokens/nested-output')
    with pytest.raises(ValueError,match='device'):run(s,tmp_path/'no-output',backend='mlx',device='cpu')
    assert not (tmp_path/'tokens/nested-output').exists() and not (tmp_path/'no-output').exists()


def test_cli_saved_spec_runs_in_a_separate_process(tmp_path):
    s=spec(tmp_path);(tmp_path/'spec.json').write_text(json.dumps(s))
    result=subprocess.run([sys.executable,'-m','slm.train','--spec',str(tmp_path/'spec.json'),'--output',str(tmp_path/'cli'),
        '--max-new-updates','1'],capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)['status']=='invocation_update_limit'
    assert json.loads((tmp_path/'cli/run.json').read_text())['logical_plan']['initialization']=='canonical-random-fp32-v1'


def test_mixture_inputs_verify_each_leaf_release_and_execute(tmp_path):
    from test_mixture import components,build,paths
    cs,tok=components(tmp_path);mix=build(cs,tok,tmp_path/'mix')
    from slm.common.tokenizer import BPE
    s={'version':1,'config':Config(vocab_size=BPE.load(tok).vocab_size,max_seq_len=64).to_dict(),
       'recipe':asdict(Recipe(accumulation_steps=3,embedding_implementation='dense-onehot-v1')),'seed':5,
       'tokenizer':str(tok),'data':{'kind':'mixture','path':str(tmp_path/'mix'),'fingerprint':mix['dataset_hash'],'bindings':{k:str(v) for k,v in paths(cs).items()}},
       'releases':{sha(c['path'].parent/'reviewed/manifest.json'):str(c['path'].parent/'reviewed') for c in cs},
       'limits':{'updates':2,'processed_positions':10000},'checkpoint':{'every_updates':1,'keep':2},'scope':'synthetic_mechanics'}
    from slm.data.mixture import MixtureBatches
    with MixtureBatches(tmp_path/'mix',paths(cs),tok) as data:expected=sum(data[i][0].size for i in range(6))
    r=run(s,tmp_path/'run');assert r['final']['cursor']==6 and r['final']['tokens']==expected


def test_curriculum_stops_at_gate_and_accepted_bound_actual_student_screen_allows_next_stage(tmp_path):
    from test_curriculum import fixture as curriculum_fixture
    from slm.data.curriculum import CurriculumBatches
    from slm.common.curriculum import CurriculumTrainer
    from slm.common.tokenizer import BPE
    from slm.common.config import initialize
    stages,bindings,tok,recipe,report=curriculum_fixture(tmp_path)
    s={'version':1,'config':Config(vocab_size=BPE.load(tok).vocab_size,max_seq_len=512).to_dict(),
       'recipe':asdict(recipe),'seed':7,'tokenizer':str(tok),
       'data':{'kind':'curriculum','path':str(tmp_path/'plan'),'fingerprint':report['dataset_hash'],
               'bindings':{k:{'path':str(v['path']),'components':{kk:str(vv) for kk,vv in v['components'].items()}} for k,v in bindings.items()}},
       'releases':{sha(Path(p).parent/'reviewed/manifest.json'):str(Path(p).parent/'reviewed') for b in bindings.values() for p in b['components'].values()},
       'limits':{'updates':report['optimizer_updates'],'processed_positions':100000},'checkpoint':{'every_updates':1000,'keep':2},'scope':'synthetic_mechanics'}
    first=run(s,tmp_path/'first');assert first['status']=='stage_review_required' and first['final']['step']<s['limits']['updates']
    from slm.inference.greedy import GreedyModel
    from slm.eval.cases import candidate_suite
    from slm.eval.conversation import evaluate
    from test_language import reviewed,policy
    suite=candidate_suite();exact=next(c for c in suite['cases'] if c['style']=='professional' and c['oracle']['kind']!='human')
    human=next(c for c in suite['cases'] if c['style']=='professional' and c['oracle']['kind']=='human')
    suite['cases']=[exact,human]
    model=GreedyModel(Path(first['latest_checkpoint'])/'state/model',tok,'torch','cpu',expected_tokenizer_hash=sha(tok/'manifest.json'),embedding_implementation=recipe.embedding_implementation)
    results=evaluate(suite,model,1);sr,hr=reviewed(suite,results)
    # Explicit zero-threshold mechanics policy. Random-model grades stay false;
    # this is not the production policy or human review/capability evidence.
    for row in hr['cases'].values():row['grades']={k:False for k in row['grades']}
    p=policy();p.update(status='accepted',policy_id='synthetic-zero-threshold-stage-mechanics',requires_baseline=False,
        min_cases=2,min_scenarios=2,min_template_families=2,min_cases_per_slice=1,min_human_per_style=1,
        required_slices=sorted({c['slice'] for c in suite['cases']}),required_styles=['professional'],exact_min_rate=0.,human_min_rate=0.)
    docs={'suite':suite,'result':results,'policy':p,'suite_review':sr,'output_review':hr,'baseline':None,'baseline_review':None};bundle={}
    for key,value in docs.items():
        path=tmp_path/(key+'.json')
        if value is not None:path.write_text(json.dumps(value));bundle[key]=str(path)
        else:bundle[key]=None
    # A proposed or rejected screen must not advance, even with valid bindings.
    proposed=deepcopy(p);proposed['status']='proposed';Path(bundle['policy']).write_text(json.dumps(proposed))
    blocked=run(s,tmp_path/'blocked',resume=first['latest_checkpoint'],gates={'foundation':bundle})
    assert blocked['status']=='stage_review_required' and blocked['executed_this_invocation']['updates']==0
    Path(bundle['policy']).write_text(json.dumps(p))
    second=run(s,tmp_path/'second',resume=first['latest_checkpoint'],gates={'foundation':bundle})
    assert second['status']=='stage_review_required' and 'foundation' in second['passed_stage_gates']
    # The final stage still needs its own review; no reset/replay in the second stage.
    inputs=Inputs(s)
    try:
        reference=CurriculumTrainer(inputs.config,initialize(inputs.config,s['seed']),inputs.data,'torch','cpu',inputs.recipe,inputs.data.tokenizer_hash)
        while reference.cursor<len(inputs.data):reference.update()
        resumed=CurriculumTrainer.resume(Path(second['latest_checkpoint'])/'state',inputs.data,'torch','cpu')
        compare(reference,resumed,True)
    finally:inputs.close()
    third=run(s,tmp_path/'third',resume=second['latest_checkpoint'],gates={'foundation':bundle})
    assert third['executed_this_invocation']['updates']==0 and third['status']=='stage_review_required'
    with pytest.raises(ValueError,match='Prior stage acceptance'):
        run(s,tmp_path/'missing-evidence',resume=second['latest_checkpoint'])



def test_soft_wall_limit_saves_zero_step_and_retention_ignores_unrelated_paths(tmp_path,monkeypatch):
    s=spec(tmp_path);r=run(s,tmp_path/'wall',wall_seconds=1e-12)
    assert r['status']=='soft_wall_limit' and r['final']['step']==0
    original=Trainer.update
    outside=tmp_path/'unrelated';outside.mkdir();(outside/'keep.txt').write_text('preserve')
    def insert(self):
        value=original(self)
        if self.step==1:
            root=tmp_path/'retained/checkpoints';root.mkdir(exist_ok=True)
            (root/'notes').mkdir();(root/'notes/keep.txt').write_text('notes')
            (root/'999999999999-aaaaaaaaaaaa').symlink_to(outside,target_is_directory=True)
        return value
    monkeypatch.setattr(Trainer,'update',insert)
    r=run(s,tmp_path/'retained');assert r['completed_update_target']
    assert (outside/'keep.txt').read_text()=='preserve' and (tmp_path/'retained/checkpoints/notes/keep.txt').read_text()=='notes'
    assert len([p for p in (tmp_path/'retained/checkpoints').iterdir() if p.name[:12].isdigit() and not p.is_symlink()])==2


def test_raw_attempt_directory_and_orphaned_checkpoint_are_not_resumable(tmp_path):
    s=spec(tmp_path);r=run(s,tmp_path/'run',max_new_updates=1)
    (tmp_path/'run/latest.json').write_text('{"checkpoint":"wrong","step":999}')
    with pytest.raises(ValueError,match='file set'):run(s,tmp_path/'wrong',resume=tmp_path/'run')
    # The explicit valid checkpoint still works: no trust in the modified pointer.
    out=run(s,tmp_path/'resumed',resume=r['latest_checkpoint']);assert out['initial']['step']==1
    bad=tmp_path/'orphan';shutil.copytree(r['latest_checkpoint'],bad);(bad/'manifest.json').unlink()
    with pytest.raises((ValueError,FileNotFoundError)):run(s,tmp_path/'bad-orphan',resume=bad)
    assert not (tmp_path/'bad-orphan').exists()


def test_preflight_relative_spec_and_saved_spec_are_reusable_from_other_cwd(tmp_path):
    s=spec(tmp_path)
    s['tokenizer']='tokenizer';s['data']['path']='tokens';s['releases']={k:'reviewed' for k in s['releases']}
    path=tmp_path/'relative.json';path.write_text(json.dumps(s))
    root=Path(__file__).parents[1]
    env=__import__('os').environ.copy();env['PYTHONPATH']=str(root/'src')
    result=subprocess.run([sys.executable,'-m','slm.train','--spec',str(path),'--preflight-only'],cwd='/',env=env,capture_output=True,text=True,check=True)
    assert not json.loads(result.stdout)['training_started']
    subprocess.run([sys.executable,'-m','slm.train','--spec',str(path),'--output',str(tmp_path/'first-relative'),'--max-new-updates','1'],cwd='/',env=env,capture_output=True,text=True,check=True)
    saved=json.loads((tmp_path/'first-relative/spec.json').read_text());assert Path(saved['tokenizer']).is_absolute()
    r=json.loads((tmp_path/'first-relative/report.json').read_text())
    result=subprocess.run([sys.executable,'-m','slm.train','--spec',str(tmp_path/'first-relative/spec.json'),'--output',str(tmp_path/'resume-relative'),'--resume',r['latest_checkpoint']],cwd='/',env=env,capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)['completed_update_target']


def test_hash_identity_allows_relocated_reviewed_artifacts(tmp_path):
    s=spec(tmp_path);first=run(s,tmp_path/'first',max_new_updates=1)
    moved=tmp_path/'moved';moved.mkdir()
    for name in ('reviewed','tokens','tokenizer'):shutil.copytree(tmp_path/name,moved/name)
    other=deepcopy(s);other['tokenizer']=str(moved/'tokenizer');other['data']['path']=str(moved/'tokens')
    other['releases']={k:str(moved/'reviewed') for k in s['releases']}
    second=run(other,tmp_path/'second',resume=first['latest_checkpoint']);assert second['completed_update_target'] and second['plan_hash']==first['plan_hash']



def test_wrapper_backend_transfer_retains_plan_and_exact_imported_values(tmp_path):
    pytest.importorskip('mlx.core')
    s=spec(tmp_path);a=run(s,tmp_path/'torch-first',max_new_updates=1)
    torch_state,ti=restore(a,s,'torch');mlx_state,mi=restore(a,s,'mlx')
    try:compare(torch_state,mlx_state,True)
    finally:ti.close();mi.close()
    b=run(s,tmp_path/'mlx-next',backend='mlx',device='default',resume=a['latest_checkpoint'],max_new_updates=1)
    c=run(s,tmp_path/'torch-last',resume=b['latest_checkpoint'])
    assert a['plan_hash']==b['plan_hash']==c['plan_hash'] and c['initial']['step']==2 and c['final']['step']==3



def test_checkpoint_changed_during_restore_is_detected_before_any_update(tmp_path,monkeypatch):
    s=spec(tmp_path);first=run(s,tmp_path/'first',max_new_updates=1)
    copy=tmp_path/'input-copy';shutil.copytree(first['latest_checkpoint'],copy)
    original=Trainer.resume.__func__
    def mutate(cls,path,*args,**kwargs):
        trainer=original(cls,path,*args,**kwargs)
        with (Path(path)/'state.json').open('a') as f:f.write(' ')
        return trainer
    monkeypatch.setattr(Trainer,'resume',classmethod(mutate))
    monkeypatch.setattr(Trainer,'update',lambda *a:(_ for _ in ()).throw(AssertionError('Must not update after input changes')))
    with pytest.raises(ValueError,match='changed during pilot'):run(s,tmp_path/'changed',resume=copy)
    assert not (tmp_path/'changed/report.json').exists()



def test_final_checkpoint_corruption_does_not_report_completion_and_prior_state_survives(tmp_path,monkeypatch):
    import slm.train as runner
    s=spec(tmp_path);save=runner.save_checkpoint;corrupted=False
    def corrupt(output,trainer,inputs,passed):
        nonlocal corrupted
        path=save(output,trainer,inputs,passed)
        if trainer.step==3 and not corrupted:
            corrupted=True
            with (path/'state/model/model.safetensors').open('ab') as f:f.write(b'corrupt')
        return path
    monkeypatch.setattr(runner,'save_checkpoint',corrupt)
    with pytest.raises(ValueError,match='checksum'):run(s,tmp_path/'damaged')
    assert not (tmp_path/'damaged/report.json').exists()
    failure=json.loads((tmp_path/'damaged/failure.json').read_text())
    checkpoint=Path(failure['latest_checkpoint']);assert json.loads((checkpoint/'state/state.json').read_text())['step']==2
    monkeypatch.setattr(runner,'save_checkpoint',save)
    r=run(s,tmp_path/'recovered',resume=checkpoint);assert r['initial']['step']==2 and r['completed_update_target']
