import numpy as np
import pytest
from slm.common.tokenizer import STRUCTURAL
from slm.restart.generation_execution import sample,generate,copying

class Tokens:
    vocab_size=16
    def encode(self,text):return [10]*len(text.split())
    def decode(self,ids):return ' '.join('word' for i in ids)


def logits_for(token):
    def logits(x,p):
        a=np.full((*x.shape,16),-100.,np.float32);a[:,:,-1]=0;a[:,:,token]=100
        return a
    return logits


def test_sampling_seed_and_nucleus_crossing_token():
    scores=np.log([.61,.3,.09])*.7
    a=np.random.default_rng(42);b=np.random.default_rng(42)
    left=[sample(scores,a) for _ in range(100)]
    assert left==[sample(scores,b) for _ in range(100)]
    assert set(left)=={0,1}


def test_eos_not_suppressed_or_resampled():
    r=generate([10],Tokens(),logits=logits_for(STRUCTURAL['eos']),heartbeat=lambda:None,seed=42)
    assert r['stop_reason']=='eos' and r['generated_token_ids']==[STRUCTURAL['eos']] and r['text']==''


def test_structural_failure_is_retained():
    r=generate([10],Tokens(),logits=logits_for(STRUCTURAL['tool']),heartbeat=lambda:None,seed=42)
    assert r['stop_reason']=='invalid_structural_token' and r['generated_token_ids']==[STRUCTURAL['tool']]


def test_exact_word_stop_without_output_repair():
    r=generate([10],Tokens(),logits=logits_for(10),heartbeat=lambda:None,seed=42)
    assert r['stop_reason']=='word_limit' and len(r['text'].split())==120


def test_context_exhaustion_never_truncates_prefix():
    seen=[]
    def logits(x,p):seen.append(x.shape[1]);return logits_for(10)(x,p)
    r=generate([10]*510,Tokens(),logits=logits,heartbeat=lambda:None,seed=42)
    assert seen==[511,512] and r['stop_reason']=='context_limit' and len(r['generated_token_ids'])==2


def test_greedy_copy_exact_64_and_denominator():
    item={'prefix':' '.join(['word']*64),'prefix_token_ids':[10]*64,'expected_next_64_token_ids':[10]*64}
    pairs=[dict(pair_id=str(i),training=item,heldout=item) for i in range(100)]
    r=copying(pairs,Tokens(),logits=logits_for(10),heartbeat=lambda:None)
    assert r['metrics']['training_copies']==100 and r['metrics']['heldout_copies']==100
    assert not r['metrics']['final_gate_pass']
    assert len(r['outputs'])==100


@pytest.mark.parametrize('bad',[[],[0],[16],[True],[10]*512])
def test_bad_prefix_refused(bad):
    with pytest.raises(ValueError):generate(bad,Tokens(),logits=logits_for(10),heartbeat=lambda:None,seed=42)


def test_nonfinite_logits_terminal():
    with pytest.raises(ValueError):generate([10],Tokens(),heartbeat=lambda:None,seed=42,
        logits=lambda x,p:np.full((*x.shape,16),np.nan,np.float32))
