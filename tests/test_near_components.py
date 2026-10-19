# Creator: Navneet Prabhakar
from copy import deepcopy
import pytest
from slm.data.near_components import Components


def row(sid,fixed=0,blocked=0,candidate=0):return dict(sid=sid,eid='source:'+str(sid),fixed=fixed,blocked=blocked,candidate=candidate)


def test_near_links_propagate_heldout_and_rejection_without_changing_original_labels():
    records=[row(0,fixed=1),row(1,candidate=1),row(2,fixed=2),row(3,blocked=1),row(4,candidate=1)]
    original=deepcopy(records);c=Components(records,[0,1,2,3,4])
    for i in range(5):c.register(100+i,i)
    c.link(100,101);c.link(101,102);c.link(103,104)
    result=c.result();assert result['roots']==[0,0,0,3,3]
    assert result['candidate_withheld']==dict(heldout_family=1,blocked_family=1)
    assert result['components'][0]['heldout_priority']==2 and records==original


def test_inherited_seed_link_roots_are_consumed_before_near_links():
    records=[row(0,blocked=1),row(1),row(2,candidate=1)]
    c=Components(records,[0,0,2]);c.register(10,1);c.register(20,2);c.link(10,20)
    assert c.result()['candidate_withheld']==dict(blocked_family=1)


def test_missing_endpoint_and_inconsistent_raw_exact_mappings_refused():
    c=Components([row(0),row(1)],[0,1]);c.register(10,0)
    with pytest.raises(ValueError,match='inherited exact'):c.register(10,1)
    with pytest.raises(ValueError,match='endpoint'):c.link(10,99)


def test_incomplete_or_noncanonical_inherited_roots_refused():
    with pytest.raises(ValueError):Components([row(0)],[])
    with pytest.raises(ValueError):Components([row(0)],[9])
    with pytest.raises(ValueError):Components([row(0),row(1)],[1,0])
