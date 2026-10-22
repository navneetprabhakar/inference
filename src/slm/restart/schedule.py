"""Verified immutable schedule and exact checkpoint cursor bindings; no execution."""
from dataclasses import dataclass
import hashlib,json,math
from .monitor import cosine_rate

@dataclass(frozen=True)
class ScheduledUpdate:
    step:int
    epoch:int
    targets:int
    cumulative_targets:int
    lr:float
    events:tuple
    microbatches:tuple


def events_at(targets,cap):
    events=[]
    if targets%500000==0:events.append('dev_loss_checkpoint')
    if targets%2000000==0:events.append('full_development_diagnostics')
    if targets%5000000==0:events.append('copying_probes')
    if targets==2000000:events.append('pilot_continuation_gate')
    if targets==cap:events.append('normal_budget_end')
    return tuple(events)


class Schedule:
    def __init__(self,raw,*,expected_sha256,document_targets):
        if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('Schedule hash changed')
        if not document_targets or any(not isinstance(k,str) or not k or type(v) is not int or v<1 for k,v in document_targets.items()):
            raise ValueError('Invalid bound document inventory')
        per_pass=sum(document_targets.values());cap=3*per_pass
        if cap>48000000 or cap<=250000:raise ValueError('Invalid real-data target cap')
        seen={k:0 for k in document_targets};epoch=1;total=0;cursor=[0];boundaries=[0];updates=[]
        for row in map(json.loads,raw.splitlines()):
            step=len(updates)+1
            if step>6000 or type(row['step']) is not int or row['step']!=step:raise ValueError('Invalid update sequence')
            if type(row['pass']) is not int:raise ValueError('Invalid pass')
            if row['pass']!=epoch:
                if row['pass']!=epoch+1 or epoch>=3 or seen!=document_targets:raise ValueError('Invalid pass transition')
                epoch+=1;seen={k:0 for k in document_targets}
            micros=[];count=0
            for micro in row['microbatches']:
                if not 1<=len(micro)<=4:raise ValueError('Invalid microbatch')
                spans=[];n=0
                for doc,first,last in micro:
                    if (doc not in seen or type(first) is not int or type(last) is not int
                            or first!=seen[doc] or not 0<last-first<=512 or last>document_targets[doc]):
                        raise ValueError('Invalid or repeated scheduled span')
                    seen[doc]=last;n+=last-first;spans.append((doc,first,last))
                micros.append(tuple(spans));count+=n;cursor.append(cursor[-1]+n)
            end=total+count
            if (not 0<count<=8192 or type(row['targets']) is not int or row['targets']!=count
                    or type(row['cumulative_targets']) is not int or row['cumulative_targets']!=end
                    or end>cap or (total//500000+1)*500000<end):
                raise ValueError('Invalid totals or skipped checkpoint boundary')
            if tuple(row['events_after_update'])!=events_at(end,cap):raise ValueError('Missing or altered evaluation event')
            lr=row['lr']
            if type(lr) not in (int,float) or not math.isfinite(lr) or abs(lr-cosine_rate(end,cap))>1e-15:
                raise ValueError('Learning rate differs from bound schedule')
            updates.append(ScheduledUpdate(step,epoch,count,end,float(lr),tuple(row['events_after_update']),tuple(micros)))
            total=end;boundaries.append(len(cursor)-1)
        if epoch!=3 or seen!=document_targets or total!=cap:raise ValueError('Incomplete three-pass schedule')
        self.updates=tuple(updates);self.cursor_targets=tuple(cursor);self.update_cursors=tuple(boundaries)
        self.sha256=expected_sha256;self.target_cap=cap

    def resume_position(self,*,step,cursor,targets):
        if (any(type(x) is not int or x<0 for x in (step,cursor,targets))
                or step>=len(self.update_cursors) or cursor!=self.update_cursors[step]
                or targets!=self.cursor_targets[cursor]):
            raise ValueError('Checkpoint is not an exact scheduled update boundary')
        return None if step==len(self.updates) else self.updates[step]
