#!/usr/bin/env python3
"""Record actual equal-exposure controls after both optimizer screens finish."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
from slm.data.schema import digest
from slm.data.tokenized import sha


def main():
    root=Path('data/iteration-two-experiment-v1');protocol=json.loads((root/'protocol.json').read_text())
    freeze=Path('reports/milestone-forty-eight-experiment-freeze.json')
    if sha(root/'protocol.json')!=json.loads(freeze.read_text())['protocol_sha256']:raise ValueError('Frozen optimizer protocol differs')
    trials={};plans=[];first_losses=[]
    for trial in ('lr-0003','lr-0010'):
        run=root/'runs'/trial;launch=json.loads((run/'run.json').read_text());report=json.loads((run/'report.json').read_text())
        events=[json.loads(line) for line in (run/'events.jsonl').read_text().splitlines()]
        plan=launch['logical_plan'];expected=dict(step=256,cursor=256,tokens=262144,supervised_tokens=262144)
        if (digest(plan)!=protocol['plan_hashes'][trial] or launch['plan_hash']!=protocol['plan_hashes'][trial]
            or report['plan_hash']!=launch['plan_hash'] or launch['resume_manifest_sha256'] is not None
            or report['initial']!=dict(step=0,cursor=0,tokens=0,supervised_tokens=0) or report['final']!=expected
            or report['status']!='invocation_update_limit' or len(events)!=256
            or [e['step'] for e in events]!=list(range(1,257)) or sha(run/'events.jsonl')!=report['events_sha256']):raise ValueError('Actual complete canonical screen controls differ')
        normalized=json.loads(json.dumps(plan));rate=normalized['recipe'].pop('lr');plans.append(normalized);first_losses.append(events[0]['loss'])
        trials[trial]=dict(plan_hash=launch['plan_hash'],run_sha256=sha(run/'run.json'),report_sha256=sha(run/'report.json'),
            events_sha256=sha(run/'events.jsonl'),learning_rate=rate,training_final=report['final'],
            total_seconds=report['total_seconds'],timing_seconds=report['timing_seconds'],memory=report['memory'],
            first_update_loss=events[0]['loss'],last_update_loss=events[-1]['loss'],training_launch_commit=json.loads((root/'reservations'/(trial+'.json')).read_text())['launch_commit'])
    if plans[0]!=plans[1]:raise ValueError('Plans differ beyond learning rate')
    result=dict(creator='Navneet Prabhakar',protocol_sha256=sha(root/'protocol.json'),script_sha256=sha(__file__),
        only_logical_plan_difference='recipe.lr',first_preupdate_loss_exactly_equal=first_losses[0]==first_losses[1],trials=trials,
        physical_training_positions=524288,
        scope='Actual frozen plan/exposure and first-loss controls. No independent initial-tensor equality audit, trajectory parity or conversation quality inferred. Runtime observations are not controlled cross-rate speed benchmarks.')
    with Path('reports/milestone-forty-nine-controls.json').open('x') as out:out.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
