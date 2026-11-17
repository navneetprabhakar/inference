"""Approved task adapter: fixed SFT recipes and full checkpoint probe collection.
No admission, cloud provisioning, review fabrication or release promotion.
"""
import json,subprocess,sys
from pathlib import Path
from cloud_training.nano_recovery_gate import inspect,digest,timestamp
from cloud_training.nano_recovery_controller import safe
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_quality import atomic_report

def train_argv(request,task,root):
    common=request['training_inputs'];pilot=task['operation']=='train_curriculum'
    data=request['curriculum_inputs'] if pilot else request['fit_inputs']
    out=safe(root,task['directory'])
    args=[sys.executable,'-m','cloud_training.nano_sft','--repo',str(safe(root,common['repo'])),
          '--base',str(safe(root,common['base'])),'--base-manifest-sha',common['base_manifest_sha256'],
          '--tokenizer',str(safe(root,common['tokenizer'])),'--tokenizer-sha',common['tokenizer_sha256'],
          '--manifest',str(safe(root,data['manifest'])),'--quality-contract',str(safe(root,data['contract'])),
          '--output',str(out),'--epochs','3' if pilot else '64','--max-updates','64','--context-tokens','2048',
          '--batch-tokens','8192','--microbatch','1','--packing-buffer-size','1','--lr-multiplier','.25',
          '--eval-every-updates','1' if pilot else '5','--eval-rows','128','--seed','103','--deterministic']
    if not pilot:args+=['--fit-diagnostic','--fit-eval-steps','0','16','32','64']
    return args

def probe_all(request,task,root):
    producer=safe(root,task['producer_directory']);result=json.loads((producer/'result.json').read_text())
    best,last=result['best_development_step'],result['step']
    steps=sorted(set([best,last]+([x for x in (0,16,32,64) if x<=last] if task['operation']=='probe_fit' else [])))
    common=request['training_inputs'];destination=safe(root,task['directory']);destination.mkdir(parents=True,exist_ok=False)
    sources=[('exposed_fit',request['fit_inputs']['suite'],steps),('development',request['fit_inputs']['development_suite'],sorted(set([0,best,last])))] if task['operation']=='probe_fit' else [('development',request['curriculum_inputs']['suite'],[-1]+sorted(set([best,last]))),('protected',request['curriculum_inputs']['protected_suite'],[-1]+sorted(set([best,last])))]
    index=[]
    for scope,suite,candidates in sources:
        for step in candidates:
            checkpoint=safe(root,common['base']) if step==-1 else producer/f'step-{step:08d}'
            manifest=validate_bundle(checkpoint)
            if step>=0 and manifest['step']!=step:raise ValueError('Checkpoint step does not match selected candidate')
            path=destination/f'{scope}-{step:08d}.json';suitepath=safe(root,suite)
            argv=[sys.executable,'-m','cloud_training.nano_fit_probe','--checkpoint',str(checkpoint),
                  '--checkpoint-sha',digest(checkpoint/'manifest.json'),'--suite',str(suitepath),'--suite-sha',digest(suitepath),
                  '--repo',str(safe(root,common['repo'])),'--tokenizer',str(safe(root,common['tokenizer'])),
                  '--tokenizer-sha',common['tokenizer_sha256'],'--device','cuda','--scope','development' if scope=='protected' else scope,
                  '--timeout-seconds',str(task['per_probe_seconds']),'--output',str(path)]
            if step==-1:argv+=['--allow-base']
            child=subprocess.run(argv,check=False)
            if not path.exists():raise RuntimeError('Missing probe result')
            index.append({'scope':scope,'step':step,'path':str(path.relative_to(root)), 'sha256':digest(path),'exit_code':child.returncode})
            atomic_report(safe(root,task['result']),{'status':'running','candidates':index})
            if child.returncode:raise RuntimeError('Incomplete probe; keep full evidence')
    atomic_report(safe(root,task['result']),{'status':'complete_requires_review','candidates':index,'release_eligible':False})

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',required=True);p.add_argument('--task',required=True)
    p.add_argument('--root',default='.');p.add_argument('--validate-only',action='store_true');a=p.parse_args()
    root=Path(a.root).resolve();request=json.loads(Path(a.request).read_text());task=next(t for t in request['tasks'] if t['id']==a.task)
    if a.validate_only:
        if task['operation'] not in ('train_fit','train_curriculum'):raise ValueError('Validate-only applies to training preflight')
        return subprocess.run(train_argv(request,task,root)+['--validate-only'],cwd=root).returncode
    # Child repeats gate verification, and refuses invocation without controller intent.
    decision=inspect(root,request,task['stage'])
    if not decision['allowed']:raise ValueError('Task gate: '+ '; '.join(decision['blockers']))
    state=json.loads(safe(root,request['controller_directory']+'/state.json').read_text())
    if state.get('spec_sha256')!=decision['spec_sha256'] or state.get('running',{}).get('id')!=task['id']:
        raise ValueError('Task requires matching durable controller intent')
    if task['operation'] in ('train_fit','train_curriculum'):
        remote=request['backup_prefix'].rstrip('/')+'/'+task['id']+'/checkpoints'
        deadline=request['worker_stop_utc'];timestamp(deadline)
        argv=train_argv(request,task,root)+['--deadline-utc',deadline,'--checkpoint-reserve-seconds','600','--backup-prefix',remote]
        code=subprocess.run(argv,cwd=root).returncode
        if code:return code
        result=json.loads((safe(root,task['directory'])/'result.json').read_text())
        if result.get('reason') not in ('dataset_complete','pilot_update_limit'):raise ValueError('Training did not reach its bounded endpoint')
        atomic_report(safe(root,task['result']),{'status':'bounded_training_complete_not_accepted','training_result_sha256':digest(safe(root,task['directory'])/'result.json'),'step':result['step']})
    elif task['operation'] in ('probe_fit','probe_curriculum'):probe_all(request,task,root)
    else:raise ValueError('Unknown operation')
    return 0
if __name__=='__main__':raise SystemExit(main())
