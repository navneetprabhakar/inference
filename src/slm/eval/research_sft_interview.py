"""Actual adaptive conversation and direct scoring after bounded SFT termination."""
# Creator: Navneet Prabhakar
import argparse
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import sys
from slm.common.tokenizer import BPE
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.eval.iteration_two_assessment import validate_and_score
from slm.eval.iteration_two_interview import converse
from slm.eval.research_sft import ROOT, STAGE, TRIALS, checked, inputs, selection, publish
from slm.inference.greedy import GreedyModel
from slm.research_sft_stage import ExposureLedger
from slm.train import read, verify_checkpoint


def checked_implementation():
    frozen=read(ROOT/'interview-freeze.json')
    if frozen['implementation_sha256'] != sha(__file__) or frozen['protocol_sha256'] != sha(ROOT/'protocol.json'):
        raise ValueError('Frozen conversation wrapper changed')


def terminal_binding():
    checked_implementation(); p=checked(); chosen=selection()
    trial=chosen['selected_trial'] or TRIALS[0]
    name='selected-continuation' if chosen['selected_trial'] else trial
    score_path=ROOT/('terminal-score.json' if chosen['selected_trial'] else trial+'-score.json')
    scored=read(score_path); run_path=ROOT/'runs'/name
    report=read(run_path/'report.json'); launch=read(run_path/'run.json')
    inp=inputs(trial)
    try:
        step=475 if chosen['selected_trial'] else 64
        pos, sup=inp.data.counts(step*4)
        final=dict(step=step,cursor=step*4,tokens=pos,supervised_tokens=sup)
        if (report['status'] != ('update_target_reached' if step==475 else 'invocation_update_limit')
            or report['final'] != final or scored['training_final'] != final
            or report['plan_hash'] != inp.identity or scored['plan_hash'] != inp.identity
            or launch['logical_plan'] != inp.plan or scored['protocol_sha256'] != sha(ROOT/'protocol.json')
            or scored['run_report_sha256'] != sha(run_path/'report.json')
            or report['experiment_contract_sha256'] != sha(ROOT/'contract.json')
            or sha(run_path/'events.jsonl') != report['events_sha256']):
            raise ValueError('Complete scored terminal run required')
        path=Path(report['latest_checkpoint']).resolve()
        if (path.parent != (run_path/'checkpoints').resolve() or scored['checkpoint'] != str(path)
            or scored['checkpoint_manifest_sha256'] != report['latest_manifest_sha256']
            or sha(path/'manifest.json') != report['latest_manifest_sha256']):
            raise ValueError('Terminal score/checkpoint differs')
        _, state=verify_checkpoint(path,inp)
        if any(state[k] != v for k,v in final.items()): raise ValueError('Terminal checkpoint counters differ')
        ledger=ExposureLedger(ROOT/'contract.json',inp,'mlx','default')
        try:
            if (inp.identity,sha(path/'manifest.json')) not in ledger.checkpoints: raise ValueError('Unrecorded terminal checkpoint')
        finally: ledger.close()
        inp.check(); checked()
        spec=read(STAGE/(trial+'.json'))
        return dict(model_path=str(path/'state/model'),model_manifest_sha256=sha(path/'state/model/manifest.json'),
            tokenizer_path=spec['tokenizer'],tokenizer_manifest_sha256=sha(Path(spec['tokenizer'])/'manifest.json'),
            embedding_implementation=inp.recipe.embedding_implementation,plan_hash=inp.identity,training_final=final,
            checkpoint_manifest_sha256=report['latest_manifest_sha256'],terminal_report_sha256=sha(run_path/'report.json'),
            terminal_score_sha256=sha(score_path),selection_sha256=sha(ROOT/'selection.json'),
            termination='full_schedule_complete' if step==475 else 'both_screens_failed_retention_guard')
    finally: inp.close()


def interview():
    binding=terminal_binding(); protocol=checked()['conversation']
    model=GreedyModel(binding['model_path'],binding['tokenizer_path'],'mlx','default',
        expected_tokenizer_hash=binding['tokenizer_manifest_sha256'],embedding_implementation=binding['embedding_implementation'])
    if model.identity['model_manifest_sha256'] != binding['model_manifest_sha256']: raise ValueError('Loaded model differs')
    header=dict(creator='Navneet Prabhakar',created_at_utc=datetime.now(timezone.utc).isoformat(),
        protocol_sha256=sha(ROOT/'protocol.json'),protocol_digest=digest(protocol),interviewer_sha256=sha(__file__),
        student=model.identity,terminal=binding,review_mode='delegated_expert',human_attestation=False,training_approved=False)
    def requests():
        for line in sys.stdin: yield json.loads(line)
    def emit(value): print(json.dumps(value,ensure_ascii=False,allow_nan=False),flush=True)
    converse(model,protocol,ROOT/'conversation',header,requests(),emit)


def assess(grades_file):
    binding=terminal_binding(); protocol=checked()['conversation']; session=ROOT/'conversation'
    header=read(session/'session.json'); completion=read(session/'completion.json')
    architecture=read(Path(binding['model_path'])/'config.json')['architecture']
    if (header['terminal'] != binding or header['interviewer_sha256'] != sha(__file__)
        or header['protocol_sha256'] != sha(ROOT/'protocol.json') or header['protocol_digest'] != digest(protocol)
        or header['review_mode'] != 'delegated_expert' or header['human_attestation'] is not False
        or header['training_approved'] is not False
        or header['student']['model_manifest_sha256'] != binding['model_manifest_sha256']
        or header['student']['tokenizer_manifest_sha256'] != binding['tokenizer_manifest_sha256']
        or header['student']['architecture'] != architecture
        or header['student']['embedding_implementation'] != binding['embedding_implementation']
        or header['student']['decoding'] != protocol['decoding']
        or completion['turns'] != protocol['max_turns'] or completion['session_sha256'] != sha(session/'session.json')
        or completion['turns_sha256'] != sha(session/'turns.jsonl') or completion['assessment_pending'] is not True
        or completion['human_attestation'] is not False or completion['training_approved'] is not False):
        raise ValueError('Bound complete raw conversation required')
    rows=[json.loads(line) for line in (session/'turns.jsonl').read_text().splitlines()]
    result=validate_and_score(rows,protocol,BPE.load(binding['tokenizer_path']),read(grades_file),architecture['max_seq_len'])
    result.update(creator='Navneet Prabhakar',student=header['student'],terminal=binding,
        protocol_sha256=sha(ROOT/'protocol.json'),grades_sha256=sha(grades_file),
        transcript_sha256=sha(session/'turns.jsonl'),session_sha256=sha(session/'session.json'),
        completion_sha256=sha(session/'completion.json'),assessment_code_sha256=sha(__file__))
    publish(ROOT/'conversation-assessment.json',result)
    print(json.dumps({k:result[k] for k in ('normalized_score_out_of_100','successful_tasks','turns')}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['freeze','interview','assess'])
    parser.add_argument('--grades')
    a=parser.parse_args()
    with (ROOT/'orchestrator.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.action=='freeze':
            checked()
            if (ROOT/'execution').exists(): raise ValueError('Freeze conversation wrapper before real gradients')
            publish(ROOT/'interview-freeze.json',dict(creator='Navneet Prabhakar',implementation_sha256=sha(__file__),
                protocol_sha256=sha(ROOT/'protocol.json'),actual_conversation_required=True))
        elif a.action=='interview': interview()
        elif a.grades: assess(a.grades)
        else: raise ValueError('Direct grading file required')


if __name__=='__main__': main()
