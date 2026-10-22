"""Bounded two-phase teacher generation. No student imports or operations."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import threading
import time
from types import SimpleNamespace
from jsonschema import Draft202012Validator
from slm.teacher.cli import OVERRIDES,clean_environment
from slm.teacher.sol import parse_sol_events

ROOT=Path(__file__).resolve().parent
EXE='/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex'
lock=threading.Lock();usage=Counter();cancel=threading.Event()

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    temp=p.with_suffix(p.suffix+'.tmp');temp.write_text(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n');temp.replace(p)

def request(index,phase,batch,first,start):
    if cancel.is_set():raise RuntimeError('Another request stopped; no new dispatch')
    folder=ROOT/f'batch-{index:02d}-turn{phase}';folder.mkdir()
    schema=dict(type='object',properties={r['id']:dict(type='object',properties={'reply':{'type':'string'}},
          required=['reply'],additionalProperties=False) for r in batch},required=[r['id'] for r in batch],additionalProperties=False)
    save(folder/'schema.json',schema)
    packets=[]
    for r in batch:
        messages=[dict(role='user',content=r['users'][0])]
        if phase==2:messages += [dict(role='assistant',content=first[r['id']]['reply']),dict(role='user',content=r['users'][1])]
        packets.append(dict(id=r['id'],messages=messages,reference=r['oracle_notes'][phase-1],word_limit=r['wordcaps'][phase-1]))
    prompt=('Produce English conversation training demonstrations. Each scenario is independent. Return ONLY the next assistant reply to its actual last user message. '
       'Use only that scenario\'s visible conversation. Never transfer names, facts or assumptions from another scenario. '
       'The reference is a correctness rubric derived from this scenario, not additional hidden facts: preserve its meaning while writing naturally. '
       'Keep factual and yes/no decisions consistent; if people exceed seats the answer to whether all fit is NO. '
       'For arithmetic, show the answer concisely and verify it against the reference. '
       'For ambiguity, ask a useful clarification; do not guess. Respect corrections, negation, word limits and formatting. '
       'Do not imply tools, external access or actions that have not occurred. Do not invent policies, dates, promises or facts. '
       'Normally use 1-3 concise sentences. When the user requests a list, JSON or more steps, follow that format. '
       'Use no tools, files, browsing, code execution, delegated agents or external actions. Do not expose hidden reasoning. '
       'Return the schema-conforming JSON object.\nSCENARIOS:\n'+json.dumps(packets,ensure_ascii=False))
    if len(prompt.encode())>65536:raise ValueError('Prompt byte cap')
    (folder/'prompt.txt').write_text(prompt)
    argv=[EXE,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','--cd',str(folder),
          '--model','gpt-6-luna','--json','--color','never','--output-schema',str(folder/'schema.json'),'--output-last-message',str(folder/'last.json')]
    controls={k:v for k,v in OVERRIDES.items() if k!='tools.view_image'};controls['model_reasoning_effort']='high'
    for key,value in controls.items():argv+=['-c',key+'='+json.dumps(value)]
    argv+=['-'];save(folder/'request.json',dict(argv=argv,phase=phase,ids=[r['id'] for r in batch],model='gpt-6-luna',reasoning='high',prompt_sha256=sha(folder/'prompt.txt')))
    t=time.monotonic()
    with (folder/'events.jsonl').open('wb') as out,(folder/'stderr.txt').open('wb') as err,(folder/'prompt.txt').open('rb') as inp:
        proc=subprocess.Popen(argv,cwd=folder,env=clean_environment(),stdin=inp,stdout=out,stderr=err,start_new_session=True)
        try:
            while proc.poll() is None:
                if cancel.is_set() or time.monotonic()-t>240 or time.monotonic()-start>7200:raise TimeoutError('Teacher request/global stop')
                if (folder/'events.jsonl').stat().st_size>2*1024**2 or (folder/'stderr.txt').stat().st_size>131072:raise ValueError('Log cap')
                if (folder/'last.json').exists() and (folder/'last.json').stat().st_size>131072:raise ValueError('Final response byte cap')
                time.sleep(.1)
        finally:
            if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            save(folder/'terminal.json',dict(pid=proc.pid,returncode=proc.returncode,seconds=time.monotonic()-t))
    if proc.returncode:raise RuntimeError(f'Teacher exit {proc.returncode}; no automatic retry')
    raw=parse_sol_events((folder/'events.jsonl').read_text(),(folder/'last.json').read_text(),
        SimpleNamespace(model_id='gpt-6-luna',max_response_bytes=131072,observed_output_token_limit=16000))
    answer=json.loads((folder/'last.json').read_text());Draft202012Validator(schema).validate(answer)
    for r in batch:
        if not answer[r['id']]['reply'].strip():raise ValueError('Empty reply')
    with lock:
        usage.update(raw['usage'])
        if usage['output_tokens']+usage['reasoning_output_tokens']>300000:raise ValueError('Aggregate observed-output cap')
    save(folder/'receipt.json',dict(usage=raw['usage'],requested_model='gpt-6-luna',resolved_model=None,
        client='codex-cli 0.163.0-alpha.11',tool_events=0,
        files={f.name:sha(f) for f in folder.iterdir() if f.is_file()}))
    return answer

def job(index,batch,start):
    first=request(index,1,batch,None,start)
    # A first-turn prompt contains no second-turn user text or reference.
    second=request(index,2,batch,first,start)
    rows=[]
    for r in batch:
        rows.append({**r,'messages':[dict(role='user',content=r['users'][0]),dict(role='assistant',content=first[r['id']]['reply']),
             dict(role='user',content=r['users'][1]),dict(role='assistant',content=second[r['id']]['reply'])]})
    save(ROOT/f'completed-{index:02d}.json',rows)
    with lock:
        done=len(list(ROOT.glob('completed-*.json')))*25
        save(ROOT/'progress.json',dict(completed_conversations=done,elapsed_seconds=time.monotonic()-start,usage=dict(usage)))
        print(json.dumps(dict(batch=index,conversations=done,seconds=round(time.monotonic()-start,1))),flush=True)
    return rows

def main():
    if (ROOT/'started.json').exists():raise RuntimeError('One generation attempt; no replay')
    assert subprocess.run([EXE,'--version'],capture_output=True,text=True,check=True).stdout.strip()=='codex-cli 0.163.0-alpha.11'
    login=subprocess.run([EXE,'login','status'],env=clean_environment(),capture_output=True,text=True,check=True)
    if (login.stdout+login.stderr).strip()!='Logged in using ChatGPT':raise ValueError('Saved ChatGPT auth required')
    rows=json.loads((ROOT/'seeds.json').read_text());assert len(rows)==500
    if shutil.disk_usage(ROOT).free<20*1024**3:raise ValueError('Free disk floor')
    start=time.monotonic();save(ROOT/'started.json',dict(pid=os.getpid(),utc=datetime.now(timezone.utc).isoformat()))
    result=[]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks=[pool.submit(job,i,rows[i*25:(i+1)*25],start) for i in range(20)]
            try:
                for task in as_completed(tasks):result.extend(task.result())
            except BaseException:
                cancel.set()
                for task in tasks:task.cancel()
                raise
        result.sort(key=lambda r:r['id'])
        (ROOT/'candidates.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in result))
        save(ROOT/'generation-result.json',dict(status='COMPLETE',conversations=len(result),requests=40,usage=dict(usage),seconds=time.monotonic()-start))
    except BaseException as e:
        save(ROOT/'generation-result.json',dict(status='STOPPED',error=str(e),seconds=time.monotonic()-start,usage=dict(usage)))
        raise

if __name__=='__main__':main()
