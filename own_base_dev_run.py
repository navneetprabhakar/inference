"""Explicit-spec foreground development inference. No default spec or activation.

CLI production is MPS-only and exact-own-candidate-only. Generic budget/decoder
helpers are independently testable with tiny CPU fixtures; no scripted decoder
or alternate candidate route is exposed by the CLI.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
import stat

ROOT=Path(__file__).resolve().parent
CORPORA=(('primary_tools','data/own-base-tool-dev-rubrics-v4',422,583),
         ('four_call_sessions','data/own-base-tool-session-dev-rubrics-v2',8,24),
         ('public_conversation','reports/own-base-public-conversation-dev-v1',12,25))
RUNTIME=('own_base_dev_run.py','own_base_dev_eval.py','own_base_chat.py','own_base_sft_export.py',
         'gpt2.py','guards.py','tokenizer.py','dialogue.py','tools/__init__.py')
RESERVED_BYTES=1024**2
EMERGENCY_BYTES=512*1024
TERMINAL_BYTES=128*1024

CAPS=('wall_seconds','heartbeat_seconds','termination_grace_seconds','max_frames',
      'max_reserved_generation_tokens','max_reserved_input_positions','max_reserved_attention_cells',
      'max_actual_generated_tokens','max_rss_bytes','max_swap_growth_bytes','min_free_disk_bytes',
      'max_output_bytes','max_thermal_state')

class RunnerStop(RuntimeError):pass

def checksum(path,check=lambda:None):
    h=hashlib.sha256()
    with open(path,'rb') as stream:
        for chunk in iter(lambda:stream.read(1024**2),b''):
            check();h.update(chunk)
    return h.hexdigest()

def atomic(path,value,max_total_bytes=None):
    payload=(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n').encode()
    if max_total_bytes is not None and sum(p.stat().st_size for p in path.parent.iterdir() if p.is_file())+len(payload)>max_total_bytes:
        raise RunnerStop('artifact output cap including atomic temporary')
    temp=path.with_suffix(path.suffix+'.tmp')
    with temp.open('wb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)

def persist_emergency_turn(out,chat,error,max_output_bytes,*,record_start=0):
    """Save ordinary-exception state before larger reports can consume space.

    Uses fixed headroom, including the atomic temporary. This is not a hard-kill
    recovery mechanism. Source records are preserved, never reconstructed.
    """
    trace=chat.session.trace;decisions=chat.session.decisions
    record=chat.turn_records[-1] if len(chat.turn_records)>record_start else None
    payload=dict(state='incomplete',kind='ordinary_exception_current_turn',
                 error_type=type(error).__name__,error=str(error)[:4096],
                 error_text_truncated=len(str(error))>4096,
                 current_turn_record=record,authoritative_session_trace=trace,
                 authoritative_session_decisions=decisions,omitted=[],hard_kill_recovery=False)
    def fits(value):return len((json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n').encode())<=EMERGENCY_BYTES
    if not fits(payload):
        payload['current_turn_record']=None
        payload['omitted']=['current_turn_record: exceeds emergency payload cap; includes raw frames/user/history']
    if not fits(payload):
        def identity(value):
            raw=json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
            return dict(call_id=value.get('call_id'),name=value.get('name'),ok=value.get('ok'),
                        source=value.get('source'),schema_version=value.get('schema_version'),
                        record_sha256=hashlib.sha256(raw).hexdigest())
        payload['authoritative_session_trace']=None;payload['authoritative_session_decisions']=None
        payload['tool_record_identities']=[identity(value) for value in trace]
        payload['decision_identities']=[identity(value) for value in decisions]
        payload['omitted']+=['full tool records and decisions: exceeds emergency payload cap; identifiers/hashes retained']
    if not fits(payload):
        # A corrupted/unbounded external session cannot be squeezed silently into
        # the fixed reserve. Record explicit count/aggregate hashes, not fake rows.
        for field in ('tool_record_identities','decision_identities'):
            values=payload.pop(field)
            payload[field+'_summary']=dict(count=len(values),sha256=hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest(),first=values[:8],last=values[-8:])
        payload['omitted']+=['middle identity entries: exceeds cap; counts, aggregate hashes and edge identifiers retained']
    if not fits(payload):raise RunnerStop('minimal emergency payload exceeds fixed cap')
    atomic(out/'emergency-turn.json',payload,max_total_bytes=max_output_bytes-2*TERMINAL_BYTES)
    return payload


def write_terminal(out,filename,payload,max_output_bytes):
    if len((json.dumps(payload,ensure_ascii=False,allow_nan=False)+'\n').encode())>TERMINAL_BYTES:
        raise RunnerStop('terminal receipt exceeds allocated headroom')
    atomic(out/filename,payload,max_total_bytes=max_output_bytes)


def incomplete_terminal(out,error,counters,pending,max_output_bytes):
    payload=dict(state='incomplete',error_type=type(error).__name__,error=str(error)[:4096],
                 emergency_receipt=(out/'emergency-turn.json').exists(),counters=counters,
                 inflight_frame=pending,planned_sessions=442,planned_turns=632,aggregate_score=None)
    write_terminal(out,'worker-terminal.json',payload,max_output_bytes)
    return payload


def validate_spec(spec):
    if type(spec)!=dict or set(spec)!={'schema','candidate','corpora','runtime_sha256','budgets','output','device','dtype','stop_paths'} or spec['schema']!=1:
        raise ValueError('exact explicit runner schema required')
    if spec['device']!='mps' or spec['dtype']!='float32':raise ValueError('only explicit MPS FP32 evaluation supported')
    if type(spec['budgets'])!=dict or set(spec['budgets'])!=set(CAPS):raise ValueError('all budgets must be explicitly supplied')
    for key,value in spec['budgets'].items():
        if type(value)!=int or value<=( -1 if key=='max_thermal_state' else 0):raise ValueError('invalid explicit budget '+key)
    b=spec['budgets']
    if b['max_thermal_state']>1 or b['min_free_disk_bytes']<20*1024**3:raise ValueError('resource safety thresholds cannot be weakened')
    if b['max_output_bytes']<=2*1024**2:raise ValueError('output cap must include terminal/report headroom')
    if b['heartbeat_seconds']>b['wall_seconds'] or b['termination_grace_seconds']>30:raise ValueError('invalid watchdog bounds')
    out=Path(spec['output'])
    if out!=out.resolve() or out.parent!=ROOT/'runs' or not re.fullmatch(r'own-base-dev-[a-z0-9-]+',out.name):raise ValueError('output must be a fresh canonical runs child')
    if set(spec['candidate'])!={'manifest','manifest_sha256'}:raise ValueError('exact candidate manifest pin required')
    candidate=Path(spec['candidate']['manifest'])
    if candidate!=candidate.resolve() or candidate.parent.parent!=ROOT/'own-base-candidates':raise ValueError('candidate outside canonical export directory')
    if not isinstance(spec['stop_paths'],list) or not spec['stop_paths']:raise ValueError('explicit inherited STOP paths required')
    required={str(ROOT/'runs/STOP'),str(ROOT/'runs/own-base-foundation-01/STOP'),str(out/'STOP')}
    if not required<=set(spec['stop_paths']):raise ValueError('required STOP inheritance missing')
    for item in spec['stop_paths']:
        p=Path(item)
        if p!=p.resolve() or not p.is_relative_to(ROOT):raise ValueError('STOP path must be canonical under own root')
    if set(spec['runtime_sha256'])!=set(RUNTIME):raise ValueError('complete runtime pins required')
    if not isinstance(spec['corpora'],list) or len(spec['corpora'])!=3:raise ValueError('exactly three frozen corpora required')
    for item,(name,path,sessions,turns) in zip(spec['corpora'],CORPORA):
        if set(item)!={'id','file_sha256','canonical_sha256','receipt_sha256','freeze_sha256','sessions','turns'} or item['id']!=name or item['sessions']!=sessions or item['turns']!=turns:raise ValueError('corpus identity/denominator mismatch')
    hashes=[spec['candidate']['manifest_sha256'],*spec['runtime_sha256'].values()]
    hashes += [item[k] for item in spec['corpora'] for k in ('file_sha256','canonical_sha256','receipt_sha256','freeze_sha256')]
    if any(not isinstance(h,str) or not re.fullmatch('[a-f0-9]{64}',h) for h in hashes):raise ValueError('invalid SHA256 pin')
    return deepcopy(spec)

class Journal:
    def __init__(self,path,max_bytes):
        self.path=Path(path);self.limit=max_bytes;self.written=0;self.file=self.path.open('xb')
    def emit(self,event,durable=True,**data):
        payload=(json.dumps(dict(event=event,monotonic=time.monotonic(),wall=time.time(),**data),ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode()
        if self.written+len(payload)>self.limit or sum(p.stat().st_size for p in self.path.parent.iterdir() if p.is_file())+len(payload)>self.limit:raise RunnerStop('journal output budget exhausted')
        self.file.write(payload);self.file.flush();self.written+=len(payload)
        if durable:os.fsync(self.file.fileno())
    def close(self):self.file.close()

class Budget:
    def __init__(self,caps,journal):
        self.caps=caps;self.journal=journal
        self.counts=dict(frames=0,reserved_generation_tokens=0,reserved_input_positions=0,reserved_attention_cells=0,
                         actual_generated_tokens=0,actual_input_positions=0,actual_attention_cells=0,completed_forward_seconds=0.0)
        self.pending=None
    def reserve(self,prefix):
        if self.pending is not None:raise RunnerStop('unfinished prior frame')
        p=len(prefix)
        if not 1<=p<=768:raise RunnerStop('frame does not reserve full 256-token reply')
        charges=dict(frames=1,reserved_generation_tokens=256,
                     reserved_input_positions=sum(p+i for i in range(256)),
                     reserved_attention_cells=sum((p+i)**2 for i in range(256)))
        proposed=dict(self.counts)
        for key,value in charges.items():
            proposed[key]+=value
            if proposed[key]>self.caps['max_'+key]:raise RunnerStop('attempt budget exhausted: '+key)
        self.journal.emit('frame_reserved',prefix_ids=list(prefix),charges=charges,counters=proposed)
        self.counts=proposed;self.pending=dict(frame=self.counts['frames'],generated=0)
    def before_step(self,length):
        if self.pending is None or self.pending['generated']>=256:raise RunnerStop('decoder frame budget violation')
        if self.counts['actual_generated_tokens']>=self.caps['max_actual_generated_tokens']:raise RunnerStop('actual generation cap')
        # This attempt is durable only at frame boundaries; a hard kill may leave
        # an in-flight forward unknown. Reserved worst-case charges remain spent.
        self.pending['step_started']=time.monotonic()
        self.journal.emit('forward_started',durable=False,frame=self.pending['frame'],input_positions=length)
    def after_step(self,length,token):
        self.counts['completed_forward_seconds']+=time.monotonic()-self.pending.pop('step_started')
        self.counts['actual_generated_tokens']+=1;self.counts['actual_input_positions']+=length;self.counts['actual_attention_cells']+=length**2
        self.pending['generated']+=1
        self.journal.emit('token_observed',durable=False,frame=self.pending['frame'],token=token,counters=self.counts)
    def finish(self,output):
        self.journal.emit('frame_completed',frame=self.pending['frame'],generated_ids=output,counters=self.counts)
        self.pending=None

def bounded_greedy(model,prefix,reply_budget,guard,budget):
    """Actual argmax decoder, matching evaluate.greedy; no fallback or repair."""
    import torch
    from tokenizer import EOT
    if reply_budget!=256:raise RunnerStop('fixed reply budget changed')
    guard.check();budget.reserve(prefix);ids=list(prefix);output=[]
    with torch.inference_mode():
        for _ in range(256):
            guard.check();budget.before_step(len(ids))
            row=torch.tensor([ids],device=next(model.parameters()).device)
            token=int(model(row)[0,-1].argmax().item())
            budget.after_step(len(ids),token);output.append(token)
            if token==EOT:break
            ids.append(token)
    budget.finish(output);return output

class RunGuard:
    def __init__(self,spec,path,started,journal):
        self.spec=spec;self.path=path;self.started=started;self.journal=journal;self.last=-float('inf');self.last_heartbeat=-float('inf')
        from guards import swap_mib
        self.baseline_swap=swap_mib()
    def check(self,force=False):
        b=self.spec['budgets']
        if time.time()-self.started>=b['wall_seconds']:raise RunnerStop('wall deadline')
        if any(Path(p).exists() for p in self.spec['stop_paths']):raise RunnerStop('explicit STOP')
        # Heartbeat is best effort, not a claim that an interrupted forward completed.
        if time.monotonic()-self.last_heartbeat>=.25:
            (self.path/'heartbeat').write_text(str(time.monotonic()));self.last_heartbeat=time.monotonic()
        if force or time.monotonic()-self.last>=1:
            self.last=time.monotonic()
            from guards import thermal,swap_mib
            state=thermal();swap=swap_mib();rss=group_rss(os.getpgrp())
            if state>b['max_thermal_state'] or state not in range(4):raise RunnerStop('thermal threshold')
            if (swap-self.baseline_swap)*1024**2>b['max_swap_growth_bytes'] or rss>b['max_rss_bytes']:raise RunnerStop('memory/swap threshold')
            check_storage(self.spec)
            self.journal.emit('resources',durable=False,rss_bytes=rss,thermal=state,swap_growth_bytes=(swap-self.baseline_swap)*1024**2)

def group_rss(pgid,timeout=2):
    output=subprocess.check_output(['ps','-axo','pgid=,rss='],text=True,timeout=timeout)
    return sum(int(parts[1])*1024 for line in output.splitlines() if len(parts:=line.split())==2 and int(parts[0])==pgid)

def apple_thermal():
    """OS-only parent telemetry: do not import Torch into the watchdog."""
    import ctypes
    ctypes.CDLL('/System/Library/Frameworks/Foundation.framework/Foundation')
    objc=ctypes.CDLL('/usr/lib/libobjc.A.dylib')
    objc.objc_getClass.argtypes=[ctypes.c_char_p];objc.objc_getClass.restype=ctypes.c_void_p
    objc.sel_registerName.argtypes=[ctypes.c_char_p];objc.sel_registerName.restype=ctypes.c_void_p
    address=ctypes.cast(objc.objc_msgSend,ctypes.c_void_p).value
    send=ctypes.CFUNCTYPE(ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p)(address)
    integer=ctypes.CFUNCTYPE(ctypes.c_long,ctypes.c_void_p,ctypes.c_void_p)(address)
    process=send(objc.objc_getClass(b'NSProcessInfo'),objc.sel_registerName(b'processInfo'))
    return integer(process,objc.sel_registerName(b'thermalState'))


def check_storage(spec):
    out=Path(spec['output']);b=spec['budgets']
    if shutil.disk_usage(out).free<b['min_free_disk_bytes']:raise RunnerStop('free disk floor')
    if sum(p.stat().st_size for p in out.iterdir() if p.is_file())>b['max_output_bytes']:raise RunnerStop('output bytes cap')

def read_inputs(spec,check):
    from own_base_dev_eval import prepare,fingerprint
    for relative,expected in spec['runtime_sha256'].items():
        if checksum(ROOT/relative,check)!=expected:raise RunnerStop('runtime pin mismatch: '+relative)
    result=[]
    for item,(name,relative,sessions,turns) in zip(spec['corpora'],CORPORA):
        base=ROOT/relative;cases_path=base/'cases.json';freeze_path=base/'freeze.json'
        receipt_path=freeze_path if name=='public_conversation' else base/'receipt.json'
        for p,key in ((cases_path,'file_sha256'),(receipt_path,'receipt_sha256'),(freeze_path,'freeze_sha256')):
            if checksum(p,check)!=item[key]:raise RunnerStop('corpus artifact pin mismatch')
        cases=json.loads(cases_path.read_text());prepare(cases,item['canonical_sha256'])
        if len(cases)!=sessions or sum(len(c['turns']) for c in cases)!=turns:raise RunnerStop('planned corpus denominator changed')
        receipt=json.loads(receipt_path.read_text())
        if name=='public_conversation':
            if receipt['cases_sha256']!=fingerprint(cases) or receipt['case_file_sha256']!=item['file_sha256']:raise RunnerStop('public freeze binding mismatch')
        elif receipt['cases_canonical_sha256']!=fingerprint(cases) or receipt['cases_file_sha256']!=item['file_sha256'] or receipt['freeze_sha256']!=item['freeze_sha256']:
            raise RunnerStop('tool receipt binding mismatch')
        result.append((name,cases))
    return result

def worker(spec_path,expected_sha,ticket):
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[name]='1'
    os.environ['TOKENIZERS_PARALLELISM']='false'
    if checksum(spec_path)!=expected_sha:raise RunnerStop('spec changed before worker')
    spec=validate_spec(json.loads(Path(spec_path).read_text()));out=Path(spec['output'])
    launch_meta=json.loads((out/'launch.json').read_text())
    if (launch_meta['parent_pid']!=os.getppid() or launch_meta['nonce']!=ticket['nonce'] or ticket['spec_sha256']!=expected_sha or abs(ticket['deadline']-ticket['wall_started']-spec['budgets']['wall_seconds'])>1e-5):raise RunnerStop('worker must belong to its recorded foreground watchdog')
    started=launch_meta['started']
    journal=Journal(out/'events.jsonl',spec['budgets']['max_output_bytes']-RESERVED_BYTES)
    lock=(ROOT/'runs/mps.lock').open('a+')
    budget=Budget(spec['budgets'],journal)
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        guard=RunGuard(spec,out,started,journal);guard.check(force=True)
        inputs=read_inputs(spec,guard.check)
        from own_base_sft_export import verify_candidate_manifest,load_candidate
        candidate=spec['candidate'];manifest=verify_candidate_manifest(candidate['manifest'],candidate['manifest_sha256'],check=guard.check)
        required_source_stop=str(Path(manifest['source']['run'])/'STOP')
        if required_source_stop not in spec['stop_paths']:raise RunnerStop('SFT source STOP inheritance missing')
        guard.check(force=True)
        state,loaded_manifest=load_candidate(candidate['manifest'],candidate['manifest_sha256'],check=guard.check)
        if manifest!=loaded_manifest:raise RunnerStop('candidate changed while loading')
        import torch
        from gpt2 import GPT2,Config
        from tokenizer import load
        from own_base_chat import Chat
        from tools import FixtureSession
        from own_base_dev_eval import run,EvaluationAborted
        if not torch.backends.mps.is_available():raise RunnerStop('MPS unavailable; no device fallback')
        torch.set_num_threads(1)
        model=GPT2(Config(**manifest['model_config']));model.load_state_dict(state,strict=True);del state
        model=model.to(device='mps',dtype=torch.float32).eval();tok=load();guard.check(force=True)
        journal.emit('candidate_loaded',manifest_sha256=candidate['manifest_sha256'],planned_sessions=442,planned_turns=632)
        class LoggedSession(FixtureSession):
            def propose(self,raw,**kwargs):
                journal.emit('tool_intent',raw=raw)
                try:record=super().propose(raw,**kwargs)
                except Exception as error:
                    journal.emit('tool_refusal',error_type=type(error).__name__,error=str(error));raise
                journal.emit('tool_observed',record=record,decision=self.decisions[-1]);return record
        class LoggedChat(Chat):
            def turn(self,user,**policy):
                record_start=len(self.turn_records)
                try:
                    journal.emit('turn_started',user=user,policy=policy)
                    result=super().turn(user,**policy)
                    journal.emit('turn_completed',result=result);return result
                except Exception as error:
                    # This precedes journal/full-corpus attempts: the real broker
                    # may have executed even when recording its result failed.
                    persist_emergency_turn(out,self,error,spec['budgets']['max_output_bytes'],record_start=record_start)
                    try:
                        if len(self.turn_records)>record_start:journal.emit('turn_interrupted',record=self.turn_records[-1])
                    except Exception:pass
                    raise
        reports=[]
        for name,cases in inputs:
            def factory(case):
                journal.emit('session_started',corpus=name,case_id=case['id'])
                chat=LoggedChat(model,tok,guard,generate=lambda p,b:bounded_greedy(model,p,b,guard,budget));chat.session=LoggedSession();return chat
            try:report=run(cases,expected_sha256=spec['corpora'][len(reports)]['canonical_sha256'],chat_factory=factory)
            except EvaluationAborted as error:
                try:atomic(out/(name+'.incomplete.json'),error.report,spec['budgets']['max_output_bytes']-RESERVED_BYTES)
                except RunnerStop:pass  # Emergency receipt already saved before evaluator unwound.
                raise
            reports.append(dict(corpus=name,report=report));atomic(out/(name+'.json'),report,spec['budgets']['max_output_bytes']-RESERVED_BYTES);guard.check(force=True)
        journal.emit('evaluation_completed',counters=budget.counts)
        write_terminal(out,'worker-terminal.json',dict(state='completed_development_not_release',planned_sessions=442,planned_turns=632,
               completed_sessions=sum(r['report']['summary']['sessions']['total'] for r in reports),
               completed_turns=sum(r['report']['summary']['turns']['total'] for r in reports),
               corpora=[dict(corpus=r['corpus'],summary=r['report']['summary']) for r in reports],
               counters=budget.counts,seconds=time.time()-started,manual_judgments='pending_not_automatic_pass',training_admitted=False),spec['budgets']['max_output_bytes'])
        return 0
    except BaseException as error:
        try:journal.emit('worker_aborted',error_type=type(error).__name__,error=str(error),counters=budget.counts,inflight_frame=budget.pending)
        except Exception:pass
        incomplete_terminal(out,error,budget.counts,budget.pending,spec['budgets']['max_output_bytes'])
        return 2
    finally:lock.close();journal.close()

def make_ticket(seconds,spec_sha='test-fixture'):
    wall=time.time();mono=time.monotonic()
    return dict(watchdog_pid=os.getpid(),nonce=uuid.uuid4().hex,wall_started=wall,
                monotonic_started=mono,deadline=wall+seconds,spec_sha256=spec_sha)


def remaining(ticket):
    return min(ticket['deadline']-time.time(),ticket['monotonic_started']+
               ticket['deadline']-ticket['wall_started']-time.monotonic())


def consume_ticket(fd):
    if fd is None or fd<3 or not stat.S_ISFIFO(os.fstat(fd).st_mode):raise RunnerStop('inherited watchdog pipe required')
    with os.fdopen(fd,'rb') as stream:raw=stream.read(4097)
    if len(raw)>4096:raise RunnerStop('oversized watchdog ticket')
    ticket=json.loads(raw)
    if (ticket.get('watchdog_pid')!=os.getppid() or os.getsid(0)!=os.getpid() or
        not isinstance(ticket.get('nonce'),str) or not re.fullmatch('[a-f0-9]{32}',ticket['nonce']) or
        remaining(ticket)<=0):raise RunnerStop('invalid/stale watchdog ticket')
    return ticket


def supervise(command_factory,out,*,ticket,heartbeat_seconds,grace_seconds,max_rss_bytes,check=lambda pid,seconds:None):
    """Only this owned child/group; all termination and reap use one deadline."""
    kill_margin=min(.5,grace_seconds/2)
    if not 0<kill_margin<grace_seconds<remaining(ticket):raise RunnerStop('termination grace must fit inside original deadline')
    read_fd,write_fd=os.pipe();process=None;reason=None
    stdout=(out/'worker.stdout').open('xb');stderr=(out/'worker.stderr').open('xb')
    try:
        process=subprocess.Popen(command_factory(read_fd),pass_fds=(read_fd,),close_fds=True,
                                 start_new_session=True,stdout=stdout,stderr=stderr)
        os.close(read_fd);read_fd=None
        with os.fdopen(write_fd,'wb') as stream:stream.write(json.dumps(ticket).encode())
        write_fd=None
        while process.poll() is None:
            try:
                left=remaining(ticket)
                if left<=grace_seconds:raise RunnerStop('watchdog wall deadline with reserved termination grace')
                check(process.pid,left-grace_seconds)
                if group_rss(process.pid,timeout=min(.5,max(.01,remaining(ticket)-grace_seconds)))>max_rss_bytes:raise RunnerStop('watchdog process-group RSS cap')
                heartbeat=out/'heartbeat'
                last=heartbeat.stat().st_mtime if heartbeat.exists() else ticket['wall_started']
                if time.time()-last>=heartbeat_seconds:raise RunnerStop('watchdog heartbeat timeout')
            except BaseException as error:
                reason=str(error) or type(error).__name__;break
            time.sleep(min(.1,max(0,remaining(ticket)-grace_seconds)))
        if reason is not None:
            try:os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:process.wait(timeout=max(.001,min(grace_seconds-kill_margin,remaining(ticket)-kill_margin)))
            except subprocess.TimeoutExpired:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                try:process.wait(timeout=max(.001,remaining(ticket)))
                except subprocess.TimeoutExpired:reason+='; owned child reap incomplete'
        else:process.wait(timeout=max(.001,remaining(ticket)))
        return dict(exit_code=process.returncode,watchdog_reason=reason,seconds=time.monotonic()-ticket['monotonic_started'],
                    within_deadline=remaining(ticket)>0,child_pid=process.pid,
                    hard_stop_inflight_state='unknown_until_durable_events_reconciled' if reason else None)
    finally:
        if read_fd is not None:os.close(read_fd)
        if write_fd is not None:os.close(write_fd)
        if process is not None and process.poll() is None:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            try:process.wait(timeout=max(.001,remaining(ticket)))
            except subprocess.TimeoutExpired:pass
        stdout.close();stderr.close()


def launch(path,expected):
    wall=time.time();mono=time.monotonic()
    path=Path(path)
    if not path.is_file() or path.stat().st_size>1024**2:raise ValueError('bounded regular spec file required')
    if checksum(path)!=expected:raise ValueError('exact mandatory spec SHA mismatch')
    spec=validate_spec(json.loads(path.read_text()));out=Path(spec['output'])
    ticket=make_ticket(spec['budgets']['wall_seconds'],expected)
    ticket.update(wall_started=wall,monotonic_started=mono,deadline=wall+spec['budgets']['wall_seconds'])
    if remaining(ticket)<=spec['budgets']['termination_grace_seconds']:raise RunnerStop('deadline consumed during initial spec verification')
    out.mkdir(exist_ok=False)
    atomic(out/'spec.json',spec);atomic(out/'launch.json',dict(started=wall,parent_pid=os.getpid(),nonce=ticket['nonce'],spec_sha256=expected,planned_sessions=442,planned_turns=632))
    try:
        # Parent reads OS telemetry independently of the possibly hung worker.
        def read_swap(timeout):
            value=subprocess.check_output(['sysctl','-n','vm.swapusage'],text=True,timeout=timeout)
            match=re.search(r'used = ([\d.]+)([KMG])',value)
            if not match:raise RunnerStop('watchdog swap telemetry unavailable')
            return float(match[1])*{'K':1024,'M':1024**2,'G':1024**3}[match[2]]
        baseline=read_swap(min(.5,max(.01,remaining(ticket)-spec['budgets']['termination_grace_seconds'])))
        last_sample=-float('inf')
        def parent_check(pid,available):
            nonlocal last_sample
            if any(Path(p).exists() for p in spec['stop_paths']):raise RunnerStop('STOP observed by watchdog')
            check_storage(spec)
            if time.monotonic()-last_sample>=1:
                last_sample=time.monotonic();state=apple_thermal()
                if state not in range(4) or state>spec['budgets']['max_thermal_state']:raise RunnerStop('watchdog thermal threshold')
                if read_swap(min(.5,max(.01,available)))-baseline>spec['budgets']['max_swap_growth_bytes']:raise RunnerStop('watchdog swap threshold')
        command=lambda fd:[sys.executable,str(Path(__file__)), '_worker',str(path.resolve()),'--expected-spec-sha256',expected,'--worker-fd',str(fd)]
        result=supervise(command,out,ticket=ticket,heartbeat_seconds=spec['budgets']['heartbeat_seconds'],grace_seconds=spec['budgets']['termination_grace_seconds'],max_rss_bytes=spec['budgets']['max_rss_bytes'],check=parent_check)
        terminal_path=out/'worker-terminal.json';terminal=json.loads(terminal_path.read_text()) if terminal_path.exists() else None
        completed=result['exit_code']==0 and not result['watchdog_reason'] and result['within_deadline'] and terminal and terminal.get('state')=='completed_development_not_release' and terminal.get('completed_sessions')==442 and terminal.get('completed_turns')==632 and remaining(ticket)>0
        write_terminal(out,'terminal.json',dict(state='completed_development_not_release' if completed else 'incomplete',watchdog=result,
               worker_terminal=terminal,aggregate_score=None if not completed else 'see_fixed_denominator_corpus_reports',manual_judgments='pending_not_automatic_pass',training_admitted=False),spec['budgets']['max_output_bytes'])
        return 0 if completed else 2
    except BaseException as error:
        write_terminal(out,'terminal.json',dict(state='incomplete',error_type=type(error).__name__,error=str(error)[:4096],aggregate_score=None,planned_sessions=442,planned_turns=632),spec['budgets']['max_output_bytes'])
        return 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('run','_worker'));parser.add_argument('spec');parser.add_argument('--expected-spec-sha256',required=True)
    parser.add_argument('--worker-fd',type=int)
    args=parser.parse_args()
    if args.mode=='_worker' and os.getpgrp()!=os.getpid():raise SystemExit('worker requires foreground watchdog process group')
    raise SystemExit(worker(args.spec,args.expected_spec_sha256,consume_ticket(args.worker_fd)) if args.mode=='_worker' else launch(args.spec,args.expected_spec_sha256))
