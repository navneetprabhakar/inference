"""Raw inference correctness checks, not conversation quality tests."""
import json
import numpy as np
import pytest
pytest.importorskip('tokenizers')
from slm.common.config import Config,initialize
from slm.common.checkpoint import save
from slm.common.tokenizer import train_core,STRUCTURAL
from slm.data.tokenized import sha
from slm.inference.greedy import GreedyModel,prompt_ids


def model(tmp_path,backend='torch',repeat=False):
    tok=train_core(['Hello user assistant 42. Professional meeting Friday room Q17.']*5,512)
    tok.save(tmp_path/'tokenizer',{'scope':'Synthetic inference test'})
    c=Config(vocab_size=tok.vocab_size,max_seq_len=512);weights=initialize(c,119)
    if repeat:
        for k in weights:
            if weights[k].ndim==2:weights[k].fill(0)
        weights['embedding'][STRUCTURAL['assistant']]=.01;weights['embedding'][10]=.1
    save(tmp_path/'model',c,weights)
    return GreedyModel(tmp_path/'model',tmp_path/'tokenizer',backend,expected_tokenizer_hash=sha(tmp_path/'tokenizer/manifest.json'))


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_assistant_prefix_and_cached_greedy_match_full_recompute(tmp_path,backend):
    if backend=='mlx':pytest.importorskip('mlx.core')
    m=model(tmp_path,backend,repeat=True);messages=[{'role':'user','content':'Hello assistant'}]
    prefix=prompt_ids(m.tokenizer,messages)
    x,_,_=m.tokenizer.serialize([*messages,{'role':'assistant','content':'42'}])
    assert x[:len(prefix)]==prefix and prefix[-1]==STRUCTURAL['assistant']
    result=m.generate(messages,8);ids=prefix.copy();expected=[]
    with m.context():
        for _ in range(8):
            logits,_,_=m.impl.forward(m.params,m.config,m.array([ids]));token=m.argmax(logits[0,-1]);expected.append(token)
            if token<10:break
            ids.append(token)
    assert result['token_ids']==expected==[10]*8 and result['generated_tokens']==8
    assert result['seconds']>=result['ttft_seconds']>=0
    if backend=='torch':assert all(p.grad is None for p in m.params.values())


@pytest.mark.parametrize('ending',['eos','message_end','invalid_structural','length'])
def test_stops_are_explicit_and_structural_tokens_never_decode_as_content(tmp_path,monkeypatch,ending):
    import torch
    m=model(tmp_path);content=m.tokenizer.encode('42');stop={'eos':1,'message_end':3,'invalid_structural':4}.get(ending)
    sequence=content+[stop] if stop is not None else [content[0]]*8
    called=0;original=m.impl.forward
    def controlled(*args,**kwargs):
        nonlocal called
        logits,cache,traces=original(*args,**kwargs);logits=torch.full_like(logits,-10);logits[0,-1,sequence[called]]=10;called+=1
        return logits,cache,traces
    monkeypatch.setattr(m.impl,'forward',controlled)
    out=m.generate([{'role':'user','content':'Hello'}],8)
    assert out['stop_reason']==ending and out['token_ids']==sequence
    if stop is not None:assert out['text']=='42'
    assert out['content_tokens']==len(sequence)-(stop is not None)


def test_reference_content_loss_matches_independent_fp64_cross_entropy_and_no_gradients(tmp_path):
    import torch
    m=model(tmp_path);messages=[{'role':'user','content':'Hello'},{'role':'assistant','content':'Professional meeting'},{'role':'user','content':'Room?'}];reference='42'
    score=m.reference_loss(messages,reference)
    x,y,mask=m.tokenizer.serialize([*messages,{'role':'assistant','content':reference}])
    with torch.no_grad():
        logits=m.impl.forward(m.params,m.config,m.array([x]))[0].double()
        losses=torch.nn.functional.cross_entropy(logits[0],m.array(y),reduction='none')
    supervised=np.asarray(mask,dtype=bool)&(np.asarray(y)>=10)&(np.arange(len(y))>=len(prompt_ids(m.tokenizer,messages))-1)
    assert score['nll_sum']==pytest.approx(float(losses[torch.tensor(supervised)].sum()),abs=1e-12)
    assert score['content_targets']==int(supervised.sum()) and score['utf8_bytes']==len(reference.encode())
    assert all(p.grad is None for p in m.params.values())


def test_invalid_budget_binding_and_prompt_never_silently_truncate(tmp_path,monkeypatch):
    m=model(tmp_path)
    with pytest.raises(ValueError,match='binding'):GreedyModel(tmp_path/'model',tmp_path/'tokenizer',expected_tokenizer_hash='0'*64)
    for budget in (0,513,True):
        with pytest.raises(ValueError,match='budget'):m.generate([{'role':'user','content':'Hello'}],budget)
    with pytest.raises(ValueError,match='truncation'):m.generate([{'role':'user','content':'x '*1000}],8)
    with pytest.raises(ValueError,match='user/tool'):m.generate([{'role':'assistant','content':'Hello'}],8)
    original=m.impl.forward
    def nan(*args,**kwargs):
        logits,cache,traces=original(*args,**kwargs);return logits*float('nan'),cache,traces
    monkeypatch.setattr(m.impl,'forward',nan)
    with pytest.raises(FloatingPointError):m.generate([{'role':'user','content':'Hello'}],8)


def test_mlx_cpu_raw_greedy_and_reference_scores_share_the_same_checkpoint(tmp_path):
    pytest.importorskip('mlx.core')
    a=model(tmp_path,repeat=True)
    b=GreedyModel(tmp_path/'model',tmp_path/'tokenizer','mlx',expected_tokenizer_hash=a.tokenizer_hash)
    messages=[{'role':'user','content':'Hello user assistant'}]
    ra=a.generate(messages,8);rb=b.generate(messages,8)
    assert ra['token_ids']==rb['token_ids']==[10]*8 and ra['text']==rb['text']
    assert a.reference_loss(messages,'42')['nll_sum']==pytest.approx(b.reference_loss(messages,'42')['nll_sum'],abs=1e-5,rel=1e-4)


@pytest.mark.skipif(not __import__('torch').cuda.is_available(),reason='NVIDIA CUDA device unavailable')
def test_cuda_cpu_raw_greedy_and_reference_score_match(tmp_path):
    a=model(tmp_path,repeat=True)
    b=GreedyModel(tmp_path/'model',tmp_path/'tokenizer',device='cuda',expected_tokenizer_hash=a.tokenizer_hash)
    messages=[{'role':'user','content':'Hello user assistant'}]
    assert a.generate(messages,8)['token_ids']==b.generate(messages,8)['token_ids']==[10]*8
    assert a.reference_loss(messages,'42')['nll_sum']==pytest.approx(b.reference_loss(messages,'42')['nll_sum'],abs=1e-5,rel=1e-4)


def test_cli_run_emits_actual_bound_model_output(tmp_path):
    import subprocess
    import sys
    from slm.eval.cases import candidate_suite
    from slm.eval.conversation import check_results
    m=model(tmp_path,repeat=True);suite=candidate_suite();suite['cases']=suite['cases'][:1]
    path=tmp_path/'suite.json';path.write_text(json.dumps(suite));out=tmp_path/'results.json'
    subprocess.run([sys.executable,'-m','slm.eval.language','run','--suite',str(path),'--model',str(tmp_path/'model'),
        '--tokenizer',str(tmp_path/'tokenizer'),'--tokenizer-hash',m.tokenizer_hash,'--max-new-tokens','4','--output',str(out)],check=True,capture_output=True)
    result=json.loads(out.read_text());check_results(suite,result)
    assert result['records'][0]['response']['token_ids']==[10]*4
    assert result['identity']['model_manifest_sha256']==sha(tmp_path/'model/manifest.json')
