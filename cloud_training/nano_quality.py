"""Frozen development checks through the actual serving/broker path.

Never used as training data or final acceptance. Exact-answer probes are narrow;
open-ended conversation still needs rubric review. Runs in a separate process
against an immutable checkpoint, with no optimizer or writes to its weights.
"""
import argparse
import hashlib
import json
import re
import time
import os
import signal
import subprocess
import sys
import math
from pathlib import Path


def normalize(text):
    return re.sub(r'\s+', ' ', (text or '').strip().casefold()).rstrip('.!')


def assess(result, spec):
    actions = [e['parsed']['proposal'] for e in result['events']
               if e['kind'] == 'model_action' and 'proposal' in e['parsed']]
    rejected = any(e['kind'] == 'broker_decision' and not e['decision']['dispatched']
                   for e in result['events'])
    decisions = [e for e in result['events'] if e['kind'] == 'broker_decision']
    correct_calls = (actions == spec.get('expected_calls', []) and not rejected
                     and len(decisions) == len(actions))
    exact = spec.get('exact_answers')
    answer = None if exact is None else normalize(result.get('assistant_text')) in [normalize(x) for x in exact]
    text = result.get('assistant_text') or ''
    words = text.casefold().split()
    grams = [tuple(words[i:i+4]) for i in range(max(0,len(words)-3))]
    repetition = 0 if not grams else 1-len(set(grams))/len(grams)
    return {'complete':result['status']=='complete','calls_correct':correct_calls,
            'exact_answer_correct':answer,'repeated_fourgram_fraction':repetition,
            'automated_pass':result['status']=='complete' and correct_calls and answer is True,
            'manual_review_required':exact is None}


def validate_suite(suite, *, release=False):
    from cloud_training.nano_chat_format import host_policy
    purpose='heldout_release_never_train' if release else 'development_only_never_train'
    if suite.get('purpose')!=purpose:raise ValueError('Wrong suite purpose')
    sessions=suite.get('sessions',[])
    if not sessions:raise ValueError('Empty evaluation suite')
    ids=[]
    for session in sessions:
        if not isinstance(session.get('id'),str) or not session['id'] or not session.get('turns'):raise ValueError('Invalid session')
        if release and not session.get('category'):raise ValueError('Release category required')
        ids.append(session['id'])
        for turn in session['turns']:
            if not isinstance(turn.get('user'),str) or not turn['user'].strip():raise ValueError('Invalid user turn')
            host_policy(turn.get('policy'))
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate session IDs')


def run_suite(chat_factory, suite, *, deadline, publish=lambda report:None):
    records=[]
    for session in suite['sessions']:
        chat=chat_factory()
        for index,spec in enumerate(session['turns']):
            if time.monotonic()>=deadline:
                return {'status':'incomplete_deadline','records':records,'usable_model_claim':False}
            result=chat.turn(spec['user'],policy=spec.get('policy'))
            records.append({'session':session['id'],'turn':index,'user':spec['user'],
                            'policy':spec.get('policy'),'rubric':spec.get('rubric'),
                            'result':result,'assessment':assess(result,spec)})
            publish({'status':'running','records':records,'usable_model_claim':False})
            if time.monotonic()>=deadline:
                return {'status':'incomplete_deadline','records':records,'usable_model_claim':False}
    scored=[r for r in records if not r['assessment']['manual_review_required']]
    return {'status':'development_checks_complete','records':records,
            'automated_passed':sum(r['assessment']['automated_pass'] for r in scored),
            'automated_total':len(scored),'manual_review_turns':len(records)-len(scored),
            'usable_model_claim':False,'limitation':'Small exposed development suite; not final acceptance.'}


def atomic_report(path,report):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('w') as f:
        json.dump(report,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def output_guard(checkpoint,output):
    checkpoint,output=Path(checkpoint).resolve(),Path(output).resolve()
    if output==checkpoint or checkpoint in output.parents:
        raise ValueError('Quality output must be outside immutable checkpoint')
    if output.exists():raise FileExistsError('Refuse to overwrite quality evidence')
    return output


def supervise(argv,output,seconds):
    """Hard wall budget includes model loading; kills and waits for entire child group.
    Controller must already have joined the base writer before calling this.
    """
    tick=time.monotonic()
    with Path(str(output)+'.log').open('x') as log:
        process=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        timed_out=False
        try:code=process.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            timed_out=True
            os.killpg(process.pid,signal.SIGKILL)
            code=process.wait()
    report=json.loads(Path(output).read_text())
    if timed_out or code!=0:
        report.update(status='incomplete_timeout' if timed_out else 'incomplete_worker_error',usable_model_claim=False)
    report.update(worker_exit_code=code,wall_seconds=time.monotonic()-tick,hard_process_timeout_seconds=seconds)
    atomic_report(output,report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('repo','checkpoint','checkpoint-manifest-sha256','tokenizer','tokenizer-sha256','suite','output'):
        p.add_argument('--'+key,required=True)
    p.add_argument('--device',default='cuda',choices=['cpu','mps','cuda'])
    p.add_argument('--allow-base',action='store_true')
    p.add_argument('--release',action='store_true',help='Frozen release suite; raw output still requires full semantic review and release gate')
    p.add_argument('--repetition-penalty',type=float,default=1.0)
    p.add_argument('--seconds',type=int,default=600)
    p.add_argument('--reply-budget',type=int,default=128)
    p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    a=p.parse_args()
    if not 1<=a.seconds<=600:p.error('Checks require a1..600second total process budget')
    if not 1<=a.reply_budget<=512:p.error('Reply budget must be 1..512 tokens')
    if not math.isfinite(a.repetition_penalty) or a.repetition_penalty!=1.0:
        p.error('Stage comparisons require raw repetition penalty1.0')
    checkpoint=Path(a.checkpoint).resolve()
    actual=hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest()
    if actual!=a.checkpoint_manifest_sha256:raise ValueError('Checkpoint manifest differs from requested provenance')
    raw=Path(a.suite).read_bytes();suite=json.loads(raw)
    validate_suite(suite,release=a.release)
    if a.release and a.allow_base:raise ValueError('Base diagnostics cannot be releases')
    metadata=json.loads((checkpoint/'metadata.json').read_text())
    if a.allow_base and (metadata['identity'].get('phase')!='base' or metadata['identity'].get('initialization')!='own_random'):
        raise ValueError('Base diagnostic requires own-random base lineage')
    provenance={'checkpoint_manifest_sha256':actual,'suite_sha256':hashlib.sha256(raw).hexdigest(),
        'step':metadata['step'],'identity':metadata['identity'],'repetition_penalty':1.0,
        'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'decoding':{'temperature':0,'reply_budget_per_action':a.reply_budget,'max_actions_per_turn':3},
        'diagnostic_base_mode':a.allow_base,'usable_model_claim':False,
        'scope':'Raw base diagnostic, not instruction-trained acceptance' if a.allow_base else 'Exposed development assessment, not final acceptance'}
    if not a.worker:
        output=output_guard(checkpoint,a.output);output.parent.mkdir(parents=True,exist_ok=True)
        atomic_report(output,dict(provenance,status='loading',records=[]))
        report=supervise([sys.executable,'-m','cloud_training.nano_quality',*sys.argv[1:],'--worker'],output,a.seconds)
        if hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest()!=actual:
            report.update(status='checkpoint_provenance_changed',usable_model_claim=False);atomic_report(output,report)
        return 0 if report['status'] in ('development_checks_complete','complete_requires_full_review') else 2
    # Separate process owns the model; no optimizer is constructed or saved.
    from cloud_training.nano_serve import BrokerChat,generate_action,load_own_bundle
    model,tok,metadata=load_own_bundle(a.repo,checkpoint,a.tokenizer,
        tokenizer_sha256=a.tokenizer_sha256,device=a.device,allow_base=a.allow_base)
    import torch
    import nanochat.flash_attention as attention
    provenance['evaluation_runtime']={'torch':torch.__version__,'cuda':torch.version.cuda,
        'device':a.device,'attention':'fa3' if attention.USE_FA3 else 'sdpa',
        'gpu':torch.cuda.get_device_name() if a.device=='cuda' else None}
    factory=lambda:BrokerChat(tok,lambda ids,n:generate_action(model,tok,ids,n,
        repetition_penalty=1.0),reply_budget=a.reply_budget,context=model.config.sequence_len)
    publish=lambda report:atomic_report(a.output,{**provenance,**report})
    report=run_suite(factory,suite,deadline=time.monotonic()+a.seconds,publish=publish)
    if a.release and report['status']=='development_checks_complete':
        report.update(status='complete_requires_full_review',scope='Frozen release evaluation awaiting full semantic review; no acceptance inferred',limitation='Raw completion is not release acceptance')
    publish(report)
    return 0 if report['status'] in ('development_checks_complete','complete_requires_full_review') else 2

if __name__=='__main__':raise SystemExit(main())
