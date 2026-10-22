from dataclasses import replace
import pytest
from slm.restart.batching import plan_epoch,cursor_schedule
from slm.restart.segments import segments,collate

@pytest.mark.parametrize('microbatch',[1,2,4])
@pytest.mark.parametrize('target_batch',[7,8192])
def test_schedule_has_exact_coverage_target_batches_and_cursor(microbatch,target_batch):
    contents={'short':[11,12], 'long':[10+i%100 for i in range(17000)],'empty':[]}
    parts=[s for k,v in contents.items() for s in segments(k,v)]
    expected={k:len(v)+1 for k,v in contents.items()}
    updates=plan_epoch(parts,expected_targets=expected,microbatch=microbatch,target_batch=target_batch)
    assert all(u.targets==target_batch for u in updates[:-1])
    assert 0<updates[-1].targets<=target_batch
    recovered={k:[] for k in contents};spans={k:[] for k in contents}
    for u in updates:
        n=0
        for micro in u.microbatches:
            assert 1<=len(micro)<=microbatch
            x,y,mask,ids=collate(micro)
            n+=int(mask.sum())
            for s in micro:
                recovered[s.document].extend(s.targets)
                spans[s.document].extend(range(s.first,s.last))
                original=([0]+contents[s.document])[s.first:s.last]
                assert list(s.inputs)==original
        assert n==u.targets
    for k,v in contents.items():
        assert recovered[k]==v+[1]
        assert spans[k]==list(range(len(v)+1))
    targets,boundaries=cursor_schedule(updates)
    assert targets[-1]==sum(expected.values())
    assert [targets[b] for b in boundaries]==[0]+[sum(u.targets for u in updates[:i+1]) for i in range(len(updates))]
    assert updates==plan_epoch(parts,expected_targets=expected,microbatch=microbatch,target_batch=target_batch)

@pytest.mark.parametrize('fault',['missing','repeat','shift','predecessor','eos','foreign','size'])
def test_corrupted_epoch_rejected_before_any_schedule_returned(fault):
    parts=list(segments('doc',[11]*600));expected={'doc':601}
    if fault=='missing':parts=parts[:-1]
    if fault=='repeat':parts.insert(1,parts[0])
    if fault=='shift':parts[0]=replace(parts[0],inputs=(0,12)+parts[0].inputs[2:])
    if fault=='predecessor':parts[1]=replace(parts[1],inputs=(12,)+parts[1].inputs[1:])
    if fault=='eos':parts[1]=replace(parts[1],targets=parts[1].targets[:-1]+(11,))
    if fault=='foreign':parts[0]=replace(parts[0],document='other')
    if fault=='size':expected={'doc':600}
    with pytest.raises(ValueError):plan_epoch(parts,expected_targets=expected)


def test_exact_pilot_and_evaluation_boundaries_preserve_all_targets():
    parts=list(segments('doc',[11]*20000))
    updates=plan_epoch(parts,expected_targets={'doc':20001},stop_targets=(5000,10000,20000))
    cumulative,boundaries=cursor_schedule(updates)
    ends=[cumulative[x] for x in boundaries]
    assert {5000,10000,20000,20001}<=set(ends)
    assert all(u.targets<=8192 for u in updates)
    positions=[i for u in updates for micro in u.microbatches for s in micro for i in range(s.first,s.last)]
    assert positions==list(range(20001))
    for u in updates:
        for micro in u.microbatches:
            for s in micro:assert list(s.inputs)==([0]+[11]*20000)[s.first:s.last]


@pytest.mark.parametrize('stops',[(0,),(4,),(2,2),(2,1),(True,)])
def test_invalid_stop_boundaries_rejected(stops):
    with pytest.raises(ValueError):
        plan_epoch(segments('a',[11,12]),expected_targets={'a':3},stop_targets=stops)
