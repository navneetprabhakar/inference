"""One reserved VM, sequential fresh training processes, no provisioning or idle wait.

A reviewed config permits step32->64 recovery pilot then base continuation. Each
process uses the unchanged trainer/numerical identity and authoritative GCS
journal. Total boot-relative deadline is externally provider-enforced. Milestone
review stops by default; an explicit reviewed continue decision is required.
"""
from copy import deepcopy
import datetime as dt
import hashlib, json, math, os, shutil
from pathlib import Path
import subprocess, sys, time
from cloud_training.nano_launch import BATCH,HORIZON,stage,restore_resume,worker_argv,run_cloud,uri,fetch,digest
from cloud_training.nano_package import relative
from cloud_training.nano_benchmark import atomic_json

MILESTONES=(1_000_000_000,3_000_000_000,6_000_000_000,10_000_000_000)
EXPECTED_CE=5.803871169686317

def validate_config(config):
    retained=config.get('retained',{})
    if config.get('launch_kind')!='retained' or config.get('mode')!='resume' or config.get('resume_step')!=32:
        raise ValueError('Reviewed retained campaign must resume authoritative step32')
    if retained.get('reviewed') is not True or retained.get('allow_pilot_then_base') is not True or not retained.get('review_receipt'):
        raise ValueError('Explicit reviewed pilot-to-base continuation authorization required')
    if retained.get('expected_start_ce')!=EXPECTED_CE or retained.get('pilot_updates',32)!=32:
        raise ValueError('Pilot requires exact recorded start CE and32updates')
    finish=retained.get('protected_finish_seconds')
    if type(finish) is not int or not 14400<=finish<config['max_runtime_seconds']-1200: raise ValueError('At least4h protected finish inside lifetime required')
    if retained.get('control_uri'): uri(retained['control_uri'])
    wait=retained.get('review_wait_seconds',600)
    if type(wait) is not int or not 30<=wait<=900: raise ValueError('Review wait must be30..900seconds')
    worker_seconds=retained.get('worker_seconds',21600)
    if type(worker_seconds) is not int or not 1200<=worker_seconds<=21600: raise ValueError('Worker lifetime must be20min..6h')
    for key,policy in retained.get('milestones',{}).items():
        if key not in {str(n) for n in MILESTONES} or policy.get('action') not in ('stop','continue'):
            raise ValueError('Invalid milestone policy')
        if policy.get('action')=='continue' and (policy.get('reviewed') is not True or not policy.get('review_receipt')):
            raise ValueError('Milestone continuation requires explicit reviewed policy')
    return retained

def validation_ce(value):
    if not isinstance(value,dict) or value.get('complete') is not True or not value.get('shards') or len(value['shards'])!=value.get('expected_shards'):
        raise ValueError('Complete fixed validation required')
    shards=value['shards'];counts=[s.get('evaluated_tokens',s.get('tokens')) for s in shards]
    # Pilot01 reference is single-shard; do not average incompatible budgets.
    if len(shards)!=1: raise ValueError('Recovery comparison requires exact single-shard pilot protocol')
    ce=shards[0].get('cross_entropy_nats')
    if isinstance(ce,bool) or not isinstance(ce,(int,float)) or not math.isfinite(ce): raise ValueError('Finite validation CE required')
    return ce

def check_pilot(result,expected_identity):
    if result.get('step')!=64 or result.get('status')!='bounded_pilot_complete' or result.get('reason')!='pilot_update_limit':
        raise ValueError('Recovery pilot did not complete exactly at step64')
    if result.get('identity')!=expected_identity: raise ValueError('Pilot changed immutable numerical/data identity')
    if validation_ce(result.get('pilot_validation_start'))!=EXPECTED_CE: raise ValueError('Fresh-process restart CE differs from previous exact end')
    end=validation_ce(result.get('validation'))
    if end>=EXPECTED_CE: raise ValueError('Recovery pilot did not improve held-out CE')
    if result.get('last_checkpoint',{}).get('step')!=64: raise ValueError('Pilot64 checkpoint not reported committed')
    return {'restart_exact_ce':True,'start_ce':EXPECTED_CE,'end_ce':end,'improved':True}

def next_bound(step):
    return min([math.ceil(n/BATCH) for n in MILESTONES if math.ceil(n/BATCH)>step]+[HORIZON])

def run_process(argv,log,deadline):
    """Watchdog bounds complete process startup, loading, training and shutdown."""
    remaining=int(deadline-time.time())
    if remaining<=30: raise TimeoutError('Insufficient process watchdog reserve')
    with Path(log).open('x') as f:
        return subprocess.call(['timeout','--signal=TERM','--kill-after=60s',str(remaining),*argv],stdout=f,stderr=subprocess.STDOUT)

def validate_fetch_files(files):
    if not isinstance(files,list) or len(files)>64: raise ValueError('Bounded reviewed auxiliary file list required')
    seen=set()
    for item in files:
        if set(item)!={'path','uri','sha256','bytes'}: raise ValueError('Exact auxiliary file integrity schema required')
        path=relative(item['path'])
        if len(path.parts)<2 or path.parts[0]!='sft' or str(path) in seen: raise ValueError('Unique auxiliary paths restricted to sft/')
        seen.add(str(path));uri(item['uri']);digest(item['sha256'])
        if type(item['bytes']) is not int or not 0<item['bytes']<=2*1024**3: raise ValueError('Auxiliary object size out of bounds')
    return files

def validate_command(envelope,config,step,generation,last_generation):
    command=envelope.get('command',{})
    raw=json.dumps(command,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    if envelope.get('sha256')!=hashlib.sha256(raw).hexdigest(): raise ValueError('Control hash mismatch')
    if type(generation) is not int or generation<=last_generation: raise ValueError('Control replay/stale generation')
    if command.get('schema')!=1 or command.get('campaign_sha256')!=config['campaign_sha256'] or command.get('expected_step')!=step or command.get('reviewed') is not True or not command.get('review_receipt'):
        raise ValueError('Control not reviewed for current campaign/step')
    if command.get('action') not in ('continue_base','stop','run_stage'): raise ValueError('Unsupported control action')
    if command['action']=='run_stage':
        validate_fetch_files(command.get('fetch_files',[]))
        stage=command.get('stage');seconds=command.get('seconds');args=command.get('args')
        if stage not in ('sft','quality') or type(seconds) is not int or not 60<=seconds<=(600 if stage=='quality' else 21600): raise ValueError('Invalid bounded finish stage')
        if not isinstance(args,list) or any(not isinstance(a,str) or '\x00' in a for a in args): raise ValueError('Explicit argv list required')
        if any(a=='--output' or a.startswith('--output=') for a in args): raise ValueError('Controller owns fresh stage output')
        if stage=='sft' and any(a=='--deadline-utc' or a.startswith('--deadline-utc=') for a in args): raise ValueError('Controller owns SFT deadline')
    return command

def poll_command(config,step,last_generation,deadline):
    retained=config['retained'];source=retained.get('control_uri')
    if not source:return None,last_generation
    wait_until=min(deadline-300,time.time()+retained.get('review_wait_seconds',600))
    while time.time()<wait_until:
        # Missing object is the only tolerated GCS read failure; IAM/network errors fail closed.
        try:
            info=json.loads(run_cloud(['objects','describe',source,'--format=json'],min(wait_until,time.time()+30)))
        except subprocess.CalledProcessError as error:
            if not any(s in str(error.output) for s in ('404','not found','not exist')):raise
            time.sleep(min(30,max(0,wait_until-time.time())));continue
        generation=int(info['generation'])
        if generation>last_generation:
            raw=run_cloud(['cat',source+'#'+str(generation)],min(wait_until,time.time()+30))
            envelope=json.loads(raw)
            command=validate_command(envelope,config,step,generation,last_generation)
            return command,generation
        time.sleep(min(30,max(0,wait_until-time.time())))
    return None,last_generation

def now_utc():return dt.datetime.now(dt.timezone.utc).isoformat()

def validate_quality_result(path):
    report=json.loads(Path(path).read_text())
    if report.get('status')!='development_checks_complete':
        raise ValueError('Quality assessment incomplete; never treat timeout/error as pass')
    return {'status':report['status'],'quality_pass_claimed':False,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}

def execute_review_stage(command,config,root,number,deadline):
    import datetime as dt
    seconds=min(command['seconds'],int(deadline-time.time()-300))
    if seconds<60:raise TimeoutError('No protected lifetime left for reviewed finish stage')
    stage_deadline=time.time()+seconds
    files=validate_fetch_files(command.get('fetch_files',[]))
    if shutil.disk_usage(root).free<sum(f['bytes'] for f in files)+20*1024**3: raise ValueError('Insufficient auxiliary staging/checkpoint disk reserve')
    for item in files: fetch(item['uri'],root/item['path'],item['sha256'],stage_deadline-60,item['bytes'])
    out=root/'results'/f'review-{number:03d}';out.mkdir(exist_ok=False)
    output=out/'quality.json' if command['stage']=='quality' else out/'sft'
    args=[sys.executable,'-u','-m','cloud_training.nano_'+command['stage'],*command['args'],'--output',str(output)]
    if command['stage']=='sft':args+=['--deadline-utc',dt.datetime.fromtimestamp(stage_deadline,dt.timezone.utc).isoformat()]
    started=now_utc()
    code=run_process(args,out/'worker.log',stage_deadline)
    if code:raise RuntimeError('Reviewed stage failed; no automatic continuation')
    quality=validate_quality_result(output) if command['stage']=='quality' else None
    sft_summary=None
    if command['stage']=='sft':
        result=json.loads((output/'result.json').read_text())
        sft_summary={'status':result.get('status'),'step':result.get('step'),'reason':result.get('reason'),
                     'finite_dataset_complete':result.get('status')=='complete',
                     'quality_pass_claimed':False}
        # Bounded partial tuning is preserved for review, never called a completed diagnostic.
        if command.get('expected_end_step') is not None:
            sft_summary['expected_step_completed']=result.get('step')==command['expected_end_step']
    # Backup every small evidence artifact, never unordered checkpoint payloads.
    destination=config['backup_prefix'].rsplit('/',1)[0]+'/retained-runs/'+config['run_id']+'/reviews/'+out.name
    receipts=[]
    for file in sorted(out.rglob('*')):
        if file.is_file() and file.name!='payload.pt':
            target=destination+'/'+file.relative_to(out).as_posix()
            run_cloud(['cp',str(file),target,'--if-generation-match=0'],min(deadline-60,time.time()+120))
            receipts.append({'uri':target,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    return {'stage':command['stage'],'review_receipt':command['review_receipt'],'output':str(output),'evidence':receipts,'started_utc':started,'finished_utc':now_utc(),'argv':args,'argv_sha256':hashlib.sha256(json.dumps(args).encode()).hexdigest(),'quality_assessment':quality,'sft_assessment':sft_summary,'command':command,'command_sha256':hashlib.sha256(json.dumps(command,sort_keys=True,separators=(',',':')).encode()).hexdigest()}

def run_campaign(config,root,deadline):
    retained=validate_config(config);root=Path(root).resolve()
    if not time.time()+1200<deadline<=time.time()+115200: raise ValueError('Bounded provider-aligned lifetime required')
    results=root/'results';results.mkdir(exist_ok=True)
    status={'schema':1,'status':'staging','stages':[],'deadline_epoch':deadline,'same_vm':True,'started_utc':now_utc(),'review_receipt':retained['review_receipt']}
    def report():
        status['updated_utc']=now_utc()
        atomic_json(results/'campaign-status.json',status)
    report()
    try:
        campaign,resume=stage(config,root,deadline-900)
        identity=json.loads((resume/'metadata.json').read_text())['identity']
        step=32;number=0;generation=0;review_number=0
        base_deadline=deadline-retained['protected_finish_seconds']
        while True:
            if step>=HORIZON or base_deadline-time.time()<1200:
                status.update(status='awaiting_review',reason='protected_finish_boundary',step=step);report()
                while True:
                    command,generation=poll_command(config,step,generation,deadline)
                    if command is None or command['action']=='stop':
                        status.update(status='stopped',reason='finish_review_timeout_or_stop');report();return 0
                    if command['action']=='continue_base':raise ValueError('Base cannot consume protected finish reserve')
                    status.setdefault('review_stages',[]).append(execute_review_stage(command,config,root,review_number,deadline));review_number+=1;report()
            pilot=number==0;bound=64 if pilot else next_bound(step)
            seconds=min(10800 if pilot else retained.get('worker_seconds',21600),base_deadline-time.time()-300)
            worker_deadline=time.time()+seconds
            out=results/f'stage-{number:03d}';out.mkdir(exist_ok=False)
            current={**config,'mode':'resume','resume_step':step,'max_updates':bound-step}
            if shutil.disk_usage(root).free<20*1024**3: raise ValueError('Less than20GiB free before next stage; preserve pinned checkpoints and stop')
            if number:
                resume=restore_resume(current,root/f'resume-{number:03d}',min(worker_deadline-600,deadline-900))
            metadata=json.loads((resume/'metadata.json').read_text())
            if metadata['identity']!=identity or metadata['step']!=step: raise ValueError('Authoritative recovery identity/step changed')
            stage_record={'number':number,'kind':'recovery_pilot' if pilot else 'base','start_step':step,'bound_step':bound,'output':str(out.relative_to(root)),'status':'running','started_utc':now_utc()}
            status['stages'].append(stage_record);status.update(status='running',step=step);report()
            argv=worker_argv(current,root,campaign,resume,out,worker_deadline)
            stage_record.update(argv=argv,argv_sha256=hashlib.sha256(json.dumps(argv).encode()).hexdigest());report()
            code=run_process(argv,out/'worker.log',worker_deadline)
            if code: raise RuntimeError(f'Worker{number} failed with exit{code}; no automatic retry')
            result=json.loads((out/'result.json').read_text())
            new_step=result.get('step')
            if type(new_step) is not int or not step<new_step<=bound or result.get('identity')!=identity:
                raise ValueError('Worker made no valid progress or changed identity')
            if result.get('last_checkpoint',{}).get('step')!=new_step: raise ValueError('Latest worker result lacks matching committed checkpoint')
            if pilot:stage_record['recovery_gate']=check_pilot(result,identity)
            # Re-read remote journal and validate downloaded committed bundle before
            # a later process; never infer authority from a local result file.
            stage_record.update(status='complete',end_step=new_step,finished_utc=now_utc(),result_sha256=hashlib.sha256((out/'result.json').read_bytes()).hexdigest())
            evidence=[]
            for file in sorted(out.glob('*.json')):
                target=config['backup_prefix'].rsplit('/',1)[0]+'/retained-runs/'+config['run_id']+'/'+out.name+'/'+file.name
                run_cloud(['cp',str(file),target,'--if-generation-match=0'],min(deadline-60,time.time()+120))
                evidence.append({'uri':target,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
            stage_record['evidence']=evidence
            step=new_step;number+=1;status.update(step=step);report()
            reached=[n for n in MILESTONES if math.ceil(n/BATCH)==step]
            if reached:
                probes=result.get('base_probes',{})
                if probes.get('complete') is not True: raise ValueError('Milestone qualitative probes incomplete')
                if reached[0]==1_000_000_000:
                    checkpoint=Path(result['last_checkpoint']['path'])
                    command={'action':'run_stage','stage':'quality','seconds':600,'review_receipt':retained['review_receipt'],
                        'args':['--repo',str(root/'nanochat-source'),'--checkpoint',str(checkpoint),
                                '--checkpoint-manifest-sha256',hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest(),
                                '--tokenizer',str(root/'tokenizer'),'--tokenizer-sha256',config.get('tokenizer_sha256','ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'),
                                '--suite',str(root/'cloud_training/evaluation/conversation-tools-dev.json'),
                                '--seconds','600','--allow-base','--repetition-penalty','1.0']}
                    status.update(status='running_raw_base_quality',step=step);report()
                    status.setdefault('review_stages',[]).append(execute_review_stage(command,config,root,review_number,deadline));review_number+=1;report()
                policy=retained.get('milestones',{}).get(str(reached[0]),{'action':'continue' if reached[0]==1_000_000_000 else 'stop'})
                stage_record['milestone_policy']=policy
                if policy['action']!='continue':
                    status.update(status='awaiting_review',reason='milestone_quality_review',milestone_tokens=reached[0]);report()
                    while True:
                        command,generation=poll_command(config,step,generation,deadline)
                        if command is None or command['action']=='stop':
                            status.update(status='stopped',reason='milestone_review_timeout_or_stop');report();return 0
                        if command['action']=='continue_base':
                            stage_record['continuation_control']={'generation':generation,'command':command,'received_utc':now_utc(),'sha256':hashlib.sha256(json.dumps(command,sort_keys=True,separators=(',',':')).encode()).hexdigest()};report();break
                        status.setdefault('review_stages',[]).append(execute_review_stage(command,config,root,review_number,deadline));review_number+=1;report()
        status.update(status='base_complete',step=step,reason='SFT_requires_separate_admitted_stage_recipe');report();return 0
    except Exception as error:
        status.update(status='failed_closed',error=str(error));report();raise
