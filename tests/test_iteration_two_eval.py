"""Selection and optimizer choice do not turn diagnostic loss into capability."""
# Creator: Navneet Prabhakar
import json
import sqlite3
from types import SimpleNamespace
import numpy as np
import pytest
from slm.eval.iteration_two import SOURCES,select,summarize,choose,score
from slm.common.config import Config,initialize
from slm.common.training import Recipe


def fixture():
    db=sqlite3.connect(':memory:');db.execute('CREATE TABLE approved(eid TEXT,data TEXT,gid TEXT,split TEXT)')
    for j,source in enumerate(SOURCES):
        for i in range(4):
            for suffix in ('a','b'):
                r=dict(example_id=f'{j}-{i}-{suffix}',source=source,messages=[dict(role='user',content='Q'),dict(role='assistant',content='A')])
                db.execute('INSERT INTO approved VALUES(?,?,?,?)',(r['example_id'],json.dumps(r),f'{j}-{i}','validation'))
    db.execute('INSERT INTO approved VALUES(?,?,?,?)',('train','{}','train','train'))
    db.execute('INSERT INTO approved VALUES(?,?,?,?)',('test','invalid','test','test'))
    return SimpleNamespace(db=db)


def test_selection_is_source_balanced_canonical_grouped_and_train_test_protected():
    index=fixture();bpe=SimpleNamespace(serialize=lambda messages,objective:([1]*20,[2]*20,[1]*20))
    try:
        rows=select(index,bpe,2);assert len(rows)==4 and len({r['group'] for r in rows})==4
        assert all(r['example_id'].endswith('a') for r in rows)
        assert rows==select(index,bpe,2)
        index.db.execute('UPDATE approved SET gid="0-0" WHERE split="train"')
        with pytest.raises(ValueError,match='intersects'):select(index,bpe,2)
    finally:index.db.close()


def test_short_supervision_and_oversized_context_are_not_silently_truncated():
    index=fixture()
    try:
        for length,mask in [(1025,1025),(20,15)]:
            bpe=SimpleNamespace(serialize=lambda messages,objective:([1]*length,[2]*length,[1]*mask+[0]*(length-mask)))
            with pytest.raises(ValueError,match='Insufficient'):select(index,bpe,2)
    finally:index.db.close()


def test_source_balanced_metric_and_predeclared_tie_break():
    groups=[dict(source=SOURCES[0]),dict(source=SOURCES[0]),dict(source=SOURCES[1])]
    r=summarize(groups,[2,4,6],[3,5,7]);assert r['source_balanced_foundation_nll']==4.5
    assert choose({'lr-0003':r,'lr-0010':dict(source_balanced_foundation_nll=4.495)})=='lr-0003'
    assert choose({'lr-0003':r,'lr-0010':dict(source_balanced_foundation_nll=4.48)})=='lr-0010'
    with pytest.raises(ValueError):choose({'lr-0003':r})
    with pytest.raises(ValueError):summarize(groups,[2,float('nan'),6],[3,5,7])


def test_scoring_matches_direct_torch_masked_losses():
    pytest.importorskip('torch')
    from slm.backends import torch_backend as backend
    import torch
    cfg=Config();weights=initialize(cfg,7);params=backend.load(cfg,weights,device='cpu');recipe=Recipe()
    groups=[dict(source=s,x=[4]*20,y=[5]*20,assistant_mask=[0]*4+[1]*16) for s in SOURCES]
    result=score(cfg,weights,groups,recipe,'torch')
    expected=float(backend.loss(params,cfg,torch.tensor([[4]*20]),torch.tensor([[5]*20]),torch.tensor([[0.]*4+[1.]*16])).detach())
    assert result['source_balanced_assistant_nll']==pytest.approx(expected)
