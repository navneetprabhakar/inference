"""One-core regularized lexical feasibility diagnostic. No student, network or GPU."""
from collections import Counter,defaultdict
from functools import lru_cache
from hashlib import sha256,file_digest
import json
from pathlib import Path
import re,zlib
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
REPORT=ROOT/'reports/snli-semantic'
DATA=ROOT/'data/snli-semantic'
LABELS=['entailment','neutral','contradiction']
HASH=65536
NEG=re.compile(r"\b(?:no|not|never|nobody|none|nothing|without|neither|nor|no one|n’t|can't|cannot|isn't|aren't|weren't|wasn't|doesn't|don't|didn't)\b|\bn\s*['’]t\b",re.I)
STOP=set('a and the in of is are were was by on to an it there his her their from with this that for be as at he she they some around has have had its'.split())

def file_hash(p):
    with p.open('rb') as f:return file_digest(f,'sha256').hexdigest()

def read_data():
    receipt=json.loads((REPORT/'receipt.json').read_text())['splits']
    custody=json.loads((REPORT/'protected-custody-summary.json').read_text())
    denyfile=REPORT/'protected-excluded-pair-hashes.json'
    assert file_hash(denyfile)==custody['denylist_sha256']=='64af4e1c568c38f659d61a849e7ffae8d7a28cb8c7de55c326e7c99e858a2c08'
    deny=set(json.loads(denyfile.read_text()))
    results=[]
    for split,name in [('train','train.jsonl'),('validation','internal-validation.jsonl')]:
        f=DATA/name
        assert file_hash(f)==receipt[split]['sha256']
        rows=[json.loads(l) for l in f.open()]
        assert len(rows)==receipt[split]['pairs'] and all(r['official_split']=='train' and r['split']==split for r in rows)
        if split=='train':rows=[r for r in rows if r['pair_sha256'] not in deny]
        results.append(rows)
    train,val=results
    assert len(train)==custody['approved']==41008 and len(val)==2754
    assert {r['group'] for r in train}.isdisjoint({r['group'] for r in val}) and {r['image_id'] for r in train}.isdisjoint({r['image_id'] for r in val})
    return train,val

@lru_cache(maxsize=20000)
def words(s):
    return tuple(re.findall(r"[a-z0-9]+(?:'[a-z]+)?",s.casefold().replace('’',"'")))
def twos(ws):return set(x+'_'+y for x,y in zip(ws,ws[1:]))
@lru_cache(maxsize=180000)
def key(s):return zlib.crc32(s.encode())%HASH
def ratio_bin(r):return str(min(5,int(r*5)))
def features(h,p,mode):
    H=words(h);hs=set(H);hb=twos(H)
    features={*(('h:'+w) for w in hs),*(('hb:'+w) for w in hb),'hneg:'+str(bool(NEG.search(h))),'hsize:'+str(min(8,len(H)//3))}
    if mode!='hypothesis':
        P=words(p);ps=set(P);pb=twos(P)
        if mode!='coarse':
            features.update('p:'+w for w in ps)
            features.update('pb:'+w for w in pb)
        features.update(('pneg:'+str(bool(NEG.search(p))),'psize:'+str(min(8,len(P)//3))))
    if mode in ('pair','coarse'):
        h_content=hs-STOP;p_content=ps-STOP
        if mode=='pair':
            features.update('shared:'+w for w in h_content&p_content)
            features.update('introduced:'+w for w in h_content-p_content)
            features.update('phrase:'+b for b in hb&pb)
        features.update(('same-neg:'+str(bool(NEG.search(h))==bool(NEG.search(p))),
                    'word-overlap:'+ratio_bin(len(hs&ps)/len(hs)),
                    'content-overlap:'+ratio_bin(len(h_content&p_content)/max(1,len(h_content))),
                    'phrase-overlap:'+ratio_bin(len(hb&pb)/max(1,len(hb))),
                    'new-content-count:'+str(min(5,len(h_content-p_content))),
                    'missing-content-count:'+str(min(5,len(p_content-h_content))),
                    'length-diff:'+str(np.clip((len(P)-len(H))//4,-4,6))))
    return sorted(set(key(s) for s in features))

class Sparse:
    def __init__(self,rows,mode,premises=None):
        keys=[];sizes=[]
        for i,r in enumerate(rows):
            f=features(r['hypothesis'],r['premise'] if premises is None else premises[i],mode)
            keys.extend(f);sizes.append(len(f))
        self.k=np.asarray(keys,dtype=np.int32)
        self.i=np.repeat(np.arange(len(rows),dtype=np.int32),sizes)
        self.starts=np.cumsum([0]+sizes[:-1],dtype=np.int64)
    def logits(self,W):
        return np.add.reduceat(W[self.k],self.starts,axis=0)
    def grad(self,e):
        return np.stack([np.bincount(self.k,weights=e[self.i,k],minlength=HASH) for k in range(3)],axis=1)

def fit(rows,X):
    # Equal total training weight per available evidence tier and class.
    Y=np.array([LABELS.index(r['label']) for r in rows])
    strata=[(r['annotation_tier'],r['label']) for r in rows];n=Counter(strata)
    weight=np.array([1/(len(n)*n[k]) for k in strata])
    W=np.zeros((HASH,3));m=np.zeros_like(W);v=np.zeros_like(W)
    for step in range(1,43):
        logits=X.logits(W);logits-=logits.max(axis=1,keepdims=True);prob=np.exp(logits)
        prob/=prob.sum(axis=1,keepdims=True);prob[np.arange(len(rows)),Y]-=1
        grad=X.grad(prob*weight[:,None])+.001*W
        m=.9*m+.1*grad;v=.999*v+.001*grad**2
        W-=.045*(m/(1-.9**step))/(np.sqrt(v/(1-.999**step))+1e-8)
    return W

def score(pred,y,ix):
    cm=np.bincount((3*y[ix]+pred[ix]),minlength=9).reshape(3,3);tot=cm.sum(axis=1)
    recalls=np.divide(cm.diagonal(),tot,out=np.full(3,np.nan),where=tot>0)
    return dict(n=int(tot.sum()),by_class=tot.tolist(),confusion=cm.tolist(),
                correct=int(cm.diagonal().sum()),balanced_accuracy=float(recalls.mean()) if np.all(tot>0) else None)
def permutation(rows):
    groups=defaultdict(list)
    for i,r in enumerate(rows):groups[(r['annotation_tier'],len(words(r['premise']))//5)].append(i)
    donors=list(range(len(rows)))
    for ids in groups.values():
        ids.sort(key=lambda i:sha256(('snli-permute-v1'+rows[i]['pair_id']).encode()).digest())
        for a,b in zip(ids,ids[1:]+ids[:1]):donors[a]=b
    return [rows[i]['premise'] for i in donors],sum(k!=v for k,v in enumerate(donors))

def bootstrap(rows,y,h,p,ix):
    # Paired image/premise-family bootstrap. Replicates losing a label get excluded.
    gr={g:i for i,g in enumerate(sorted({rows[i]['group'] for i in ix}))};counts=np.zeros((len(gr),6),int)
    for i in ix:
        row=counts[gr[rows[i]['group']]];k=y[i];row[k]+=1;row[k+3]+=int(p[i]==k)-int(h[i]==k)
    rng=np.random.default_rng(71033);vals=[]
    for _ in range(2000):
        draw=counts[rng.integers(0,len(counts),len(counts))].sum(axis=0)
        if (draw[:3]>0).all():vals.append(float((draw[3:]/draw[:3]).mean()))
    return dict(lower=float(np.quantile(vals,.025)),upper=float(np.quantile(vals,.975)),usable_draws=len(vals))

def main():
    train,val=read_data();y=np.array([LABELS.index(r['label']) for r in val])
    consensus=np.array([r['annotation_tier']=='multi-unanimous' for r in val])
    no_h=np.array([not NEG.search(r['hypothesis']) for r in val]);no_p=np.array([not NEG.search(r['premise']) for r in val])
    ix={k:np.flatnonzero(v) for k,v in {'all':np.ones(len(val),bool),'all_no_h_neg':no_h,'consensus':consensus,'consensus_no_h_neg':consensus&no_h,'consensus_no_either_neg':consensus&no_h&no_p}.items()}
    alternatives,n_shuffled=permutation(val)
    matched=defaultdict(list)
    for i,r in enumerate(val):matched[words(r['hypothesis'])].append(i)
    repeated=[v for v in matched.values() if len({y[i] for i in v})>1]
    ix['same_hypothesis_different_gold']=np.array([i for group in repeated for i in group],dtype=int)
    summary=dict(label_order=LABELS,denied_train=10407,validation_groups=len({r['group'] for r in val}),source_hash=file_hash(HERE/'diagnose.py'),moved_validation_premises=n_shuffled,validation_hypothesis_groups_with_multiple_gold=len(repeated),runs={})
    for tier,rows in [('unanimous',[r for r in train if r['annotation_tier']=='multi-unanimous']),('all-cleared',train)]:
        run=dict(train_by_class=Counter(r['label'] for r in rows),metrics={},paired={},error_ids={})
        pred={}
        for mode in ['hypothesis','unaligned','coarse','pair']:
            X=Sparse(rows,mode);W=fit(rows,X);del X
            pred[mode]=Sparse(val,mode).logits(W).argmax(axis=1)
            run['metrics'][mode]={k:score(pred[mode],y,v) for k,v in ix.items()}
            if mode=='pair':
                s=Sparse(val,mode,alternatives).logits(W).argmax(axis=1)
                run['metrics']['pair_scrambled_premise']={k:score(s,y,v) for k,v in ix.items()}
        for k,v in ix.items():
            h,p=pred['hypothesis'],pred['pair'];run['paired'][k]=dict(
                gains=[int(((h[v]!=y[v])&(p[v]==y[v])&(y[v]==i)).sum()) for i in range(3)],
                losses=[int(((h[v]==y[v])&(p[v]!=y[v])&(y[v]==i)).sum()) for i in range(3)])
            if k in ['consensus','consensus_no_either_neg']:
                run['paired'][k]['macro_gain_95pct_family_bootstrap']=bootstrap(val,y,h,p,v)
        for k in ['consensus','consensus_no_either_neg']:
            run['error_ids'][k]={}
            for i,label in enumerate(LABELS):
                fail=[j for j in ix[k] if y[j]==i and pred['pair'][j]!=i]
                run['error_ids'][k][label]=[{'pair_id':val[j]['pair_id'],'gold':label,'pred':LABELS[pred['pair'][j]]} for j in fail[:10]]
        summary['runs'][tier]=run
        (HERE/'results.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(tier,run['train_by_class'],{m:run['metrics'][m]['consensus']['balanced_accuracy'] for m in run['metrics']},flush=True)
if __name__=='__main__':main()
