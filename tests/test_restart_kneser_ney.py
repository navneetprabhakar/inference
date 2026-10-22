import itertools
import numpy as np
import pytest
from slm.restart.kneser_ney import build,windows,Model,discount

def fixture(tmp_path):
    docs=[[2,3,1]]*10+[[4,3,1]]
    ids=[];index=[]
    for doc in docs:index.append({'offset':len(ids),'targets':len(doc)});ids.extend(doc)
    path=tmp_path/'model';build(windows(np.array(ids,dtype=np.uint16),index),path)
    return path

def test_distinct_left_context_counts_not_raw_frequency(tmp_path):
    p=fixture(tmp_path)
    g=np.load(p/'grams-1.npy');c=np.load(p/'counts-1.npy')
    assert dict(zip(g['0'].tolist(),c.tolist()))=={1:1,2:1,3:2,4:1}
    g=np.load(p/'grams-5.npy');c=np.load(p/'counts-5.npy')
    found={tuple(row.tolist()):int(n) for row,n in zip(g,c)}
    assert found[(0,0,0,2,3)]==10 and found[(0,0,0,4,3)]==1
    assert (2,3,1,4,3) not in found

def test_all_seen_unseen_contexts_normalize(tmp_path):
    p=fixture(tmp_path)
    contexts=list(itertools.product(range(6),repeat=4))
    q=np.array([(*h,w) for h in contexts for w in range(6)],dtype=np.uint16)
    for scale in [.8,1.,1.2]:
        prob=Model(p,scale).probabilities(q).reshape(-1,6)
        np.testing.assert_allclose(prob.sum(axis=1),1.,atol=1e-12)
        assert np.all(prob>=0)

def test_unseen_history_backs_off_to_continuation_distribution(tmp_path):
    p=fixture(tmp_path)
    q=np.array([[5,5,5,5,w] for w in range(6)],dtype=np.uint16)
    np.testing.assert_allclose(Model(p).probabilities(q),[0,.2,.2,.4,.2,0],atol=1e-12)

def test_discount_formula_and_sparse_fallback():
    d,h,f=discount(np.array([1]*20+[2]*10+[3]*4+[4]*2))
    np.testing.assert_allclose(d,[.5,1.4,2.]);assert h==[20,10,4,2] and not f
    d,h,f=discount(np.array([10,10]));assert f
    np.testing.assert_allclose(d,[.5,1,1.5])
