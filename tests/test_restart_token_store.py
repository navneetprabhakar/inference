import hashlib,json
import numpy as np
import pytest
from slm.restart.token_store import TrainingTokens


def fixture(tmp_path,mutate=None):
    data=np.array([10,11,12,1,13,1],dtype='<u2').tobytes()
    rows=[{'audit_id':'a','family_id':'fa','split':'train','partial':False,'offset':0,'targets':4,'full_document_targets':4},
          {'audit_id':'b','family_id':'fb','split':'train','partial':False,'offset':4,'targets':2,'full_document_targets':2}]
    if mutate:rows,data=mutate(rows,data)
    (tmp_path/'tokens.u16').write_bytes(data)
    (tmp_path/'index.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
    m={'split':'train','targets':6,'documents':2,'families':2,'files':{f:hashlib.sha256((tmp_path/f).read_bytes()).hexdigest() for f in ['index.jsonl','tokens.u16']}}
    p=tmp_path/'manifest.json';p.write_text(json.dumps(m));return hashlib.sha256(p.read_bytes()).hexdigest()


def test_reconstruct_predecessor_eos_padding_and_immutable_source(tmp_path):
    h=fixture(tmp_path);s=TrainingTokens(tmp_path,manifest_sha256=h,vocab_size=16)
    assert s.segment('a',2,4).inputs==(11,12)
    x,y,m,p,ids=s.microbatch([('a',0,4),('b',0,2)])
    assert x.tolist()==[[0,10,11,12],[0,13,2,2]]
    assert y.tolist()==[[10,11,12,1],[13,1,2,2]]
    assert m.sum()==6 and p.tolist()==[[True]*4,[True,True,False,False]]
    (tmp_path/'tokens.u16').write_bytes(b'changed')
    assert s.segment('a',2,4).targets==(12,1)
    with pytest.raises(ValueError):TrainingTokens(tmp_path,manifest_sha256=h)


@pytest.mark.parametrize('fault',['split','family','offset','partial','eos','control','vocab'])
def test_invalid_rehashed_source_rejected(tmp_path,fault):
    def mutate(rows,data):
        if fault=='split':rows[0]['split']='test'
        if fault=='family':rows[1]['family_id']='fa'
        if fault=='offset':rows[1]['offset']=3
        if fault=='partial':rows[0]['partial']=True
        values=np.frombuffer(data,dtype='<u2').copy()
        if fault=='eos':values[3]=12
        if fault=='control':values[0]=0
        if fault=='vocab':values[0]=16
        return rows,values.tobytes()
    h=fixture(tmp_path,mutate)
    with pytest.raises(ValueError):TrainingTokens(tmp_path,manifest_sha256=h,vocab_size=16)


@pytest.mark.parametrize('span',[('a',-1,1),('a',0,5),('a',1,1),('a',True,2),('unknown',0,1)])
def test_bad_span_rejected(tmp_path,span):
    s=TrainingTokens(tmp_path,manifest_sha256=fixture(tmp_path),vocab_size=16)
    with pytest.raises(ValueError):s.segment(*span)


def test_manifest_pin_and_symlink_rejected(tmp_path):
    h=fixture(tmp_path)
    with pytest.raises(ValueError):TrainingTokens(tmp_path,manifest_sha256='0'*64)
    p=tmp_path/'tokens.u16';q=tmp_path/'other';p.rename(q);p.symlink_to(q)
    with pytest.raises(ValueError):TrainingTokens(tmp_path,manifest_sha256=h)
