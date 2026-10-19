# Creator: Navneet Prabhakar
from copy import deepcopy
import pytest
from slm.data.near_components import Components
from slm.data.near_component_audit import reconstruct,verify


def data():
    records=[dict(sid=i,eid='source:'+str(i),fixed=1 if i==0 else 2 if i==3 else 0,blocked=int(i==4),candidate=int(i in (2,5))) for i in range(6)]
    roots=[0,0,2,3,4,5];mappings=[(10,0),(10,1),(20,2),(30,3),(40,4),(50,5)];pairs=[(10,20),(20,30),(40,50)]
    p=Components(records,roots)
    for a,b in mappings:p.register(a,b)
    for a,b in pairs:p.link(a,b)
    produced=p.result();receipt=dict(records=6,components=len(produced['components']),candidate_withheld=produced['candidate_withheld'],near_facet_links_consumed=len(pairs))
    return records,roots,mappings,pairs,produced,receipt


def test_independent_breadth_first_graph_agrees_with_all_produced_components():
    records,roots,mappings,pairs,p,r=data();expected=reconstruct(records,roots,mappings,pairs)
    report=verify(expected,[dict(sid=i,root=v) for i,v in enumerate(p['roots'])],p['components'],r)
    assert report['records_checked']==6 and r['candidate_withheld']==dict(heldout_family=1,blocked_family=1)
    assert records[0]['fixed']==1 and records[3]['fixed']==2


def test_corrupted_output_root_or_omitted_record_refused():
    records,roots,mappings,pairs,p,r=data();expected=reconstruct(records,roots,mappings,pairs)
    output=[dict(sid=i,root=v) for i,v in enumerate(p['roots'])];bad=deepcopy(output);bad[2]['root']=2
    with pytest.raises(ValueError,match='root differs'):verify(expected,bad,p['components'],r)
    with pytest.raises(ValueError,match='coverage'):verify(expected,output[:-1],p['components'],r)


def test_dropped_witness_flags_or_wrong_pair_count_refused():
    records,roots,mappings,pairs,p,r=data();expected=reconstruct(records,roots,mappings,pairs);output=[dict(sid=i,root=v) for i,v in enumerate(p['roots'])]
    bad=deepcopy(p['components']);bad[0]['heldout_priority']=0
    with pytest.raises(ValueError,match='witness flags'):verify(expected,output,bad,r)
    r['near_facet_links_consumed']=0
    with pytest.raises(ValueError,match='accounting'):verify(expected,output,p['components'],r)


def test_bad_endpoint_and_graph_cap_cannot_pass():
    records,roots,mappings,pairs,p,r=data()
    with pytest.raises(ValueError,match='endpoints'):reconstruct(records,roots,mappings,pairs+[(10,999)])
    with pytest.raises(ValueError,match='budget'):reconstruct(records,roots,mappings,pairs,max_edges=1)
