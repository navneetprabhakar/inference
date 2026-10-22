import importlib.util
from pathlib import Path
from collections import Counter
import copy
import pytest
from slm.common.tokenizer import train_core

ROOT=Path(__file__).resolve().parents[1]/'restart/teacher-pilot500-v3'

def module(name):
    spec=importlib.util.spec_from_file_location('diverse_'+name,ROOT/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def test_distinct_tasks_and_disjoint_families():
    rows,sample,splits=module('curriculum').make()
    assert len(rows)==500 and len({tuple(r['users']) for r in rows})==500
    assert len(set(sample))==100 and len(splits)==50
    assert Counter(r['split'] for r in rows)=={'train':400,'development':50,'test':50}
    assert all(len({r['split'] for r in rows if r['family']==f})==1 for f in splits)
    capacity=[r for r in rows if r['family']=='capacity_decisions']
    assert {r['oracle_notes'][0].split(';')[0] for r in capacity}=={'Yes','No'}

def test_mask_keeps_user_context_but_never_supervises_it():
    train=module('train');bpe=train_core(['hello blue folder what next red shelf'],512,min_frequency=1)
    rows=[{'messages':[{'role':'user','content':'hello blue folder'},{'role':'assistant','content':'red shelf'}]},
          {'messages':[{'role':'user','content':'hello'},{'role':'assistant','content':'blue'}]}]
    x,y,mask,attention=train.collate_chat(rows,bpe)
    assert (attention & (mask==0)).any()
    assert not (mask[~attention]>0).any()
    for i,r in enumerate(rows):
        xx,yy,mm=bpe.serialize(r['messages']);n=len(xx)
        assert x[i,:n].tolist()==xx and y[i,:n].tolist()==yy and mask[i,:n].tolist()==mm
        assert int(mask[i].sum())==len(bpe.encode(r['messages'][-1]['content']))+2

def test_guard_detects_contradictory_decision_and_strict_word_limit():
    quality=module('quality');rows,_,_=module('curriculum').make()
    r=copy.deepcopy(next(r for r in rows if r['family']=='capacity_decisions' and r['oracle_notes'][0].startswith('No')))
    r['messages']=[{'role':'user','content':r['users'][0]},{'role':'assistant','content':'Yes; a shortfall remains.'},
                   {'role':'user','content':r['users'][1]},{'role':'assistant','content':r['oracle_notes'][1]}]
    assert 'wrong_yes_no:0' in quality.check(r)
    r=copy.deepcopy(next(r for r in rows if r['family']=='declining_invitations'))
    r['messages']=[{'role':'user','content':r['users'][0]},{'role':'assistant','content':'Thank you '+r['required'][0][0]},
                   {'role':'user','content':r['users'][1]},{'role':'assistant','content':' '.join(['word']*18)}]
    assert 'wordcap:1' in quality.check(r)
