import copy
import pytest
from slm.restart.known_leakage import audit_rows


def rows():
    return [dict(audit_id=str(i),source='fixture',split='train' if i<3 else 'test',family_id='f'+str(i),
                 normalized_sha256='n'+str(i),original_text_sha256='o'+str(i)) for i in range(4)]


def test_unchanged_subset_keeps_known_exclusions():
    mechanical=rows();selected=copy.deepcopy([mechanical[0],mechanical[3]])
    assert set(audit_rows(selected,mechanical,[('1','2')],['1']))=={'0','3'}


@pytest.mark.parametrize('fault',['unknown','changed','duplicate_id','exact','family','protected','transitive_near','empty'])
def test_known_leakage_or_changed_source_refused(fault):
    mechanical=rows();selected=copy.deepcopy([mechanical[0],mechanical[3]]);edges=[];protected=[]
    if fault=='unknown':selected[0]['audit_id']='9'
    if fault=='changed':selected[0]['original_text_sha256']='changed'
    if fault=='duplicate_id':selected.append(copy.deepcopy(selected[0]))
    if fault=='exact':
        mechanical[3]['normalized_sha256']=mechanical[0]['normalized_sha256'];selected[1]=copy.deepcopy(mechanical[3])
    if fault=='family':
        mechanical[3]['family_id']=mechanical[0]['family_id'];selected[1]=copy.deepcopy(mechanical[3])
    if fault=='protected':protected=['3']
    if fault=='transitive_near':edges=[('0','1'),('1','2'),('2','3')]
    if fault=='empty':selected=[]
    with pytest.raises(ValueError):audit_rows(selected,mechanical,edges,protected)
