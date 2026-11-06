"""Single disposable hardware trial candidate. No activation, export or resume.

Production entrypoint is gated; tests call the same workload with tiny CPU rows.
"""
import os
for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):
    os.environ[_key]='1'
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import uuid
import sys
import time
import torch
from base_run_control import _write,CampaignStop
from guards import Guard
from gpt2 import GPT2
from train import optimizer_for
import own_base_sft_train as train
from own_base_sft_control import WORK,valid_work
ROOT=Path(__file__).resolve().parent
ROLES=('chat','primary_tool','four_call_extension')
CONFIG=dict(context=1024,microbatch=1,evaluation_microbatch=1,accumulation=8,bf16=True,evaluation_precision='fp32')
WARMUPS=(3,3,2);MEASURED=(12,12,8)
ACTIVE=1200;CALENDAR=1800;RSS=18*1024**3;OUTPUT=32*1024**2
LIMITS=dict(assistant_targets=327680,input_tokens=376832,padded_tokens=376832,attention_cells=385875968,evaluation_targets=49152)
SOURCE_LIMITS={role:dict(assistant_targets=n*1024,input_tokens=(n+16)*1024,padded_tokens=(n+16)*1024,attention_cells=(n+16)*1024**2,evaluation_targets=16*1024) for role,n in zip(ROLES,(120,120,80))}


def digest_value(value):return hashlib.sha256(train.canonical(value)).hexdigest()

def selection(data):
    """Deterministic, count-exact sampling with disclosed cycling, no text edits."""
    def eligible(split,role):
        result=[i for i,row in enumerate(data.rows[split]) if row['_source']==role and (role!=ROLES[2] or row['turn']==2)]
        if not result:raise ValueError('missing source/final-session prefixes')
        return sorted(result,key=lambda i:(data.rows[split][i]['length'],data.rows[split][i]['doc_id'],data.rows[split][i]['turn']))
    def take(pool,count,start=0):return [pool[(start+i)%len(pool)] for i in range(count)]
    def groups(pool):return [pool[(q*len(pool))//4:((q+1)*len(pool))//4] or pool for q in range(4)]
    def spread(pool,count):
        return take(pool,count) if len(pool)<count else [pool[(i*(len(pool)-1))//max(1,count-1)] for i in range(count)]
    def quartiles(pool,count):
        parts=groups(pool);draws=[spread(part,(count+3-q)//4) for q,part in enumerate(parts)]
        return [draws[i%4][i//4] for i in range(count)]
    def merge(queues):
        return [item for _,_,item in sorted((Fraction(2*i+1,2*len(q)),s,item) for s,q in enumerate(queues) for i,item in enumerate(q))]
    warm=[];measured=[];validation=[];coverage={}
    for role,nwarm,nmeasured in zip(ROLES,WARMUPS,MEASURED):
        pool=eligible('train',role);longest=list(reversed(pool));is_extension=role==ROLES[2]
        wr=take(longest,nwarm*8) if is_extension else quartiles(pool,nwarm*8)
        w=[dict(source=role,phase='warmup',stratum='four-call-final' if is_extension else 'length-quartiles',indices=wr[i:i+8]) for i in range(0,len(wr),8)]
        if is_extension:
            chosen=take(longest,nmeasured*8,nwarm*8)
            m=[dict(source=role,phase='measured',stratum='four-call-final-longest',indices=chosen[i:i+8]) for i in range(0,len(chosen),8)]
        else:
            stress=take(longest,32);m=[]
            for q,part in enumerate(groups(pool)):
                chosen=spread(part,16)
                m += [dict(source=role,phase='measured',stratum=f'length-quartile-{q+1}',indices=chosen[i:i+8]) for i in (0,8)]
            m += [dict(source=role,phase='measured',stratum='longest',indices=stress[i:i+8]) for i in range(0,32,8)]
        warm.append(w);measured.append(m)
        vp=eligible('validation',role)
        chosen=take(list(reversed(vp)),16) if is_extension else quartiles(vp,8)+take(list(reversed(vp)),8)
        validation.extend(chosen)
        used=wr+[j for item in m for j in item['indices']]
        coverage[role]=dict(eligible_train=len(pool),training_draws=len(used),unique_training_rows=len(set(used)),evaluation_draws=16,unique_evaluation_rows=len(set(chosen)),max_training_length=max(data.rows['train'][i]['length'] for i in used),max_evaluation_length=max(data.rows['validation'][i]['length'] for i in chosen),final_turn_only=is_extension)
    result=dict(updates=merge(warm)+merge(measured),validation=validation,coverage=coverage)
    if len(result['updates'])!=40 or len(validation)!=48:raise ValueError('fixed allocation mismatch')
    result['selected_rows']={split:[dict(index=i,**data.rows[split][i]) for i in sorted(set(indices))] for split,indices in [('train',[j for u in result['updates'] for j in u['indices']]),('validation',validation)]}
    exposure={}
    for item in result['updates']:
        bins=exposure.setdefault(item['source'],[0,0,0,0])
        for i in item['indices']:
            _,labels=data.row('train',i)
            for pos,label in enumerate(labels):
                if label!=-100:
                    if pos+1>=1024:raise ValueError('target position exceeds frozen framing')
                    bins[(pos+1)//256]+=1
    result['draw_weighted_target_positions']=exposure
    result['sha256']=digest_value(result)
    return result


class EvaluationView:
    def __init__(self,data,indices):
        self.data=data;self.indices=indices
        self.rows={'train':data.rows['train'],'validation':[data.rows['validation'][i] for i in indices]}
    def row(self,split,index):return self.data.row(split,self.indices[index] if split=='validation' else index)


class Ledger:
    """No checkpoint API: every attempt is permanent and the run is nonresumable."""
    def __init__(self,path,identity,guard,*,started=None,wall_started=None,synchronize=lambda:None,telemetry=lambda:{}):
        self.path=Path(path);self.guard=guard;self.started=time.monotonic() if started is None else started;self.wall_started=time.time() if wall_started is None else wall_started
        self.sync=synchronize;self.telemetry=telemetry;self.pending_started=None
        if (self.path/'preflight-ledger.json').exists():raise ValueError('consumed preflight directory')
        self.value=dict(schema=1,state='initializing',identity=identity,started=self.wall_started,attempted={k:0 for k in WORK},by_source={name:{k:0 for k in WORK} for name in ROLES},attempted_updates=0,attempted_train_rows=0,attempted_evaluation_rows=0,completed_updates=0,completed_evaluation_rows=0,pending=None,measurements=[])
        self.publish()
    def publish(self):
        self.value['elapsed_seconds']=time.monotonic()-self.started
        record=deepcopy(self.value);record['sha256']=digest_value(record);_write(self.path/'preflight-ledger.json',record)
    def check(self):
        train.stop_check(dict(self.value['identity'].get('spec',{}),cpu_rss_limit_bytes=RSS),self.path);self.guard.check()
        if time.monotonic()-self.started>=ACTIVE or time.time()-self.wall_started>=CALENDAR:raise CampaignStop('paused-resource','fixed preflight time ceiling')
        if shutil.disk_usage(self.path).free<20*1024**3:raise CampaignStop('paused-resource','preflight disk floor')
        if sum(p.stat().st_size for p in self.path.iterdir() if p.is_file())>OUTPUT:raise CampaignStop('paused-resource','preflight output ceiling')
    def _charge(self,work,source,pending):
        self.check();valid_work(work)
        if self.value['pending'] is not None or source not in ROLES:raise ValueError('invalid reservation boundary/source')
        if any(self.value['attempted'][k]+work[k]>LIMITS[k] or self.value['by_source'][source][k]+work[k]>SOURCE_LIMITS[source][k] for k in WORK):raise CampaignStop('paused-resource','fixed preflight work ceiling')
        for k in WORK:self.value['attempted'][k]+=work[k];self.value['by_source'][source][k]+=work[k]
        self.value['state']='running';self.value['pending']=dict(source=source,work=deepcopy(work),**pending)
    def reserve_update(self,work,item,index):
        if work['assistant_targets']<=0 or work['evaluation_targets'] or len(item['indices'])!=8 or self.value['attempted_updates']>=40 or index!=self.value['attempted_updates']:raise ValueError('invalid update allocation')
        self._charge(work,item['source'],dict(kind='update',index=index,phase=item['phase'],stratum=item['stratum'],rows=8))
        self.value['attempted_updates']+=1;self.value['attempted_train_rows']+=8;self.publish();self.sync();self.pending_started=time.monotonic()
    def complete_update(self,metric):
        self.sync();pending=self.value['pending']
        if not pending or pending['kind']!='update':raise ValueError('no pending update')
        if not all(__import__('math').isfinite(float(v)) for v in metric.values()):raise ValueError('nonfinite update metric')
        self.value['measurements'].append(dict(**pending,seconds=time.monotonic()-self.pending_started,metrics=metric,telemetry=self.telemetry()))
        self.value['completed_updates']+=1;self.value['pending']=None;self.publish()
    def _complete_evaluation(self):
        if self.value['pending'] is None:return
        if self.value['pending']['kind']!='evaluation':raise ValueError('unfinished optimizer attempt')
        self.sync();self.value['measurements'].append(dict(**self.value['pending'],seconds=time.monotonic()-self.pending_started,telemetry=self.telemetry()));self.value['completed_evaluation_rows']+=1;self.value['pending']=None;self.publish()
    def reserve_evaluation(self,work,source):
        self._complete_evaluation()
        if work['assistant_targets'] or work['evaluation_targets']<=0 or self.value['attempted_evaluation_rows']>=48:raise ValueError('invalid evaluation allocation')
        self._charge(work,source,dict(kind='evaluation',rows=1));self.value['attempted_evaluation_rows']+=1;self.publish();self.sync();self.pending_started=time.monotonic()
    def finish(self,*,error=None):
        if error is None:
            self._complete_evaluation();self.check()
            if self.value['completed_updates']!=40 or self.value['completed_evaluation_rows']!=48 or self.value['pending'] is not None:raise ValueError('incomplete workload cannot PASS')
            from collections import Counter
            actual=Counter((m['source'],m['phase']) for m in self.value['measurements'] if m['kind']=='update')
            expected={(role,'warmup'):n for role,n in zip(ROLES,WARMUPS)}
            expected.update({(role,'measured'):n for role,n in zip(ROLES,MEASURED)})
            evaluation=Counter(m['source'] for m in self.value['measurements'] if m['kind']=='evaluation')
            if actual!=expected or evaluation!={role:16 for role in ROLES}:raise ValueError('source/phase allocation incomplete')
            self.value['state']='PASS_CHILD_PENDING_WATCHDOG'
        else:self.value.update(state='FAILED_INCOMPLETE',error=dict(type=type(error).__name__,reason=str(error)))
        self.publish()


def workload(model,opt,data,plan,ledger,device):
    settings=dict(CONFIG,scheduler=dict(kind='warmup_cosine_updates',warmup_updates=0,peak_lr=6e-5,end_fraction=1.),datasets=[dict(name=role,validation_rows=16,development_split='validation' if role=='chat' else 'exposed-development') for role in ROLES])
    ledger.value['initialization_seconds']=time.monotonic()-ledger.started;ledger.publish()
    for index,item in enumerate(plan['updates']):
        work=train.work_for(data,item['indices'],1);ledger.reserve_update(work,item,index)
        metric=train.update(model,opt,data,item['indices'],settings,index,40,ledger.check,device)
        ledger.complete_update(metric)
    result=train.evaluate(model,EvaluationView(data,plan['validation']),settings,ledger,device)
    ledger.value['validation']=result;ledger.finish();return result


def timing_summary(ledger):
    groups={}
    for measurement in ledger.value['measurements']:
        key=(measurement['kind'],measurement['source'],measurement.get('phase','evaluation'),measurement.get('stratum','fp32'))
        item=groups.setdefault(key,dict(seconds=0.,rows=0,assistant_targets=0,evaluation_targets=0,input_tokens=0,padded_tokens=0))
        item['seconds']+=measurement['seconds'];item['rows']+=measurement['rows']
        for name in ('assistant_targets','evaluation_targets','input_tokens','padded_tokens'):item[name]+=measurement['work'][name]
    result=[]
    for key,item in groups.items():
        item.update(kind=key[0],source=key[1],phase=key[2],stratum=key[3])
        for name in ('assistant_targets','evaluation_targets','input_tokens','padded_tokens'):
            item[name+'_per_second']=item[name]/item['seconds'] if item['seconds']>0 else None
        result.append(item)
    return result


def validate(spec,run):
    train.validate_run_path(spec,run)
    if Path(run).exists():raise ValueError('preflight is nonresumable; existing output directory refused')
    train.stop_check(spec,run)
    if spec.get('state')!='reviewed_for_hardware_preflight' or spec.get('configuration')!=CONFIG:raise ValueError('reviewed fixed preflight configuration required')
    if not set(train.RUNTIME)<=spec['runtime_sha256'].keys():raise ValueError('trainer runtime pins incomplete')
    for name,expected in spec['runtime_sha256'].items():
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or train.digest(path)!=expected:raise ValueError('trainer runtime changed')
    required=('own_base_sft_preflight.py','verify_own_base_sft_preflight.py','reports/own-base-sft-preflight/PROTOCOL.md')
    if set(spec['preflight_code_sha256'])!=set(required):raise ValueError('preflight code/protocol pins required')
    for name,expected in spec['preflight_code_sha256'].items():
        if train.digest(ROOT/name)!=expected:raise ValueError('preflight code changed')
    if [source['name'] for source in spec['datasets']]!=list(ROLES):raise ValueError('exact three admitted sources required')
    for source in spec['datasets']:
        expected_split='validation' if source['name']=='chat' else 'exposed-development'
        if source['development_split']!=expected_split:raise ValueError('source development provenance mismatch')
        admission=train.pinned_json(source['admission']);verification=train.pinned_json(source['verification'])
        if admission.get('training_admitted') is not True or admission.get('dataset_sha256')!=source['receipt']['sha256']:raise ValueError('source not admitted')
        if verification.get('state')!='PASS' or verification.get('dataset_sha256')!=source['receipt']['sha256']:raise ValueError('independent source verification required')
    proof=train.pinned_json(spec['extension_qualification'])
    if proof.get('state')!='PASS' or proof.get('dataset_sha256')!=spec['datasets'][2]['receipt']['sha256'] or proof.get('session_calls')!=4 or proof.get('final_turn')!=2:raise ValueError('qualified four-call final-prefix source required')


def execute(spec_path,run,*,ticket):
    """Future GPU execution only; no default spec, retry or checkpoint export."""
    if ticket.get('watchdog_pid')!=os.getppid() or ticket.get('deadline')-ticket.get('wall_started')!=min(ACTIVE,CALENDAR):raise ValueError('foreground watchdog ticket required')
    started=ticket['monotonic_started'];wall=ticket['wall_started'];os.nice(10);torch.set_num_threads(1)
    spec=json.loads(Path(spec_path).read_text());validate(spec,run);run=Path(run)
    guard=Guard(run,CALENDAR,resume=False);ledger=None;model=None;opt=None
    try:
        identity=dict(spec_sha256=train.digest(spec_path),spec=spec,time_limits=dict(active_seconds=ACTIVE,calendar_seconds=CALENDAR,hard_seconds=min(ACTIVE,CALENDAR)),limits=LIMITS,source_limits=SOURCE_LIMITS,disposable=True)
        ledger=Ledger(run,identity,guard,started=started,wall_started=wall,synchronize=torch.mps.synchronize,telemetry=lambda:dict(rss_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,mps_allocated_bytes=torch.mps.current_allocated_memory(),mps_driver_allocated_bytes=torch.mps.driver_allocated_memory()));ledger.check()
        parent_spec=dict(spec,code_sha256=spec['runtime_sha256'],cpu_rss_limit_bytes=RSS)
        parent,branch,receipt=train.verified_parent(parent_spec);ledger.check()
        data=train.Sources(spec['datasets'],check=ledger.check);plan=selection(data)
        _write(run/'selection.json',plan);ledger.value['selection_sha256']=train.digest(run/'selection.json');ledger.publish();ledger.check()
        torch.manual_seed(20261106);model=GPT2().to('mps');model.load_state_dict(parent['model'],strict=True);del parent
        opt=optimizer_for(model)
        for group in opt.param_groups:group['betas']=(.9,train.BETAS[branch])
        del group
        train.validate_optimizer(opt,0,train.BETAS[branch]);ledger.check()
        workload(model,opt,data,plan,ledger,'mps')
        # No state_dict save/export: later SFT reloads the unchanged selected base.
        del model,opt;model=opt=None;torch.mps.empty_cache()
        ledger.value['disposable_weights_released']=True;ledger.publish();ledger.check()
        for pins in (spec['runtime_sha256'],spec['preflight_code_sha256']):
            for name,expected in pins.items():
                ledger.check()
                if train.digest(ROOT/name)!=expected:raise ValueError('runtime changed during preflight')
        for source in spec['datasets']:
            source_receipt=train.pinned_json(source['receipt']);directory=Path(source['receipt']['path']).parent
            for split in ('train',source['development_split']):
                for suffix in ('inputs.u16','labels.u16','index.jsonl'):
                    ledger.check();path=directory/f'{split}.{suffix}'
                    if train.digest(path)!=source_receipt['outputs'][path.name]['sha256']:raise ValueError('data changed during preflight')
        ledger.check()
        receipt=dict(state='PASS_CHILD_PENDING_WATCHDOG',time_limits=dict(active_seconds=ACTIVE,calendar_seconds=CALENDAR,hard_seconds=min(ACTIVE,CALENDAR)),watchdog_deadline=ticket['deadline'],configuration=CONFIG,runtime_sha256=spec['runtime_sha256'],preflight_code_sha256=spec['preflight_code_sha256'],validation_exercised=True,datasets={s['name']:s['receipt']['sha256'] for s in spec['datasets']},parent=receipt,selection_sha256=train.digest(run/'selection.json'),ledger_sha256=train.digest(run/'preflight-ledger.json'),initialization_seconds=ledger.value['initialization_seconds'],timing=timing_summary(ledger),coverage=plan['coverage'],draw_weighted_target_positions=plan['draw_weighted_target_positions'],disposable_weights_released=True,checkpoint_io_measured=False,capability_verified=False,limits=LIMITS,seconds=time.monotonic()-started)
        _write(run/'hardware-candidate.json',receipt);return receipt
    except BaseException as error:
        if ledger is not None:ledger.finish(error=error)
        raise
    finally:
        if model is not None:del model
        if opt is not None:del opt
        guard.close()


def consume_ticket(fd):
    if fd<3:raise ValueError('internal watchdog pipe required')
    with os.fdopen(fd,'rb') as stream:raw=stream.read(4097)
    if len(raw)>4096:raise ValueError('invalid watchdog ticket size')
    ticket=json.loads(raw)
    if (ticket.get('watchdog_pid')!=os.getppid() or os.getsid(0)!=os.getpid() or
        not isinstance(ticket.get('nonce'),str) or len(ticket['nonce'])!=32 or
        ticket.get('deadline')-ticket.get('wall_started')!=min(ACTIVE,CALENDAR) or time.time()>=ticket['deadline']):
        raise ValueError('invalid/stale foreground watchdog ticket')
    return ticket


def watch_owned_child(command_factory,ticket,*,grace_seconds=10.,kill_margin=2.):
    """Foreground wait; only the newly created child's session/process group."""
    deadline=ticket['deadline'];mono_deadline=ticket['monotonic_started']+(deadline-ticket['wall_started'])
    def remaining():return min(deadline-time.time(),mono_deadline-time.monotonic())
    if not 0<kill_margin<grace_seconds<remaining():raise ValueError('watchdog grace must fit inside original deadline')
    read_fd,write_fd=os.pipe();child=None;timed_out=False;interrupted=False
    try:
        child=subprocess.Popen(command_factory(read_fd),pass_fds=(read_fd,),close_fds=True,start_new_session=True)
        os.close(read_fd);read_fd=None
        with os.fdopen(write_fd,'wb') as stream:stream.write(train.canonical(ticket))
        write_fd=None
        try:
            child.wait(timeout=max(.001,remaining()-grace_seconds))
        except subprocess.TimeoutExpired:timed_out=True
        except KeyboardInterrupt:interrupted=True
        if timed_out or interrupted:
            # This PGID was created by start_new_session for this child alone.
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:child.wait(timeout=max(.001,remaining()-kill_margin))
            except subprocess.TimeoutExpired:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait(timeout=max(.001,remaining()))
        return dict(child_pid=child.pid,returncode=child.returncode,timed_out=timed_out,interrupted=interrupted,
                    state='FAILED_TIMEOUT' if timed_out else 'FAILED_INTERRUPTED' if interrupted else 'CHILD_EXITED',
                    deadline=deadline,finished=time.time(),within_deadline=remaining()>0,elapsed_seconds=time.monotonic()-ticket['monotonic_started'])
    finally:
        if read_fd is not None:os.close(read_fd)
        if write_fd is not None:os.close(write_fd)
        if child is not None and child.poll() is None:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            # Reap only this owned child. No retry, launch agent or other worker.
            try:child.wait(timeout=max(.001,remaining()))
            except subprocess.TimeoutExpired:pass


def foreground(spec_path,run):
    wall=time.time();started=time.monotonic();ticket=dict(watchdog_pid=os.getpid(),nonce=uuid.uuid4().hex,wall_started=wall,monotonic_started=started,deadline=wall+min(ACTIVE,CALENDAR))
    spec_path=Path(spec_path).resolve();run=Path(run);spec=json.loads(spec_path.read_text())
    train.validate_run_path(spec,run)
    if run.exists():raise ValueError('consumed or existing preflight directory')
    result=watch_owned_child(lambda fd:[sys.executable,str(Path(__file__).resolve()),str(spec_path),str(run),'--execute-reviewed','--worker-fd',str(fd)],ticket)
    if run.is_symlink():raise ValueError('unexpected output alias')
    run.mkdir(exist_ok=True)
    result.update(nonce=ticket['nonce'],started=wall,spec_sha256=train.digest(spec_path),scope='Only this owned foreground child/process group; no retry')
    _write(run/'watchdog.json',result)
    if result['timed_out'] or result['interrupted'] or result['returncode']!=0 or not result['within_deadline']:
        return dict(state='FAILED_INCOMPLETE',watchdog=result)
    candidate=run/'hardware-candidate.json'
    if not candidate.exists():return dict(state='FAILED_INCOMPLETE',reason='child supplied no hardware candidate')
    if any((run/name).is_symlink() for name in ('hardware-candidate.json','preflight-ledger.json','selection.json')):raise ValueError('child proof artifact alias')
    receipt=json.loads(candidate.read_text())
    if receipt.get('state')!='PASS_CHILD_PENDING_WATCHDOG' or receipt.get('disposable_weights_released') is not True:
        raise ValueError('child candidate incomplete')
    if (receipt.get('ledger_sha256')!=train.digest(run/'preflight-ledger.json') or
        receipt.get('selection_sha256')!=train.digest(run/'selection.json') or
        receipt.get('runtime_sha256')!=spec['runtime_sha256'] or receipt.get('preflight_code_sha256')!=spec['preflight_code_sha256'] or
        receipt.get('configuration')!=CONFIG or receipt.get('validation_exercised') is not True or
        receipt.get('time_limits')!=dict(active_seconds=ACTIVE,calendar_seconds=CALENDAR,hard_seconds=min(ACTIVE,CALENDAR)) or
        receipt.get('watchdog_deadline')!=ticket['deadline'] or not 0<=receipt.get('seconds',float('inf'))<min(ACTIVE,CALENDAR) or
        receipt.get('parent')!=spec['parent'] or receipt.get('datasets')!={s['name']:s['receipt']['sha256'] for s in spec['datasets']}):
        raise ValueError('child proof hashes/configuration/ancestry mismatch')
    ledger=json.loads((run/'preflight-ledger.json').read_text());signature=ledger.pop('sha256')
    if (signature!=digest_value(ledger) or ledger.get('state')!='PASS_CHILD_PENDING_WATCHDOG' or
        ledger.get('completed_updates')!=40 or ledger.get('completed_evaluation_rows')!=48 or ledger.get('pending') is not None or
        not 0<=ledger.get('elapsed_seconds',float('inf'))<min(ACTIVE,CALENDAR) or
        ledger.get('identity',{}).get('time_limits')!=receipt['time_limits'] or
        ledger.get('identity',{}).get('spec_sha256')!=train.digest(spec_path) or ledger['identity'].get('spec')!=spec):
        raise ValueError('child ledger proof incomplete')
    receipt.update(state='PASS',watchdog_sha256=train.digest(run/'watchdog.json'),candidate_sha256=train.digest(candidate))
    if time.time()>=ticket['deadline'] or time.monotonic()-started>=min(ACTIVE,CALENDAR):return dict(state='FAILED_INCOMPLETE',reason='deadline before final receipt')
    _write(run/'hardware-receipt.json',receipt);return receipt


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('spec',type=Path);parser.add_argument('run',type=Path);parser.add_argument('--execute-reviewed',action='store_true');parser.add_argument('--worker-fd',type=int,help=argparse.SUPPRESS);args=parser.parse_args()
    if not args.execute_reviewed:parser.error('candidate runner only; root review and explicit activation required')
    if args.worker_fd is not None:result=execute(args.spec,args.run,ticket=consume_ticket(args.worker_fd))
    else:result=foreground(args.spec,args.run)
    print(json.dumps(result))
    raise SystemExit(0 if result['state'] in ('PASS','PASS_CHILD_PENDING_WATCHDOG') else 1)
