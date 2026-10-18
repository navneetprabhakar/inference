"""Synthetic numerical checks; no public data or teacher output is trained."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
import torch
from slm.common.config import Config,initialize
from slm.common.training import Batches,Recipe,Trainer,accumulation_policy
from slm.backends import torch_backend as tb
from test_resume import compare


def fixtures(variable=False,count=7):
    rng=np.random.default_rng(817)
    items=[]
    for i in range(count):
        n=(4+i%5) if variable else 8
        x=rng.integers(0,64,(1,n));y=rng.integers(0,64,(1,n))
        mask=np.zeros((1,n),np.float32);mask[:,:1+(i*3) % n]=1
        items.append((x,y,mask))
    return Batches(items,64)


def backend_ready(backend):
    if backend=='mlx':pytest.importorskip('mlx.core')


def tensors(trainer):
    return {**trainer.impl.export(trainer.params),
        **{f'{i}:{k}':a for i in range(2) for k,a in trainer.impl.export({k:v[i] for k,v in trainer.moments.items()}).items()}}


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_accumulation_matches_native_full_batch_loss_gradients_clipping_and_adamw(backend,monkeypatch):
    backend_ready(backend)
    c=Config();data=fixtures();recipe=Recipe(accumulation_steps=3,clip=.01,warmup_tokens=40)
    trainer=Trainer(c,initialize(c),data,backend,recipe=recipe)
    p=tb.load(c,initialize(c))
    groups=[{'params':[w for k,w in p.items() if w.ndim==2 and k!='embedding'],'weight_decay':recipe.decay},
            {'params':[w for k,w in p.items() if w.ndim!=2 or k=='embedding'],'weight_decay':0.}]
    optimizer=torch.optim.AdamW(groups,lr=recipe.lr,betas=(recipe.beta1,recipe.beta2),eps=recipe.eps,foreach=False,fused=False)
    captured=[];adamw=trainer.impl.adamw
    def capture(params,grads,state,step,**settings):
        captured.append(trainer.impl.export(grads))
        return adamw(params,grads,state,step,**settings)
    monkeypatch.setattr(trainer.impl,'adamw',capture)
    consumed=0
    for start in range(0,len(data.items),3):
        batch=data.items[start:start+3]
        x,y,mask=(torch.tensor(np.concatenate([v[i] for v in batch],axis=0)) for i in range(3))
        optimizer.zero_grad(set_to_none=True)
        logits=tb.forward(p,c,x)[0]
        per=torch.nn.functional.cross_entropy(logits.reshape(-1,c.vocab_size),y.reshape(-1),reduction='none').reshape(y.shape)
        loss=(per*mask).sum()/mask.sum();loss.backward()
        before_clip={k:w.grad.detach().numpy().copy() for k,w in p.items()}
        assert np.sqrt(sum(np.square(g).sum() for g in before_clip.values()))>recipe.clip
        torch.nn.utils.clip_grad_norm_(list(p.values()),recipe.clip,foreach=False)
        consumed+=x.numel();rate=recipe.rate(consumed)
        for group in optimizer.param_groups:group['lr']=rate
        optimizer.step()
        result=trainer.update()
        assert result['microbatches']==len(batch) and result['tokens']==consumed
        assert result['lr']==rate and len(captured)==trainer.step
        np.testing.assert_allclose(result['loss'],float(loss.detach()),atol=1e-5,rtol=1e-4)
        for k,w in p.items():
            np.testing.assert_allclose(captured[-1][k],before_clip[k],atol=1e-6,rtol=1e-4)
            np.testing.assert_allclose(trainer.impl.export(trainer.params)[k],w.detach().numpy(),atol=1e-5,rtol=1e-4)
            for i,slot in enumerate(('exp_avg','exp_avg_sq')):
                actual=trainer.impl.export({k:trainer.moments[k][i]})[k]
                np.testing.assert_allclose(actual,optimizer.state[w][slot].numpy(),atol=1e-6,rtol=1e-4)
    assert trainer.cursor==7 and trainer.step==3
    assert data.counts(7)==(trainer.tokens,trainer.supervised_tokens)
    with pytest.raises(StopIteration):trainer.update()


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_accumulated_same_backend_resume_is_exact_for_own_trajectory_and_short_tail(tmp_path,backend):
    backend_ready(backend)
    c=Config();data=fixtures(variable=True,count=10)
    a=Trainer(c,initialize(c),data,backend,recipe=Recipe(accumulation_steps=3))
    a.update();a.save(tmp_path/'saved')
    state=json.loads((tmp_path/'saved/state.json').read_text())
    assert state['version']==2 and state['accumulation']==accumulation_policy(a.recipe)
    b=Trainer.resume(tmp_path/'saved',data,backend);compare(a,b,True)
    for n in (3,3,1):
        ra=a.update();rb=b.update()
        assert ra==rb and ra['microbatches']==n
        compare(a,b,True)
    a.save(tmp_path/'tail');compare(a,Trainer.resume(tmp_path/'tail',data,backend),True)
    assert a.cursor==10 and a.step==4 and not a._in_update


@pytest.mark.parametrize('backend',['torch','mlx'])
@pytest.mark.parametrize('failure',['io','loss','gradient','optimizer','interrupt'])
def test_failed_group_never_commits_partial_progress_and_retry_starts_at_boundary(tmp_path,monkeypatch,failure,backend):
    backend_ready(backend)
    c=Config();data=fixtures();recipe=Recipe(accumulation_steps=3)
    a=Trainer(c,initialize(c),data,backend,recipe=recipe);a.update();a.save(tmp_path/'before')
    snapshot=tensors(a);counters=(a.step,a.cursor,a.tokens,a.supervised_tokens)
    grad=a.impl.value_and_grad;adam=a.impl.adamw;calls=0
    def bad_grad(*args,**kwargs):
        nonlocal calls
        calls+=1
        value,grads=grad(*args,**kwargs)
        if calls==2:
            if failure=='io':raise OSError('synthetic second-microbatch read failure')
            if failure=='interrupt':raise KeyboardInterrupt('synthetic interrupt')
            if failure=='loss':return value*a.array(np.array(float('nan'),dtype=np.float32)),grads
            if failure=='gradient':return value,{**grads,'embedding':grads['embedding']*a.array(np.array(float('inf'),dtype=np.float32))}
        return value,grads
    def bad_adam(*args,**kwargs):raise OSError('synthetic optimizer failure')
    monkeypatch.setattr(a.impl,'value_and_grad',bad_grad)
    if failure=='optimizer':monkeypatch.setattr(a.impl,'adamw',bad_adam)
    with pytest.raises((OSError,FloatingPointError,KeyboardInterrupt)):a.update()
    assert counters==(a.step,a.cursor,a.tokens,a.supervised_tokens) and not a._in_update
    for k,value in tensors(a).items():np.testing.assert_array_equal(value,snapshot[k])
    a.save(tmp_path/'after-failure')
    monkeypatch.setattr(a.impl,'value_and_grad',grad);monkeypatch.setattr(a.impl,'adamw',adam)
    b=Trainer.resume(tmp_path/'before',data,backend);a.update();b.update();compare(a,b,True)


def test_mid_update_checkpoint_and_reentrant_update_are_refused(tmp_path,monkeypatch):
    a=Trainer(Config(),initialize(Config()),fixtures(),recipe=Recipe(accumulation_steps=3))
    grad=a.impl.value_and_grad;calls=0
    def inspect(*args,**kwargs):
        nonlocal calls
        calls+=1
        with pytest.raises(RuntimeError,match='boundary'):a.save(tmp_path/'partial')
        with pytest.raises(RuntimeError,match='already in progress'):a.update()
        return grad(*args,**kwargs)
    monkeypatch.setattr(a.impl,'value_and_grad',inspect)
    a.update();assert calls==3 and not (tmp_path/'partial').exists()
    assert not list(tmp_path.glob('.training-*'))
    a.save(tmp_path/'complete')


def rewrite_state(path,mutate):
    state=json.loads((path/'state.json').read_text());mutate(state)
    (path/'state.json').write_text(json.dumps(state))
    manifest=json.loads((path/'manifest.json').read_text())
    manifest['state.json']=hashlib.sha256((path/'state.json').read_bytes()).hexdigest()
    (path/'manifest.json').write_text(json.dumps(manifest))


@pytest.mark.parametrize('defect',['pending','normalization','clipping','tail','policy_count','step','cursor','tokens','version','legacy_accumulation'])
def test_rehashed_inconsistent_checkpoint_policy_and_counters_are_refused(tmp_path,defect):
    data=fixtures();a=Trainer(Config(),initialize(Config()),data,recipe=Recipe(accumulation_steps=3))
    a.update();a.save(tmp_path/'state')
    def bad(state):
        if defect=='pending':state['accumulation']['pending_microbatches']=1
        elif defect in ('normalization','clipping','tail'):state['accumulation'][defect]='different'
        elif defect=='policy_count':state['accumulation']['microbatches_per_update']=4
        elif defect=='step':state['step']+=1
        elif defect=='cursor':
            state['cursor']=1;state['tokens'],state['supervised_tokens']=data.counts(1)
        elif defect=='tokens':state['tokens']+=1
        elif defect=='version':state['version']=True
        elif defect=='legacy_accumulation':state['version']=1
    rewrite_state(tmp_path/'state',bad)
    with pytest.raises(ValueError):Trainer.resume(tmp_path/'state',data)


def test_legacy_v1_checkpoint_without_accumulation_recipe_loads_and_preserves_default(tmp_path):
    c=Config();data=fixtures();a=Trainer(c,initialize(c),data);a.update();a.save(tmp_path/'legacy')
    def legacy(state):
        state['version']=1;state.pop('accumulation');state['recipe'].pop('accumulation_steps')
        state['reproduction'].pop('trainer_sha256')
    rewrite_state(tmp_path/'legacy',legacy)
    b=Trainer.resume(tmp_path/'legacy',data);assert b.recipe.accumulation_steps==1
    assert a.update()==b.update();compare(a,b,True)
    b.save(tmp_path/'upgraded');assert json.loads((tmp_path/'upgraded/state.json').read_text())['version']==2


def test_invalid_accumulation_settings_and_tampered_runtime_boundary_cannot_save(tmp_path):
    for value in (0,-1,1.5,True,1025,'3'):
        with pytest.raises(ValueError):Recipe(accumulation_steps=value)
    a=Trainer(Config(),initialize(Config()),fixtures(),recipe=Recipe(accumulation_steps=3))
    a.cursor=1;a.step=1;a.tokens,a.supervised_tokens=a.batches.counts(1)
    with pytest.raises(ValueError,match='boundary'):a.save(tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_unequal_mean_or_microbatch_clipping_would_fail_the_native_gradient_reference():
    c=Config();data=fixtures();p=tb.load(c,initialize(c));grads=[];counts=[]
    for x,y,m in data.items[:3]:
        _,g=tb.value_and_grad(p,c,torch.tensor(x),torch.tensor(y),torch.tensor(m))
        grads.append(g['embedding'].detach().numpy());counts.append(int(m.sum()))
    weighted=sum(g*n for g,n in zip(grads,counts))/sum(counts)
    naive=sum(grads)/3
    assert len(set(counts))>1 and np.max(np.abs(weighted-naive))>1e-3


def test_accumulated_mlx_cpu_roundtrip_keeps_update_and_data_counters(tmp_path):
    backend_ready('mlx');c=Config();data=fixtures(variable=True,count=19);recipe=Recipe(accumulation_steps=3)
    a=Trainer(c,initialize(c),data,'mlx',recipe=recipe)
    for _ in range(2):a.update()
    a.save(tmp_path/'mlx');b=Trainer.resume(tmp_path/'mlx',data)
    for _ in range(2):a.update();b.update();compare(a,b)
    b.save(tmp_path/'cpu');r=Trainer.resume(tmp_path/'cpu',data,'mlx')
    while a.cursor<len(data.items):a.update();r.update();compare(a,r)
    assert a.step==7 and a.cursor==19


def test_accumulated_shard_reader_crosses_files_and_resumes_from_microbatch_cursor(tmp_path):
    pytest.importorskip('tokenizers')
    from test_tokenized import setup
    from slm.data.tokenized import ShardBatches
    from slm.common.tokenizer import BPE
    _,tok,_=setup(tmp_path,'foundation',context=17,shard=35)
    c=Config(vocab_size=BPE.load(tok).vocab_size);recipe=Recipe(accumulation_steps=4)
    with ShardBatches(tmp_path/'tokens',tok) as data:
        assert len(data.manifest['shards'])>1
        a=Trainer(c,initialize(c),data,recipe=recipe,tokenizer_hash=data.tokenizer_hash)
        a.update();a.save(tmp_path/'shard-state')
        with ShardBatches(tmp_path/'tokens',tok) as fresh:
            b=Trainer.resume(tmp_path/'shard-state',fresh,tokenizer_hash=fresh.tokenizer_hash)
            while a.cursor<len(data):
                assert a.update()==b.update();compare(a,b,True)
            assert (a.tokens,a.supervised_tokens)==data.counts(len(data))


@pytest.mark.skipif(not torch.cuda.is_available(),reason='NVIDIA CUDA device unavailable')
def test_accumulated_cuda_matches_cpu_and_resumes(tmp_path):
    c=Config();data=fixtures(variable=True,count=10);recipe=Recipe(accumulation_steps=3)
    a=Trainer(c,initialize(c),data,recipe=recipe);b=Trainer(c,initialize(c),data,device='cuda',recipe=recipe)
    a.update();b.update();compare(a,b)
    b.save(tmp_path/'cuda');r=Trainer.resume(tmp_path/'cuda',data)
    while a.cursor<len(data.items):a.update();r.update();compare(a,r)


def test_all_short_single_update_tail_and_initial_checkpoint(tmp_path):
    data=fixtures(variable=True);c=Config();a=Trainer(c,initialize(c),data,recipe=Recipe(accumulation_steps=1024))
    a.save(tmp_path/'zero');b=Trainer.resume(tmp_path/'zero',data)
    assert a.update()==b.update();compare(a,b,True)
    assert a.step==1 and a.cursor==len(data.items)
    a.save(tmp_path/'end');compare(a,Trainer.resume(tmp_path/'end',data),True)
    with pytest.raises(StopIteration):a.update()


def test_portability_bundle_uses_optimizer_probe_steps_with_multiple_microbatches(tmp_path):
    backend_ready('mlx')
    from slm.eval.portability import create,verify,get_batches
    recipe=Recipe(accumulation_steps=2)
    create(tmp_path/'bundle','mlx',recipe=recipe)
    assert len(get_batches(tmp_path/'bundle').items)==12
    first=verify(tmp_path/'bundle',tmp_path/'cpu','torch')
    assert first['passed'] and first['final_step']==4
    returned=verify(tmp_path/'bundle',tmp_path/'mlx','mlx',resume=tmp_path/'cpu/checkpoint')
    assert returned['passed'] and returned['final_step']==6
    state=json.loads((tmp_path/'mlx/checkpoint/state.json').read_text())
    assert state['cursor']==12 and state['step']==6


def test_overfit_and_benchmark_count_optimizer_updates_and_repeated_microbatch_exposure(tmp_path):
    from slm.eval.overfit import run as overfit
    from slm.eval.benchmark import run as benchmark
    c=Config(vocab_size=16,max_seq_len=8)
    r=overfit(c,tmp_path/'overfit','torch',updates=2,recipe=Recipe(accumulation_steps=3))
    assert len(r['history'])==2 and r['history'][-1]['cursor']==6
    assert r['processed_tokens']==96 and r['supervised_tokens']==60 and r['repeated_exposures']==6
    assert json.loads((tmp_path/'overfit/fixture.json').read_text())['batch_count']==6
    b=benchmark(c,tmp_path/'benchmark.json','torch','cpu',length=8,warmup=1,steps=2,accumulation_steps=3)
    assert b['measured_token_positions']==48 and b['history'][-1]['tokens']==72
    assert b['history'][-1]['step']==3 and b['history'][-1]['cursor']==9
    assert b['microbatches_per_update']==3 and b['effective_positions_per_update']==24


def test_bounded_mechanics_report_counts_actual_replay_work_and_removes_checkpoint(tmp_path):
    from slm.eval.accumulation import run
    report=run(Config(),tmp_path/'mechanics.json','torch')
    assert report['passed'] and report['synthetic_only']
    assert report['reference_optimizer_updates']==3 and report['reference_consumed_microbatches']==5
    assert report['reference_processed_positions']==92 and report['reference_supervised_positions']==60
    assert report['total_executed_updates']==5 and report['total_executed_positions']==136
    assert len(report['own_trajectory_checks'])==3 and all(v['exact'] for v in report['own_trajectory_checks'])
    assert report['temporary_checkpoint_removed'] and report['checkpoint_bytes']>3*Config().parameter_count*4
    with pytest.raises(FileExistsError):run(Config(),tmp_path/'mechanics.json','torch')
