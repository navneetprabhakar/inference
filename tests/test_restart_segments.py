import pytest
from slm.restart.segments import segments,collate
from slm.common.tokenizer import STRUCTURAL

@pytest.mark.parametrize('length',[0,1,511,512,513,1023,1024,1025])
def test_every_target_once_with_correct_predecessor(length):
    content=[10+i%100 for i in range(length)]
    parts=list(segments('doc',content))
    targets=[t for p in parts for t in p.targets]
    assert targets==content+[STRUCTURAL['eos']]
    assert [t for p in parts for t in p.inputs]==[STRUCTURAL['bos']]+content
    assert [i for p in parts for i in range(p.first,p.last)]==list(range(length+1))
    assert all(len(p.inputs)<=512 for p in parts)

def test_padding_mask_and_documents_independent():
    a=list(segments('a',[11,12]));b=list(segments('b',[13]))
    x,y,mask,spans=collate(a+b)
    assert x.tolist()==[[0,11,12],[0,13,2]]
    assert y.tolist()==[[11,12,1],[13,1,2]]
    assert mask.tolist()==[[1,1,1],[1,1,0]]
    assert spans==[('a',0,3),('b',0,2)]

@pytest.mark.parametrize('content',[[1],[False],[-1],[3.2]])
def test_structural_payload_rejected(content):
    with pytest.raises(ValueError):list(segments('doc',content))
