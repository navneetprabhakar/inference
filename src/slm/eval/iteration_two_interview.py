"""Operator-led raw conversation, available only after verified terminal training."""
# Creator: Navneet Prabhakar
import argparse
from copy import deepcopy
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import sys
from slm.common.tokenizer import BPE
from slm.data.schema import digest
from slm.data.review_stream import open_checked
from slm.data.tokenized import sha
from slm.eval.iteration_two import select
from slm.eval.iteration_two_terminal import verify_terminal
from slm.eval import iteration_two_terminal
from slm.eval.iteration_two_selection import select_from_results
from slm.inference.greedy import GreedyModel
from slm.train import Inputs,verify_checkpoint


def protocol_checked(protocol):
    prior=Path('configs/iteration-one-conversation-assessment-v1.json')
    first=json.loads(prior.read_text())
    if (protocol.get('version')!=1 or type(protocol.get('version')) is not int or protocol.get('creator')!='Navneet Prabhakar'
        or protocol.get('review_mode')!='delegated_expert' or protocol.get('human_attestation') is not False
        or protocol.get('first_iteration_protocol_sha256')!=sha(prior)
        or any(protocol.get(k)!=first[k] for k in ('max_turns','max_new_tokens','decoding','assessment_dimensions','score_anchors','aggregation','initial_prompt'))
        or type(protocol.get('max_turns')) is not int or type(protocol.get('max_new_tokens')) is not int):
        raise ValueError('Unchanged comparative rubric and bounded raw conversation required')


def terminal_binding(root,score_file,selection_file,freeze_file):
    root=Path(root);run=root/'runs/selected-continuation'
    # Reject a live or partial job before costly source checks/model allocation.
    report=json.loads((run/'report.json').read_text())
    if report.get('status')!='data_exhausted_before_target':raise ValueError('Complete terminal training required for this assessment')
    scored=json.loads(Path(score_file).read_text());selection=json.loads(Path(selection_file).read_text())
    protocol=json.loads((root/'protocol.json').read_text());launch=json.loads((run/'run.json').read_text())
    if (scored['terminal_report_sha256']!=sha(run/'report.json') or scored['selection_sha256']!=sha(selection_file)
        or scored['protocol_sha256']!=sha(root/'protocol.json') or scored['scorer_sha256']!=sha(iteration_two_terminal.__file__)
        or scored['training_final']!=report['final'] or scored['checkpoint_manifest_sha256']!=report['latest_manifest_sha256']
        or scored['plan_hash']!=selection['selected']['plan_hash']):raise ValueError('Terminal score binding differs')
    # A failed NLL smoke is still assessed conversationally; never select only passes.
    if selection!=select_from_results(root,freeze_file,{t:'reports/iteration-two-'+t+'-score.json' for t in ('lr-0003','lr-0010')}):raise ValueError('Interview optimizer selection differs')
    spec=json.loads((root/(selection['selected_trial']+'.json')).read_text());inputs=Inputs(spec)
    try:
        final=verify_terminal(report,launch,inputs,selection)
        with open_checked(next(iter(spec['releases'].values()))) as index:
            if select(index,BPE.load(spec['tokenizer']))!=protocol['groups']:raise ValueError('Terminal validation selection differs')
        if sha(run/'events.jsonl')!=report['events_sha256']:raise ValueError('Terminal events differ')
        latest=Path(report['latest_checkpoint']).resolve()
        if latest.parent!=(run/'checkpoints').resolve() or sha(latest/'manifest.json')!=report['latest_manifest_sha256']:raise ValueError('Interview checkpoint differs')
        inputs.pin_tree(latest);_,state=verify_checkpoint(latest,inputs)
        if any(state[k]!=v for k,v in final.items()):raise ValueError('Interview terminal state differs')
        model_path=latest/'state/model';model_hash=sha(model_path/'manifest.json');inputs.check()
        return dict(model_path=str(model_path),model_manifest_sha256=model_hash,tokenizer_path=spec['tokenizer'],
            tokenizer_manifest_sha256=protocol['tokenizer_manifest_sha256'],embedding_implementation=inputs.recipe.embedding_implementation,
            training_final=final,plan_hash=inputs.identity,checkpoint_manifest_sha256=report['latest_manifest_sha256'],
            terminal_score_sha256=sha(score_file),terminal_report_sha256=sha(run/'report.json'))
    finally:inputs.close()


def converse(model,protocol,output,header,requests,emit):
    protocol_checked(protocol);output=Path(output)
    if (header.get('creator')!='Navneet Prabhakar' or header.get('review_mode')!='delegated_expert'
        or header.get('human_attestation') is not False or header.get('training_approved') is not False
        or header.get('protocol_digest')!=digest(protocol) or header.get('student')!=model.identity):raise ValueError('Bound delegated interview header required')
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True)
    (output/'session.json').write_text(json.dumps(header,indent=2,sort_keys=True)+'\n')
    history=[];turns=0
    emit(dict(status='ready',transcript=str(output/'turns.jsonl')))
    with (output/'turns.jsonl').open('x') as out:
        for request in requests:
            if turns>=protocol['max_turns']:raise ValueError('Conversation turn budget exceeded')
            if set(request)!={'user'} or not isinstance(request['user'],str) or not request['user'].strip():raise ValueError('Exactly one nonempty user string required')
            if not turns and request['user']!=protocol['initial_prompt']:raise ValueError('Initial prompt differs from comparative protocol')
            history.append(dict(role='user',content=request['user']));context=deepcopy(history)
            try:response=model.generate(deepcopy(context),protocol['max_new_tokens'])
            except Exception as error:
                row=dict(turn=turns+1,user=request['user'],context_sha256=digest(context),response=None,
                    generation_error=dict(type=type(error).__name__,message=str(error)[:2000]))
                out.write(json.dumps(row,sort_keys=True,ensure_ascii=False)+'\n');out.flush();os.fsync(out.fileno());emit(row)
                (output/'failure.json').write_text(json.dumps(dict(creator='Navneet Prabhakar',complete=False,
                    failed_turn=turns+1,turns_sha256=sha(output/'turns.jsonl'),generation_error=row['generation_error']),indent=2)+'\n')
                raise
            row=dict(turn=turns+1,user=request['user'],context_sha256=digest(context),response=response)
            out.write(json.dumps(row,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n');out.flush();os.fsync(out.fileno())
            history.append(dict(role='assistant',content=response['text']));turns+=1;emit(row)
            if turns==protocol['max_turns']:break
    if turns!=protocol['max_turns']:raise ValueError('Incomplete interview retained; no completed assessment')
    completion=dict(creator='Navneet Prabhakar',turns=turns,session_sha256=sha(output/'session.json'),turns_sha256=sha(output/'turns.jsonl'),
        human_attestation=False,training_approved=False,assessment_pending=True,
        scope='Actual raw replies retained as history. Completion means transcript coverage only; direct evidence-based grading is still required.')
    (output/'completion.json').write_text(json.dumps(completion,indent=2,sort_keys=True)+'\n');emit(dict(status='complete',turns=turns))
    return completion


def main():
    parser=argparse.ArgumentParser()
    for name in ('root','score','selection','freeze','protocol','output'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();protocol=json.loads(Path(args.protocol).read_text());protocol_checked(protocol)
    if Path(args.output).exists():raise FileExistsError(args.output)
    with (Path(args.root)/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        binding=terminal_binding(args.root,args.score,args.selection,args.freeze)
        model=GreedyModel(binding['model_path'],binding['tokenizer_path'],'mlx','default',expected_tokenizer_hash=binding['tokenizer_manifest_sha256'],
            embedding_implementation=binding['embedding_implementation'])
        if model.identity['model_manifest_sha256']!=binding['model_manifest_sha256']:raise ValueError('Loaded interview model differs')
        header=dict(creator='Navneet Prabhakar',created_at_utc=datetime.now(timezone.utc).isoformat(),protocol_sha256=sha(args.protocol),protocol_digest=digest(protocol),
            interviewer_sha256=sha(__file__),student=model.identity,terminal=binding,review_mode='delegated_expert',human_attestation=False,training_approved=False)
        def requests():
            for line in sys.stdin:yield json.loads(line)
        def emit(value):print(json.dumps(value,ensure_ascii=False,allow_nan=False),flush=True)
        converse(model,protocol,args.output,header,requests(),emit)


if __name__=='__main__':main()
