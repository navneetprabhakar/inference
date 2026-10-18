"""Synthetic curriculum mechanics only, no public/teacher training approval."""
from dataclasses import asdict,replace
import json
import shutil
import subprocess
import sys
import numpy as np
import pytest
pytest.importorskip('tokenizers')
from slm.common.config import Config,initialize
from slm.common.training import Trainer,Recipe
from slm.common.curriculum import CurriculumTrainer
from slm.data.curriculum import CurriculumBatches,build_curriculum
from slm.data.mixture import MixtureBatches
from slm.data.tokenized import sha
from test_mixture import components,build,paths
from test_resume import compare


def fixture(tmp_path):
    stages=[];bindings={};tok=None;used_accumulation=set()
    for name,objective,k,rate in [('foundation','foundation',3,.001),('conversation','sft',2,.0002)]:
        root=tmp_path/name;root.mkdir();cs,tok=components(root,objective)
        opts={} if objective=='foundation' else {'objective':'sft','budget':200,'minimum':100,'group_cap':20}
        r=build(cs,tok,root/'mixture',**opts)
        # Artifact hashes intentionally change order. Guarantee short tails instead of
        # relying on one incidental schedule's number of batches.
        k=next(v for v in range(k,17) if r['batches']%v and v not in used_accumulation)
        used_accumulation.add(k)
        with MixtureBatches(root/'mixture',paths(cs),tok) as data:
            warmup=max(64,data.counts(k)[0]+1) if objective=='sft' else 64
        schedule={'lr':rate,'warmup_tokens':warmup,'cooldown_tokens':64,'final_lr_fraction':.1,'accumulation_steps':k}
        stages.append({'id':name,'path':root/'mixture','components':paths(cs),'dataset_hash':r['dataset_hash'],'schedule':schedule})
        bindings[name]={'path':root/'mixture','components':paths(cs)}
    base=Recipe(embedding_implementation='dense-onehot-v1')
    r=build_curriculum(stages,tok,tmp_path/'plan',recipe=base,family_processed_cap=100000)
    return stages,bindings,tok,base,r


def open_plan(tmp_path,bindings,tok):return CurriculumBatches(tmp_path/'plan',bindings,tok)


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_exact_stage_boundary_resume_preserves_global_adam_and_short_tail(tmp_path,backend):
    if backend=='mlx':pytest.importorskip('mlx.core')
    stages,bindings,tok,base,r=fixture(tmp_path)
    with open_plan(tmp_path,bindings,tok) as data:
        c=Config(vocab_size=data.vocab_size);a=CurriculumTrainer(c,initialize(c),data,backend)
        # Save mid-stage, exactly at transition, and after the first next-stage update.
        own=None;history=[]
        while a.cursor<len(data):
            start=a.cursor;out=a.update();history.append(out)
            if own is not None:
                assert out==own.update();compare(a,own,True)
            if len(history)==1 or out['stage_completed'] or (out['stage']=='conversation' and out['stage_updates']==1):
                dest=tmp_path/f'state-{a.step}';a.save(dest)
                own=CurriculumTrainer.resume(dest,data,backend);compare(a,own,True)
                state=json.loads((dest/'state.json').read_text())
                assert state['version']==3 and state['curriculum']==data.progress(a.cursor)
            assert out['microbatches']<=data.inventory.recipes[0 if out['stage']=='foundation' else 1].accumulation_steps
            assert data.counts(a.cursor)==(a.tokens,a.supervised_tokens)
            assert out['lr']==data.rate(start,a.cursor)
        assert a.step==r['optimizer_updates'] and a.tokens==r['processed_positions']
        assert data.progress(a.cursor)['next_stage'] is None
        boundary=next(i for i,row in enumerate(history) if row['stage']=='foundation' and row['stage_completed'])
        first_k=data.inventory.recipes[0].accumulation_steps;second_k=data.inventory.recipes[1].accumulation_steps
        assert first_k!=second_k
        assert history[boundary]['microbatches']==len(data.inventory.data[0])%first_k<first_k
        assert history[boundary+1]['stage']=='conversation' and history[boundary+1]['stage_updates']==1
        assert history[-1]['microbatches']==len(data.inventory.data[1])%second_k<second_k and history[-1]['stage_completed']
        assert history[-1]['lr']==pytest.approx(.00002)
        with pytest.raises(StopIteration):a.update()
        with pytest.raises(ValueError,match='CurriculumTrainer'):Trainer(c,initialize(c),data)


def test_global_adam_bias_correction_and_stage_lr_match_manual_reference(tmp_path,monkeypatch):
    stages,bindings,tok,base,r=fixture(tmp_path)
    with open_plan(tmp_path,bindings,tok) as data:
        c=Config(vocab_size=data.vocab_size);actual=CurriculumTrainer(c,initialize(c),data)
        # Independent stage-by-stage Trainer run with manually preserved global clock.
        weights=initialize(c);moments={};step=0;global_cursor=0
        for stage,d,srecipe in zip(stages,data.inventory.data,data.inventory.recipes):
            ref=Trainer(c,weights,d,recipe=srecipe,tokenizer_hash=data.tokenizer_hash)
            ref.moments=moments;ref.step=step
            while ref.cursor<len(d):
                # Vanilla Trainer has a local token clock; only apply the explicit cooldown externally.
                expected_rate=data.rate(global_cursor,min(global_cursor+srecipe.accumulation_steps,data.inventory.ends[0 if stage['id']=='foundation' else 1]))
                monkeypatch.setattr(ref,'_update_rate',lambda recipe,end,tokens:expected_rate)
                rr=ref.update();ar=actual.update();global_cursor+=rr['microbatches']
                assert ar['lr']==rr['lr']==expected_rate and ar['step']==rr['step']
                for k,v in ref.impl.export(ref.params).items():np.testing.assert_array_equal(v,actual.impl.export(actual.params)[k])
                for slot in (0,1):
                    a=actual.impl.export({k:v[slot] for k,v in actual.moments.items()});b=ref.impl.export({k:v[slot] for k,v in ref.moments.items()})
                    for k in a:np.testing.assert_array_equal(a[k],b[k])
            weights=ref.impl.export(ref.params);moments=ref.moments;step=ref.step
        assert step==r['optimizer_updates']


@pytest.mark.parametrize('defect',['duplicate_stage','hash','unknown_schedule','warmup_overlap','zero_accumulation','fraction','family_cap','recipe','raw'])
def test_invalid_curriculum_contract_never_publishes(tmp_path,defect):
    stages,bindings,tok,base,r=fixture(tmp_path)
    cap=100000
    if defect=='duplicate_stage':stages[1]['id']=stages[0]['id']
    elif defect=='hash':stages[0]['dataset_hash']=None
    elif defect=='unknown_schedule':stages[0]['schedule']['beta1']=.8
    elif defect=='warmup_overlap':stages[0]['schedule']['warmup_tokens']=100000
    elif defect=='zero_accumulation':stages[0]['schedule']['accumulation_steps']=0
    elif defect=='fraction':stages[0]['schedule']['final_lr_fraction']=float('nan')
    elif defect=='family_cap':cap=1
    elif defect=='recipe':base={}
    else:stages[0]['path']=tmp_path/'foundation/alpha/raw'
    with pytest.raises((ValueError,KeyError)):build_curriculum(stages,tok,tmp_path/'bad',recipe=base,family_processed_cap=cap)
    assert not (tmp_path/'bad').exists() and not list(tmp_path.glob('.curriculum-*'))


def rehash_state(path,mutate):
    p=path/'state.json';s=json.loads(p.read_text());mutate(s);p.write_text(json.dumps(s))
    p=path/'manifest.json';m=json.loads(p.read_text());m['state.json']=sha(path/'state.json');p.write_text(json.dumps(m))


@pytest.mark.parametrize('defect',['step','cursor','tokens','receipt','receipt_bool','optimizer_reset','accumulation','recipe','version'])
def test_rehashed_training_state_cannot_skip_stage_or_reset_optimizer(tmp_path,defect):
    stages,bindings,tok,base,r=fixture(tmp_path)
    with open_plan(tmp_path,bindings,tok) as data:
        a=CurriculumTrainer(Config(vocab_size=data.vocab_size),initialize(Config(vocab_size=data.vocab_size)),data)
        a.update();a.save(tmp_path/'state')
        def mutate(s):
            if defect=='step':s['step']=0
            elif defect=='cursor':s['cursor']=1
            elif defect=='tokens':s['tokens']+=1
            elif defect=='receipt':s['curriculum']['next_stage']='conversation'
            elif defect=='receipt_bool':s['curriculum']['stages'][0]['updates']=True
            elif defect=='optimizer_reset':s['curriculum']['global_updates']=0
            elif defect=='accumulation':s['accumulation']['pending_microbatches']=1
            elif defect=='recipe':s['recipe']['beta1']=.8
            else:s['version']=2
        rehash_state(tmp_path/'state',mutate)
        with pytest.raises(ValueError):CurriculumTrainer.resume(tmp_path/'state',data)
        with pytest.raises(ValueError):Trainer.resume(tmp_path/'state',data,tokenizer_hash=data.tokenizer_hash)


def test_plan_is_portable_pinned_and_changes_cannot_be_silent_on_resume(tmp_path):
    stages,bindings,tok,base,r=fixture(tmp_path)
    rebuilt=build_curriculum(stages,tok,tmp_path/'same',recipe=base,family_processed_cap=100000)
    assert rebuilt==r
    copy=tmp_path/'relocated';copy.mkdir();new_bindings={}
    for sid,b in bindings.items():
        dest=copy/sid;shutil.copytree(b['path'],dest)
        comps={}
        for cid,path in b['components'].items():
            target=copy/(sid+'-'+cid);shutil.copytree(path,target);comps[cid]=target
        new_bindings[sid]={'path':dest,'components':comps}
    shutil.copytree(tmp_path/'plan',copy/'plan')
    with CurriculumBatches(copy/'plan',new_bindings,tok,r['dataset_hash']) as d:
        assert d.counts(len(d))==(r['processed_positions'],r['supervised_positions'])
        assert str(tmp_path) not in (copy/'plan/manifest.json').read_text()
    with open_plan(tmp_path,bindings,tok) as data:
        c=Config(vocab_size=data.vocab_size);a=CurriculumTrainer(c,initialize(c),data);a.update();a.save(tmp_path/'old')
        with pytest.raises(ValueError,match='Recipe'):CurriculumTrainer(c,initialize(c),data,recipe=replace(base,eps=1e-6))
    stages[1]['schedule']['lr']=.0003
    build_curriculum(stages,tok,tmp_path/'changed',recipe=base,family_processed_cap=100000)
    with CurriculumBatches(tmp_path/'changed',bindings,tok) as changed:
        with pytest.raises(ValueError,match='mismatch'):CurriculumTrainer.resume(tmp_path/'old',changed)


def test_interrupted_plan_publication_and_live_component_mutation_fail_closed(tmp_path,monkeypatch):
    stages,bindings,tok,base,r=fixture(tmp_path)
    import slm.data.curriculum as module
    def fail(*args):raise OSError('synthetic rename interruption')
    with monkeypatch.context() as context:
        context.setattr(module.os,'rename',fail)
        with pytest.raises(OSError):build_curriculum(stages,tok,tmp_path/'bad',recipe=base,family_processed_cap=100000)
    assert not (tmp_path/'bad').exists() and not list(tmp_path.glob('.curriculum-*'))
    with open_plan(tmp_path,bindings,tok) as data:
        with (bindings['conversation']['path']/'report.json').open('a') as f:f.write(' ')
        with pytest.raises(ValueError,match='changed'):data.counts(0)


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_next_stage_failure_never_commits_or_resets_previous_state(tmp_path,monkeypatch,backend):
    if backend=='mlx':pytest.importorskip('mlx.core')
    stages,bindings,tok,base,r=fixture(tmp_path)
    with open_plan(tmp_path,bindings,tok) as data:
        c=Config(vocab_size=data.vocab_size);a=CurriculumTrainer(c,initialize(c),data,backend)
        while a.cursor<data.inventory.ends[0]:a.update()
        a.save(tmp_path/'boundary');b=CurriculumTrainer.resume(tmp_path/'boundary',data,backend)
        original=a.impl.value_and_grad;calls=0
        def failed(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('synthetic second next-stage microbatch failure')
            return original(*args,**kwargs)
        with monkeypatch.context() as context:
            context.setattr(a.impl,'value_and_grad',failed)
            with pytest.raises(OSError):a.update()
        compare(a,b,True);assert data.progress(a.cursor)['next_stage']=='conversation'
        assert a.update()==b.update();compare(a,b,True)
        # Receipt generation also occurs before logical progress is committed.
        with monkeypatch.context() as context:
            context.setattr(a,'_update_result',lambda *args: (_ for _ in ()).throw(OSError('receipt failure')))
            with pytest.raises(OSError):a.update()
        compare(a,b,True)
        assert a.update()==b.update();compare(a,b,True)


def test_curriculum_initial_checkpoint_and_mlx_cpu_stage_transition(tmp_path):
    pytest.importorskip('mlx.core')
    stages,bindings,tok,base,r=fixture(tmp_path)
    with open_plan(tmp_path,bindings,tok) as data:
        c=Config(vocab_size=data.vocab_size);a=CurriculumTrainer(c,initialize(c),data,'mlx')
        a.save(tmp_path/'zero');zero=CurriculumTrainer.resume(tmp_path/'zero',data,'mlx');compare(a,zero,True)
        while a.cursor<data.inventory.ends[0]:a.update()
        a.save(tmp_path/'mlx');moved=CurriculumTrainer.resume(tmp_path/'mlx',data,'torch');compare(a,moved,True)
        for _ in range(2):a.update();moved.update();compare(a,moved)
        moved.save(tmp_path/'cpu');returned=CurriculumTrainer.resume(tmp_path/'cpu',data,'mlx');compare(moved,returned,True)
        a.update();returned.update();compare(a,returned)


def test_cli_config_paths_and_tokenizer_identity(tmp_path):
    stages,bindings,tok,base,r=fixture(tmp_path)
    for s in stages:
        s['path']=str(s['path'].relative_to(tmp_path))
        s['components']={k:str(v.relative_to(tmp_path)) for k,v in s['components'].items()}
    config={'stages':stages,'recipe':asdict(base),'family_processed_cap':100000}
    (tmp_path/'config.json').write_text(json.dumps(config))
    result=subprocess.run([sys.executable,'-m','slm.data.curriculum','--config',str(tmp_path/'config.json'),
        '--tokenizer',str(tok),'--output',str(tmp_path/'cli')],check=True,capture_output=True,text=True)
    assert json.loads(result.stdout)==r
    with CurriculumBatches(tmp_path/'cli',bindings,tok,r['dataset_hash']) as data:
        c=Config(vocab_size=data.vocab_size)
        with pytest.raises(ValueError,match='tokenizer'):CurriculumTrainer(c,initialize(c),data,tokenizer_hash='wrong')
        with pytest.raises(ValueError,match='boundary'):data.progress(1)
        with pytest.raises(ValueError,match='crosses'):data.rate(0,1)


def test_replay_across_stages_is_explicit_and_has_one_global_processed_cap(tmp_path):
    stages,bindings,tok,base,r=fixture(tmp_path)
    repeated={**stages[0],'id':'replay','schedule':dict(stages[0]['schedule'])}
    selected=[stages[0],repeated]
    one=r['stages'][0]['processed_positions']
    # Reusing a mixture is allowed as explicit replay, but its family exposure adds.
    with MixtureBatches(stages[0]['path'],stages[0]['components'],tok) as data:
        from slm.data.mixture import account
        inv=data.inventory
        _,counts,_,_,_=account(inv,data.manifest['components'],data.index,'foundation',100000)
        from collections import Counter
        groups=Counter()
        for (ci,ri),v in counts.items():groups[inv.records[ci][ri]['split_group']]+=v['processed']
        cap=max(groups.values())
    with pytest.raises(ValueError,match='Cross-stage family'):
        build_curriculum(selected,tok,tmp_path/'overexposed',recipe=base,family_processed_cap=cap)
    rr=build_curriculum(selected,tok,tmp_path/'replay',recipe=base,family_processed_cap=2*cap)
    assert rr['processed_positions']==2*one
    assert rr['content_fingerprints_in_multiple_stages']==rr['distinct_content_fingerprints']>0


@pytest.mark.parametrize('defect',['transition','clock','cap','hash','report'])
def test_rehashed_plan_still_requires_supported_policy_and_actual_stage_inventory(tmp_path,defect):
    stages,bindings,tok,base,r=fixture(tmp_path)
    p=tmp_path/'plan/manifest.json';m=json.loads(p.read_text())
    if defect=='transition':m['transition']='reset-optimizer'
    elif defect=='clock':m['lr_clock']='global'
    elif defect=='cap':m['family_processed_cap']=1
    elif defect=='hash':m['stages'][1]['dataset_hash']='0'*64
    else:
        from slm.data.schema import digest
        rp=tmp_path/'plan/report.json';report=json.loads(rp.read_text());report['processed_positions']+=1;rp.write_text(json.dumps(report))
        m['report_hash']=digest(report);m['files']['report.json']=sha(rp)
    p.write_text(json.dumps(m))
    with pytest.raises(ValueError):open_plan(tmp_path,bindings,tok)


def test_curriculum_checkpoint_rejects_missing_optimizer_after_global_updates(tmp_path):
    from safetensors.numpy import save_file
    stages,bindings,tok,base,r=fixture(tmp_path)
    with open_plan(tmp_path,bindings,tok) as data:
        c=Config(vocab_size=data.vocab_size);a=CurriculumTrainer(c,initialize(c),data)
        a.update();a.save(tmp_path/'state')
        save_file({},str(tmp_path/'state/optimizer.safetensors'))
        p=tmp_path/'state/manifest.json';m=json.loads(p.read_text());m['optimizer.safetensors']=sha(tmp_path/'state/optimizer.safetensors');p.write_text(json.dumps(m))
        with pytest.raises(ValueError,match='Incomplete optimizer'):CurriculumTrainer.resume(tmp_path/'state',data)


@pytest.mark.skipif(not __import__('torch').cuda.is_available(),reason='NVIDIA CUDA device unavailable')
def test_curriculum_cuda_state_transfer_and_two_stage_cpu_comparison(tmp_path):
    stages,bindings,tok,base,r=fixture(tmp_path)
    with open_plan(tmp_path,bindings,tok) as data:
        c=Config(vocab_size=data.vocab_size);a=CurriculumTrainer(c,initialize(c),data)
        a.update();a.save(tmp_path/'cpu')
        b=CurriculumTrainer.resume(tmp_path/'cpu',data,device='cuda');compare(a,b,True)
        while a.cursor<len(data):a.update();b.update();compare(a,b)


def test_stage_local_warmup_and_cooldown_have_independent_analytic_clock(tmp_path):
    stages,bindings,tok,base,r=fixture(tmp_path)
    with open_plan(tmp_path,bindings,tok) as data:
        cursor=0;seen=[]
        while cursor<len(data):
            recipe,end,i,local=data.context(cursor);d=data.inventory.data[i]
            begin=0 if i==0 else data.inventory.ends[i-1]
            after=d.counts(end-begin)[0];total=d.counts(len(d))[0]
            spec=stages[i]['schedule'];expected=spec['lr']*min(1,after/spec['warmup_tokens'])
            if after>total-64:expected*=.1+.9*(total-after)/64
            assert data.rate(cursor,end)==pytest.approx(expected,abs=1e-18)
            if i==1 and not local:
                assert after<spec['warmup_tokens'] and expected<spec['lr']
                # The global count already exceeds warmup; it must not be used.
                assert data.counts(end)[0]>spec['warmup_tokens']
            if end==data.inventory.ends[i]:assert expected==pytest.approx(spec['lr']*.1)
            seen.append((i,end));cursor=end
        assert {i for i,_ in seen}=={0,1}


def test_native_default_recipe_curriculum_cpu_resume_remains_supported(tmp_path):
    stages,bindings,tok,base,r=fixture(tmp_path)
    native=replace(base,embedding_implementation='native-gather-v1')
    report=build_curriculum(stages,tok,tmp_path/'native',recipe=native,family_processed_cap=100000)
    with CurriculumBatches(tmp_path/'native',bindings,tok,report['dataset_hash']) as data:
        c=Config(vocab_size=data.vocab_size);a=CurriculumTrainer(c,initialize(c),data)
        a.update();a.save(tmp_path/'state');b=CurriculumTrainer.resume(tmp_path/'state',data)
        while a.cursor<len(data):assert a.update()==b.update();compare(a,b,True)
        assert a.recipe.embedding_implementation=='native-gather-v1'
