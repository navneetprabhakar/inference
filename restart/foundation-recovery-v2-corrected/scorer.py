"""Joint text encoding, causal next-token suffix-only scores and fixed controls."""
import numpy as np

def continuation(tok,prefix,option):
    prefix_ids=tok.encode(prefix,bos=True,eos=False)
    joint=tok.encode(prefix+option,bos=True,eos=False)
    assert joint[:len(prefix_ids)]==prefix_ids,'PREFIX_TOKENIZATION_UNSTABLE'
    assert len(joint)>len(prefix_ids) and len(joint)<=256
    return joint,len(prefix_ids)
def suffix_score(logits,joint,prefix_length):
    # row k predicts token k+1; first suffix token is at prefix_length.
    x=np.asarray(logits,dtype=np.float64)[prefix_length-1:len(joint)-1]
    targets=np.asarray(joint[prefix_length:],dtype=np.int64)
    assert len(x)==len(targets)>0
    m=x.max(axis=-1,keepdims=True)
    logp=x-m-np.log(np.exp(x-m).sum(axis=-1,keepdims=True))
    return float(logp[np.arange(len(targets)),targets].sum())
def split_passage(prefix):
    first,question=prefix.rsplit('. ',1)
    return first+'. ',question

def controls(cases):
    out=[]
    for i,c in enumerate(cases):
        passage,question=split_passage(c['prefix'])
        family=[v for v in cases if v['family']==c['family'] and v['answer']!=c['answer']]
        donor=family[i%len(family)]
        other,_=split_passage(donor['prefix'])
        out.append((c['id'],question,other+question,donor['id']))
    return {v[0]:v[1:] for v in out}
def causal_mask(n):return np.triu(np.full((n,n),-np.inf),k=1)
def binary(row):return sum(row['scores'])>=8 and min(row['scores'])>0 and not row['contradiction'] and not row['incoherent_sentence']
def kappa(a,b):
    a=np.array(a,dtype=bool);b=np.array(b,dtype=bool);assert len(a)==len(b)>0
    agreement=float(np.mean(a==b));pa=float(a.mean());pb=float(b.mean());chance=pa*pb+(1-pa)*(1-pb)
    if chance==1:raise RuntimeError('UNDEFINED_KAPPA')
    return (agreement-chance)/(1-chance)
