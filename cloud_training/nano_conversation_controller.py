"""One-writer, finite two-arm pilot controller. No VM allocator or release path."""
import argparse,datetime as dt,fcntl,hashlib,json,math,os,signal,subprocess,sys,time
from pathlib import Path
from cloud_training.nano_data import sha256_file
from cloud_training.nano_benchmark import atomic_json
from cloud_training.nano_block_replay import PLAN_SHA


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def timestamp(value):return dt.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()
def finite(v):return type(v) in (int,float) and math.isfinite(v)


def validate_request(request, root, *, now=None, require_gpu=True):
    now=time.time() if now is None else now
    errors=[]
    if request.get('schema')!=1 or request.get('experiment')!='ganesh-conversation-execution-v1':errors.append('Unknown experiment')
    if request.get('machine')!='a2-highgpu-1g' or request.get('resource_count')!=1:errors.append('Wrong resource class/count')
    if request.get('provider_action')!='STOP' or request.get('disk_auto_delete') is not False:errors.append('Recovery disk/STOP required')
    if request.get('automatic_retry') is not False or request.get('release_eligible') is not False:errors.append('Retry/release not allowed')
    files=request.get('files',{})
    if not files:errors.append('Unbound runtime')
    for name,h in files.items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts or not (root/p).is_file() or sha256_file(root/p)!=h:errors.append('Changed input: '+name)
    try:
        auth=json.loads((root/request['authorization']).read_text())
        if request['authorization'] not in files or auth['approved'] is not True or auth['approved_usd']!=25 or auth['machine']!='a2-highgpu-1g':raise ValueError()
    except (KeyError,ValueError,OSError):errors.append('Missing $25 scoped approval')
    try:
        start=timestamp(request['lease_start_utc']);stop=timestamp(request['provider_stop_utc'])
        if not 0<stop-start<=195*60 or now<start or now>=stop:errors.append('Expired/invalid fixed lease')
        hourly=request['hourly_compute_disk_usd'];reserve=request['storage_network_recovery_reserve_usd'];spent=request['prior_attempt_upper_usd']
        if not all(finite(x) and x>=0 for x in (hourly,reserve,spent)) or hourly<=0 or reserve<7:raise ValueError()
        if spent+((stop-start+60)/3600)*hourly*1.25+reserve>25:errors.append('Cap/reserve exceeded')
    except (KeyError,TypeError,ValueError):errors.append('Missing finite budget/lease')
    if request.get('block_plan_sha256')!=PLAN_SHA:errors.append('Wrong frozen plan')
    if request.get('backup_reserve_seconds')!=1500:errors.append('Backup reserve changed')
    for name in ('local_tests','input_readback','provider_readback')+(('cuda_changed_path','measured_forecast') if require_gpu else ()):
        try:
            rec=request['receipts'][name];path=root/rec['path']
            if rec['path'] not in files or files[rec['path']]!=rec['sha256'] or sha256_file(path)!=rec['sha256']:raise ValueError()
            value=json.loads(path.read_text())
            if value.get('status')!='pass' or value.get('check')!=name or value.get('runtime_sha256')!=request['runtime_sha256']:raise ValueError()
            if name=='provider_readback' and (value.get('stop_utc')!=request['provider_stop_utc'] or value.get('auto_delete') is not False or value.get('instance')!=request['instance']):raise ValueError()
            if name in ('cuda_changed_path','measured_forecast') and value.get('instance')!=request['instance']:raise ValueError()
            if name=='measured_forecast' and (not finite(value.get('remaining_seconds')) or value['remaining_seconds']<=0 or not start<=timestamp(value['measured_utc'])<=now or timestamp(value['measured_utc'])+value['remaining_seconds']+1500>stop):raise ValueError()
        except (KeyError,TypeError,ValueError,OSError):errors.append('Missing verified receipt: '+name)
    return errors


def training_argv(request, root, arm, output):
    if arm not in ('broad','control'):raise ValueError('Unknown arm')
    p='reports/ganesh-conversation-execution-v1/';c='reports/ganesh-conversation-pilot-v1/'
    cmd=[sys.executable,'-m','cloud_training.nano_sft','--manifest',p+arm+'-manifest.json','--quality-contract',p+arm+'-contract.json',
         '--block-plan',c+'exposure-plan.json','--block-arm',arm,'--stage','targeted','--base',request['parent'],
         '--base-manifest-sha',request['parent_manifest_sha256'],'--ancestor',request['ancestor'],'--tokenizer',request['tokenizer'],
         '--tokenizer-sha',request['tokenizer_sha256'],'--repo',request['repo'],'--output',str(output),
         '--context-tokens','2048','--batch-tokens','8192','--microbatch','1','--epochs','1','--seed','103',
         '--lr-multiplier','.25','--muon-kernel-mode','eager','--packing-buffer-size','1','--eval-every-updates','5','--eval-rows','128',
         '--max-updates','40','--deterministic','--checkpoint-reserve-seconds','600',
         '--deadline-utc',request['training_stop_utc'],'--backup-prefix',request['backup_prefix']+'/'+arm+'/checkpoints']
    # Every consumed manifest, dataset, source, parent and tokenizer identity must be bound.
    required=[p+arm+'-manifest.json',p+arm+'-contract.json',p+arm+'-admission.json',c+'exposure-plan.json',
              request['parent']+'/manifest.json',request['ancestor']+'/manifest.json',request['tokenizer']+'/tokenizer.pkl']
    required += [c+name for name in json.loads((root/c/'freeze.json').read_text())['files']]+[c+'freeze.json']
    required += ['cloud_training/'+name for name in ('nano_sft.py','nano_block_replay.py','nano_quality_gate.py','nano_conversation_controller.py')]
    if any(x not in request['files'] for x in required):raise ValueError('Controller omitted a consumed input')
    if timestamp(request['training_stop_utc'])+1500>timestamp(request['provider_stop_utc']):raise ValueError('Training consumes backup reserve')
    return cmd


def stop_child(child):
    os.killpg(child.pid,signal.SIGTERM)
    try:child.wait(timeout=20)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()



def validate_arm_review(root, directory, arm, review):
    result_path=directory/arm/'result.json';result=json.loads(result_path.read_text())
    if review.get('training_result_sha256')!=sha256_file(result_path) or review.get('systemic_failure') is not False:
        raise ValueError('Review/result mismatch or systemic failure')
    steps={result['step'],result['best_development_step']}
    if result['step']>=20:steps.add(20)
    expected={(step,scope) for step in steps for scope in ('development','protected')}
    items=review.get('snapshots',[])
    if len(items)!=len(expected) or {(r.get('step'),r.get('scope')) for r in items}!=expected:
        raise ValueError('Missing best/midpoint/last review')
    for item in items:
        rawpath=directory/item['raw'];labelpath=directory/item['review']
        if directory not in rawpath.resolve().parents or directory not in labelpath.resolve().parents:
            raise ValueError('Review path escapes run')
        if sha256_file(rawpath)!=item['raw_sha256'] or sha256_file(labelpath)!=item['review_sha256']:
            raise ValueError('Changed raw/review')
        raw=json.loads(rawpath.read_text());labels=json.loads(labelpath.read_text())
        suitepath=root/('reports/ganesh-conversation-pilot-v1/development-suite.json' if item['scope']=='development' else 'cloud_training/evaluation/conversation-tools-dev.json')
        suite=json.loads(suitepath.read_text());pairs=[(s['id'],i) for s in suite['sessions'] for i,_ in enumerate(s['turns'])]
        if raw.get('suite_sha256')!=sha256_file(suitepath) or raw.get('status')!='development_checks_complete':raise ValueError('Incomplete or changed evaluation suite')
        checkpoint=directory/arm/f"step-{item['step']:08d}"/'manifest.json'
        if raw.get('checkpoint_manifest_sha256')!=sha256_file(checkpoint):raise ValueError('Wrong evaluation checkpoint')
        if labels.get('raw_sha256')!=item['raw_sha256']:raise ValueError('Unbound semantic labels')
        for records in (raw.get('records',[]),labels.get('records',[])):
            if [(r.get('session'),r.get('turn')) for r in records]!=pairs:raise ValueError('Missing/extra/blocked review records')
        if any(type(r.get('pass'))is not bool or not r.get('reason') for r in labels['records']):raise ValueError('Incomplete per-turn semantic review')
    return True


def normal_stop_allowed(*, writers_joined, required, verified):
    return writers_joined is True and bool(required) and set(required)<=set(verified) and all(verified[x] is True for x in required)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',required=True);p.add_argument('--root',default='.');p.add_argument('--directory',required=True)
    p.add_argument('--validate-only',action='store_true');a=p.parse_args()
    root=Path(a.root).resolve();request=json.loads(Path(a.request).read_text());directory=Path(a.directory).resolve()
    errors=validate_request(request,root)
    if errors:print(json.dumps({'status':'hold','errors':errors}));return 2
    for arm in ('broad','control'):training_argv(request,root,arm,directory/arm)
    if a.validate_only:print(json.dumps({'status':'validated_not_executed'}));return 0
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'controller.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state_path=directory/'state.json';identity=digest(request)
        state=json.loads(state_path.read_text()) if state_path.exists() else {'request_sha256':identity,'running':None,'failed':None,'completed':{}}
        if state['request_sha256']!=identity:raise ValueError('Changed controller request')
        if state['running'] or state['failed']:raise ValueError('Interrupted/failed operation requires reconciliation; no automatic retry')
        for arm,record in state['completed'].items():
            if sha256_file(directory/arm/'result.json')!=record['result_sha256']:raise ValueError('Completed result changed')
        arm=next((x for x in ('broad','control') if x not in state['completed']),None)
        if arm is None:print(json.dumps({'status':'both_arms_stopped_requires_full_review','quality_accepted':False}));return 0
        # Both arms are the predeclared controlled experiment. A quality stop in one
        # does not authorize extra updates; infrastructure failure blocks the next.
        forecast=json.loads((root/request['receipts']['measured_forecast']['path']).read_text())
        remaining=forecast['remaining_seconds']-720*len(state['completed'])
        if time.time()+remaining+1500>timestamp(request['provider_stop_utc']):raise ValueError('Remaining measured stages no longer fit lease')
        output=directory/arm
        if output.exists():raise FileExistsError('Refuse nonempty arm output/retry')
        timeout=min(720,timestamp(request['training_stop_utc'])-time.time()-600)
        if timeout<120:raise ValueError('Insufficient stage time including checkpoint reserve')
        cmd=training_argv(request,root,arm,output)
        state['running']={'arm':arm,'argv_sha256':digest(cmd)};atomic_json(state_path,state)
        try:
            with (directory/(arm+'.log')).open('x') as log:
                child=subprocess.Popen(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:rc=child.wait(timeout=timeout)
                except BaseException:stop_child(child);raise
            result=json.loads((output/'result.json').read_text())
            if rc not in (0,2) or result.get('reason') not in ('dataset_complete','quality_regression_stop'):raise ValueError('Training/infrastructure failure')
            if result['identity'].get('block_arm')!=arm or not result['identity'].get('controlled_pilot_only'):raise ValueError('Wrong output identity')
            state['completed'][arm]={'result_sha256':sha256_file(output/'result.json'),'reason':result['reason'],'step':result['step']}
            state['running']=None;atomic_json(state_path,state)
        except BaseException as error:
            state['failed']={'arm':arm,'reason':repr(error)};state['running']=None;atomic_json(state_path,state);raise
        print(json.dumps({'status':'arm_stopped_requires_generation_and_review','arm':arm,'quality_accepted':False}));return 0
if __name__=='__main__':raise SystemExit(main())
