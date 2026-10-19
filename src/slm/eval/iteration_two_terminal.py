"""Score only the complete selected continuation under the frozen protocol."""
# Creator: Navneet Prabhakar
import argparse
import fcntl
import json
from pathlib import Path
from slm.common import checkpoint
from slm.common.config import initialize
from slm.common.tokenizer import BPE
from slm.data.review_stream import open_checked
from slm.data.tokenized import sha
from slm.eval.iteration_two import score,select
from slm.eval.iteration_two_results import paired_summary
from slm.eval.iteration_two_selection import select_from_results
from slm.train import Inputs,verify_checkpoint


def verify_terminal(report,launch,inputs,selection):
    initial=dict(step=256,cursor=256,tokens=262144,supervised_tokens=262144)
    length=len(inputs.data);positions,supervised=inputs.data.counts(length)
    final=dict(step=length,cursor=length,tokens=positions,supervised_tokens=supervised)
    executed=dict(updates=length-256,processed_positions=positions-262144,supervised_positions=supervised-262144)
    if (inputs.recipe.accumulation_steps!=1 or launch['plan_hash']!=inputs.identity or launch['logical_plan']!=inputs.plan
        or launch['resume_manifest_sha256']!=selection['selected']['checkpoint_manifest_sha256']
        or report['plan_hash']!=inputs.identity or report['status']!='data_exhausted_before_target'
        or report['initial']!=initial or report['final']!=final or report['executed_this_invocation']!=executed
        or positions<10000000 or positions+262144!=selection['maximum_physical_positions_after_continuation']
        or executed['processed_positions']!=selection['continuation_reserved_positions']):
        raise ValueError('Complete selected-chain continuation within physical budget required')
    return final


def evaluate(root,selection_file,freeze_file,backend='mlx'):
    root=Path(root);selection_file=Path(selection_file)
    selection=json.loads(selection_file.read_text());protocol=json.loads((root/'protocol.json').read_text())
    expected=select_from_results(root,freeze_file,{t:'reports/iteration-two-'+t+'-score.json' for t in ('lr-0003','lr-0010')})
    if selection!=expected:raise ValueError('Saved optimizer choice differs')
    trial=selection['selected_trial'];spec_path=root/(trial+'.json');spec=json.loads(spec_path.read_text());inputs=Inputs(spec)
    try:
        if inputs.identity!=protocol['plan_hashes'][trial]:raise ValueError('Selected terminal plan differs')
        with open_checked(next(iter(spec['releases'].values()))) as index:
            if select(index,BPE.load(spec['tokenizer']))!=protocol['groups']:raise ValueError('Terminal validation selection differs')
        run=root/'runs/selected-continuation';report=json.loads((run/'report.json').read_text());launch=json.loads((run/'run.json').read_text())
        for path in (selection_file,Path(freeze_file),root/'protocol.json',spec_path,*run.glob('*.json'),run/'events.jsonl'):inputs.pin_tree(path)
        final=verify_terminal(report,launch,inputs,selection)
        events=[json.loads(x) for x in (run/'events.jsonl').read_text().splitlines()]
        if sha(run/'events.jsonl')!=report['events_sha256'] or [e['step'] for e in events]!=list(range(257,final['step']+1)):
            raise ValueError('Terminal continuation event coverage differs')
        latest=Path(report['latest_checkpoint']).resolve()
        if latest.parent!=(run/'checkpoints').resolve() or sha(latest/'manifest.json')!=report['latest_manifest_sha256']:raise ValueError('Terminal checkpoint identity differs')
        inputs.pin_tree(latest);_,state=verify_checkpoint(latest,inputs)
        if any(state[k]!=v for k,v in final.items()):raise ValueError('Terminal state counters differ')
        cfg,weights=checkpoint.load(latest/'state/model')
        initial=score(cfg,initialize(cfg,spec['seed']),protocol['groups'],inputs.recipe,backend)
        final_metrics=score(cfg,weights,protocol['groups'],inputs.recipe,backend)
        inputs.check()
        return dict(creator='Navneet Prabhakar',version=1,selected_trial=trial,plan_hash=inputs.identity,
            protocol_sha256=sha(root/'protocol.json'),selection_sha256=sha(selection_file),scorer_sha256=sha(__file__),
            terminal_report_sha256=sha(run/'report.json'),checkpoint_manifest_sha256=sha(latest/'manifest.json'),
            checkpoint=str(latest),training_final=report['final'],initial=initial,final=final_metrics,
            comparison=paired_summary(protocol['groups'],initial,final_metrics),
            cumulative_physical_training_positions=report['final']['tokens']+262144,production_accepted=False,
            scope='Frozen initial/final foundation and assistant-target NLL diagnostics. Canonical initial weights reconstructed after training. No test-set model scores, conversation/tool capability or learned MLX/CUDA quality acceptance. Actual terminal conversation/direct assessment remains required.')
    finally:inputs.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--selection',required=True);p.add_argument('--freeze',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    output=Path(a.output)
    if output.exists():raise FileExistsError(output)
    with (Path(a.root)/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=evaluate(a.root,a.selection,a.freeze)
        with output.open('x') as out:out.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
        print(json.dumps(result['comparison'],indent=2))


if __name__=='__main__':main()
