"""Deterministic document-local batches bounded by actual supervised targets.

Planning is pure data work. A worker must reserve every returned span in the
exposure ledger before computing an update; planning itself reserves nothing.
"""
from dataclasses import dataclass
from .segments import Segment
from slm.common.tokenizer import STRUCTURAL


@dataclass(frozen=True)
class Update:
    microbatches: tuple
    targets: int


def plan_epoch(parts, *, expected_targets, target_batch=8192, microbatch=4, context=512, stop_targets=()):
    """Return a complete verified one-pass schedule, allowing a short tail and exact evaluation boundaries.

    Oversized final segments at an update boundary are sliced, retaining each
    slice's original predecessor token. No unrelated documents share a row.
    expected_targets maps immutable document IDs to content length plus EOS.
    """
    if (type(target_batch) is not int or not 1<=target_batch<=8192
            or type(microbatch) is not int or microbatch not in (1,2,4)
            or type(context) is not int or not 1<=context<=512
            or not expected_targets or any(not isinstance(k,str) or not k or
                type(v) is not int or v<1 for k,v in expected_targets.items())):
        raise ValueError('Invalid frozen batch configuration')
    epoch_targets=sum(expected_targets.values())
    stops=tuple(stop_targets)
    if (any(type(x) is not int or not 0<x<=epoch_targets for x in stops)
            or any(b<=a for a,b in zip(stops,stops[1:]))):
        raise ValueError('Stop targets must be sorted unique in-range counts')
    stop_index=0;completed=0
    seen={k:0 for k in expected_targets};previous={};updates=[];micros=[];rows=[];count=0
    for part in parts:
        if (not isinstance(part,Segment) or part.document not in seen
                or type(part.first) is not int or type(part.last) is not int
                or part.first!=seen[part.document] or part.last>expected_targets[part.document]
                or not 0<len(part.inputs)<=context or len(part.inputs)!=len(part.targets)
                or part.last-part.first!=len(part.inputs)
                or any(type(t) is not int or t<0 for t in part.inputs+part.targets)):
            raise ValueError('Invalid, repeated, missing or over-budget segment')
        if part.inputs[1:]!=part.targets[:-1]:raise ValueError('Broken target shift')
        predecessor=STRUCTURAL['bos'] if part.first==0 else previous[part.document]
        if part.inputs[0]!=predecessor:raise ValueError('Broken segment predecessor')
        final=part.last==expected_targets[part.document]
        if (any(t<len(STRUCTURAL) for t in part.targets[:-1])
                or (part.targets[-1]!=STRUCTURAL['eos'] if final else part.targets[-1]<len(STRUCTURAL))):
            raise ValueError('Invalid structural content or EOS placement')
        seen[part.document]=part.last;previous[part.document]=part.targets[-1]
        offset=0
        while offset<len(part.inputs):
            next_stop=stops[stop_index] if stop_index<len(stops) else epoch_targets
            n=min(len(part.inputs)-offset,target_batch-count,next_stop-completed-count)
            rows.append(Segment(part.document,part.first+offset,part.first+offset+n,
                                part.inputs[offset:offset+n],part.targets[offset:offset+n]))
            offset+=n;count+=n
            at_stop=completed+count==next_stop
            if len(rows)==microbatch or count==target_batch or at_stop:
                micros.append(tuple(rows));rows=[]
            if count==target_batch or at_stop:
                updates.append(Update(tuple(micros),count));completed+=count;micros=[];count=0
                if at_stop and stop_index<len(stops):stop_index+=1
    if seen!=expected_targets:raise ValueError('Incomplete epoch coverage')
    if rows:micros.append(tuple(rows))
    if count:updates.append(Update(tuple(micros),count))
    assert sum(u.targets for u in updates)==sum(expected_targets.values())
    return tuple(updates)


def cursor_schedule(updates):
    """Checkpoint cursor is completed microbatches; save only at update ends."""
    targets=[0];boundaries=[0]
    for update in updates:
        before=targets[-1]
        for micro in update.microbatches:
            targets.append(targets[-1]+sum(s.last-s.first for s in micro))
        if targets[-1]-before!=update.targets:raise ValueError('Invalid update target total')
        boundaries.append(len(targets)-1)
    return targets,boundaries
