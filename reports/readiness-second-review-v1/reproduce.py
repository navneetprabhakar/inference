"""CPU counterexample for the proposed qualification's unequal validation schedules.

Not a model run: identical hypothetical losses isolate quality-guard semantics.
"""
import json
from cloud_training.nano_quality_gate import ValidationGuard

def branch(boundaries):
    guard=ValidationGuard({'relative_tolerance':0.05,'patience':2})
    guard.observe(0,3.0)
    previous=0
    for boundary in boundaries:
        for step in range(previous+1,boundary+1):
            # The actual nano_sft loop additionally observes every worker max_step.
            if step%5==0 or step==boundary:guard.observe(step,3.3)
        previous=boundary
    return guard.state

if __name__=='__main__':
    continuous=branch([2]);split=branch([1,2])
    assert continuous['strikes']==1 and not continuous['stopped']
    assert split['strikes']==2 and split['stopped']
    print(json.dumps({'uninterrupted':continuous,'split':split,'conclusion':'Different validation schedules invalidate a controlled full-state restart comparison.'},indent=2))
