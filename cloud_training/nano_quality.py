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


def run_suite(chat_factory, suite, *, deadline):
    records=[]
    for session in suite['sessions']:
        chat=chat_factory()
        for index,spec in enumerate(session['turns']):
            if time.monotonic()>=deadline:
                return {'status':'incomplete_deadline','records':records,'usable_model_claim':False}
            result=chat.turn(spec['user'],policy=spec.get('policy'))
            records.append({'session':session['id'],'turn':index,'rubric':spec.get('rubric'),
                            'result':result,'assessment':assess(result,spec)})
    scored=[r for r in records if not r['assessment']['manual_review_required']]
    return {'status':'development_checks_complete','records':records,
            'automated_passed':sum(r['assessment']['automated_pass'] for r in scored),
            'automated_total':len(scored),'manual_review_turns':len(records)-len(scored),
            'usable_model_claim':False,'limitation':'Small exposed development suite; not final acceptance.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('repo','checkpoint','tokenizer','tokenizer-sha256','suite','output'):
        p.add_argument('--'+key,required=True)
    p.add_argument('--device',default='cuda',choices=['cpu','mps','cuda'])
    p.add_argument('--allow-base',action='store_true')
    p.add_argument('--repetition-penalty',type=float,default=1.0)
    p.add_argument('--seconds',type=int,default=600)
    a=p.parse_args()
    if not 1<=a.seconds<=900:p.error('Checks require a1..900second budget')
    from cloud_training.nano_serve import BrokerChat,generate_action,load_own_bundle
    raw=Path(a.suite).read_bytes();suite=json.loads(raw)
    if suite.get('purpose')!='development_only_never_train':raise ValueError('Development-only suite required')
    model,tok,metadata=load_own_bundle(a.repo,a.checkpoint,a.tokenizer,
        tokenizer_sha256=a.tokenizer_sha256,device=a.device,allow_base=a.allow_base)
    factory=lambda:BrokerChat(tok,lambda ids,n:generate_action(model,tok,ids,n,
        repetition_penalty=a.repetition_penalty),reply_budget=128)
    report=run_suite(factory,suite,deadline=time.monotonic()+a.seconds)
    report.update(checkpoint_manifest_sha256=hashlib.sha256((Path(a.checkpoint)/'manifest.json').read_bytes()).hexdigest(),
        suite_sha256=hashlib.sha256(raw).hexdigest(),step=metadata['step'],identity=metadata['identity'],
        repetition_penalty=a.repetition_penalty,diagnostic_base_mode=a.allow_base)
    from cloud_training.runtime import atomic_json
    atomic_json(a.output,report)

if __name__=='__main__':main()
