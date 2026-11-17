"""Bounded raw conversation probes for an explicitly selected checkpoint.
No training, answer substitution, semantic grading or release acceptance.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time
from cloud_training.nano_quality import run_suite, atomic_report, output_guard, supervise, validate_suite, validate_context_requirement

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def validate_inputs(checkpoint, checkpoint_sha, suite_path, suite_sha, scope):
    if sha(Path(checkpoint)/'manifest.json') != checkpoint_sha:
        raise ValueError('Checkpoint manifest changed')
    if sha(suite_path) != suite_sha:
        raise ValueError('Suite changed')
    suite=json.loads(Path(suite_path).read_text())
    if scope not in ('exposed_fit','development'):raise ValueError('No release scope supported')
    if scope=='exposed_fit' and suite.get('purpose')!='training_fit_exposed_never_release':
        raise ValueError('Wrong fit suite scope')
    if scope=='development' and suite.get('purpose')!='development_only_never_train':
        raise ValueError('Fit must not be relabeled development')
    if not suite.get('sessions'):raise ValueError('Empty suite')
    keys=[(s['id'],i) for s in suite['sessions'] for i,_ in enumerate(s['turns'])]
    if not keys or len(keys)!=len(set(keys)) or any(not s['turns'] for s in suite['sessions']):
        raise ValueError('Duplicate or empty sessions')
    validate_suite({**suite, 'purpose':'development_only_never_train'})
    if any(t.get('reply_budget',128)>512 for s in suite['sessions'] for t in s['turns']):
        raise ValueError('Per-action reply budget exceeds512')
    return suite

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('checkpoint','checkpoint-sha','suite','suite-sha','repo','tokenizer','tokenizer-sha','output'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--scope',choices=('exposed_fit','development'),required=True)
    p.add_argument('--device',choices=('cuda','mps','cpu'),required=True)
    p.add_argument('--timeout-seconds',type=int,default=1800)
    p.add_argument('--allow-base',action='store_true')
    p.add_argument('--worker',action='store_true')
    a=p.parse_args()
    if not 30<=a.timeout_seconds<=7200:p.error('Finite timeout30..7200required')
    suite=validate_inputs(a.checkpoint,a.checkpoint_sha,a.suite,a.suite_sha,a.scope)
    out=Path(a.output)
    identity={'checkpoint_manifest_sha256':a.checkpoint_sha,'suite_sha256':a.suite_sha,
              'runner_sha256':sha(__file__),'scope':a.scope,'release_eligible':False,
              'decoding':'greedy; repetition penalty1','reply_budget':128,'device':a.device}
    if not a.worker:
        output_guard(Path(a.checkpoint),out)
        out.parent.mkdir(parents=True,exist_ok=True)
        atomic_report(out,{**identity,'status':'loading','records':[]})
        result=supervise([sys.executable,'-m','cloud_training.nano_fit_probe',*sys.argv[1:],'--worker'],out,a.timeout_seconds)
        return 0 if result['status'] in ('fit_checks_complete_requires_review','development_checks_complete') else 2
    from cloud_training.nano_serve import load_own_bundle,generate_action,BrokerChat
    from cloud_training.nano_checkpoint import validate_bundle
    model,tok,metadata=load_own_bundle(a.repo,a.checkpoint,a.tokenizer,tokenizer_sha256=a.tokenizer_sha,
                              device=a.device,allow_base=a.allow_base)
    validate_context_requirement(suite,metadata)
    factory=lambda:BrokerChat(tok,lambda ids,n:generate_action(model,tok,ids,n),reply_budget=128,context=2048)
    publish=lambda r:atomic_report(out,{**identity,**r,'scope':a.scope,'release_eligible':False})
    result=run_suite(factory,suite,deadline=time.monotonic()+a.timeout_seconds-15,publish=publish)
    for record in result['records']:
        record['decoded_actions']=[tok.decode(e['raw_ids']) for e in record['result'].get('events',[]) if 'raw_ids' in e]
    validate_inputs(a.checkpoint,a.checkpoint_sha,a.suite,a.suite_sha,a.scope)
    validate_bundle(a.checkpoint)
    if result['status']=='development_checks_complete' and a.scope=='exposed_fit':
        result['status']='fit_checks_complete_requires_review'
    publish(result)
    return 0 if result['status'] in ('fit_checks_complete_requires_review','development_checks_complete') else 2
if __name__=='__main__':raise SystemExit(main())
