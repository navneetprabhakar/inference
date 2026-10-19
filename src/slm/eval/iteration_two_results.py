"""Verify actual optimizer-screen checkpoints before frozen diagnostic scoring."""
# Creator: Navneet Prabhakar
import argparse
import fcntl
import json
from pathlib import Path
import numpy as np
from slm.common import checkpoint
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.eval.iteration_two import score,SOURCES,select
from slm.common.tokenizer import BPE
from slm.data.review_stream import open_checked
from slm.train import Inputs,verify_checkpoint


def paired_summary(groups,initial,final):
    if len(groups)!=64:raise ValueError('64 frozen source-balanced groups required')
    result={}
    for metric in ('foundation','assistant'):
        a=np.asarray(initial[metric+'_group_nll'],dtype=float);b=np.asarray(final[metric+'_group_nll'],dtype=float)
        if a.shape!=(64,) or b.shape!=(64,) or not np.isfinite([a,b]).all():raise ValueError('Finite complete paired NLL required')
        delta=a-b;draws=[];rng=np.random.default_rng(20261019);means=[]
        for source in SOURCES:
            indices=[i for i,g in enumerate(groups) if g['source']==source]
            if len(indices)!=32:raise ValueError('32 groups per source required')
            values=delta[indices];means.append(float(values.mean()))
            draws.append(values[rng.integers(0,32,size=(10000,32))].mean(1))
        lower,upper=np.percentile(np.mean(draws,axis=0),[2.5,97.5]);mean=float(np.mean(means))
        result[metric]=dict(mean_improvement_nats=mean,improvement_95_percentile_ci=[float(lower),float(upper)],
            source_mean_improvements=dict(zip(SOURCES,means)),group_improvements=delta.tolist())
    result.update(foundation_smoke_passed=bool(result['foundation']['mean_improvement_nats']>=.1 and result['foundation']['improvement_95_percentile_ci'][0]>0),
                  bootstrap_resamples=10000,bootstrap_seed=20261019,production_accepted=False,conversation_capability_proved=False)
    return result


def evaluate_screen(root,trial,freeze_file,backend='mlx'):
    root=Path(root);protocol=json.loads((root/'protocol.json').read_text());freeze=json.loads(Path(freeze_file).read_text())
    if trial not in ('lr-0003','lr-0010') or sha(root/'protocol.json')!=freeze['protocol_sha256'] or digest(protocol['groups'])!=protocol['groups_sha256']:
        raise ValueError('Frozen optimizer protocol differs')
    for path,want in protocol['source_sha256'].items():
        if sha(path)!=want:raise ValueError('Frozen scorer implementation differs')
    spec_path=root/(trial+'.json');spec=json.loads(spec_path.read_text())
    if sha(spec_path)!=protocol['specs'][trial]['spec_file_sha256']:raise ValueError('Screen spec differs')
    inputs=Inputs(spec)
    try:
        if inputs.identity!=protocol['plan_hashes'][trial]:raise ValueError('Screen plan differs')
        with open_checked(next(iter(spec['releases'].values()))) as index:
            if select(index,BPE.load(spec['tokenizer']))!=protocol['groups']:raise ValueError('Frozen validation selection differs')
        run=root/'runs'/trial;report=json.loads((run/'report.json').read_text());launch=json.loads((run/'run.json').read_text())
        for path in (root/'protocol.json',Path(freeze_file),spec_path,*run.glob('*.json'),run/'events.jsonl'):inputs.pin_tree(path)
        expected=dict(step=256,cursor=256,tokens=262144,supervised_tokens=262144)
        if (report['plan_hash']!=inputs.identity or launch['plan_hash']!=inputs.identity or launch['logical_plan']!=inputs.plan
            or launch['resume_manifest_sha256'] is not None or report['status']!='invocation_update_limit'
            or report['initial']!=dict(step=0,cursor=0,tokens=0,supervised_tokens=0) or report['final']!=expected
            or report['executed_this_invocation']!=dict(updates=256,processed_positions=262144,supervised_positions=262144)
            or sha(run/'events.jsonl')!=report['events_sha256']):raise ValueError('Complete equal-exposure canonical screen required')
        events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
        if len(events)!=256 or [e['step'] for e in events]!=list(range(1,257)):raise ValueError('Screen event coverage differs')
        latest=Path(report['latest_checkpoint']).resolve()
        if latest.parent!=(run/'checkpoints').resolve() or sha(latest/'manifest.json')!=report['latest_manifest_sha256']:raise ValueError('Screen checkpoint identity differs')
        inputs.pin_tree(latest);_,state=verify_checkpoint(latest,inputs)
        if any(state[k]!=v for k,v in expected.items()):raise ValueError('Screen state counters differ')
        cfg,weights=checkpoint.load(latest/'state/model');metrics=score(cfg,weights,protocol['groups'],inputs.recipe,backend)
        inputs.check()
        return dict(creator='Navneet Prabhakar',trial=trial,plan_hash=inputs.identity,protocol_sha256=sha(root/'protocol.json'),
            run_report_sha256=sha(run/'report.json'),checkpoint_manifest_sha256=sha(latest/'manifest.json'),scorer_sha256=sha(__file__),
            training_final=expected,backend=backend,metrics=metrics,production_accepted=False,
            scope='Frozen source-balanced validation diagnostic after exactly 256 updates. No test model losses, conversation score, acceptance or repaired output.')
    finally:inputs.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--trial',required=True,choices=['lr-0003','lr-0010'])
    p.add_argument('--freeze',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    output=Path(a.output)
    if output.exists():raise FileExistsError(output)
    with (Path(a.root)/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=evaluate_screen(a.root,a.trial,a.freeze)
        with output.open('x') as out:out.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(trial=a.trial,metrics={k:v for k,v in result['metrics'].items() if not k.endswith('group_nll')}),indent=2))


if __name__=='__main__':main()
