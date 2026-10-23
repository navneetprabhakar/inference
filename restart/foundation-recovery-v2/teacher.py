"""Immutable 16-row, high-reasoning, serial Sol reviewer; no retries or tools."""
import json,os,random,signal,subprocess,sys,time
from types import SimpleNamespace
from common import *
sys.path.insert(0,str(PROJECT/'src'))
from slm.teacher.cli import OVERRIDES,clean_environment
from slm.teacher.sol import parse_sol_events
from jsonschema import Draft202012Validator
EXE='/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex'

def packet(phase,round_no,packet_no):
 config=read(ROOT/'packet-assignments.json')[phase];spec=config[packet_no-1];full=[]
 for ref in spec:
  rows=read(ROOT/phase/ref['path']);r=next(x for x in rows if x['id']==ref['id']);full.append((ref['group'],r))
 full += [('anchor',a) for a in read(ROOT/'anchors-private.json')]
 assert len(full)==16 and len(spec)==12
 random.Random(20261024000+round_no*100+packet_no+{'R0':0,'R1':1000,'R2':2000}[phase]).shuffle(full)
 return full

def main():
 phase=sys.argv[1];round_no=int(sys.argv[2]);packet_no=int(sys.argv[3]);assert phase in ['R0','R1','R2'] and round_no in [1,2]
 check(phase);freeze_check(phase);caps={'R0':10,'R1':12,'R2':16};assert 1<=packet_no<=caps[phase]//2
 sealed=read(ROOT/phase/'primary-seal.json');assert sha(ROOT/phase/'primary.json')==sealed['sha256'],'PRIMARY_NOT_SEALED'
 directory=ROOT/phase/'teacher';directory.mkdir(exist_ok=True);stem=f'round{round_no}-packet{packet_no}'
 assert not (directory/f'{stem}-started.json').exists(),'NO_RETRY'
 prior=list(ROOT.glob('*/teacher/*-started.json'));assert len(prior)<38
 assert len(list(directory.glob('*-started.json')))<caps[phase]
 receipts=list(ROOT.glob('*/teacher/*-receipt.json'));assert len(receipts)==len(prior),'PREVIOUS_REQUEST_NOT_AUDITED'
 usage_prior=sum(read(p)['usage']['output_tokens']+read(p)['usage']['reasoning_output_tokens'] for p in receipts);assert usage_prior<304000
 version=subprocess.run([EXE,'--version'],capture_output=True,text=True,check=True,timeout=10).stdout.strip();assert version=='codex-cli 0.163.0-alpha.11.2'
 login=subprocess.run([EXE,'login','status'],env=clean_environment(),capture_output=True,text=True,check=True,timeout=10);assert (login.stdout+login.stderr).strip()=='Logged in using ChatGPT'
 full=packet(phase,round_no,packet_no)
 rows=[dict(id=f'blind-{i:03d}',prefix=r['prefix'],response=r['response']) for i,(_,r) in enumerate(full)]
 save(directory/f'{stem}-map.json',{f'blind-{i:03d}':dict(group=g,id=r['id']) for i,(g,r) in enumerate(full)})
 item=dict(type='object',properties={'id':{'type':'string'},'scores':{'type':'array','items':{'type':'integer','minimum':0,'maximum':2},'minItems':5,'maxItems':5},'contradiction':{'type':'boolean'},'incoherent_sentence':{'type':'boolean'},'reason':{'type':'string','maxLength':120}},required=['id','scores','contradiction','incoherent_sentence','reason'],additionalProperties=False)
 schema=dict(type='object',properties={'reviews':{'type':'array','items':item,'minItems':16,'maxItems':16}},required=['reviews'],additionalProperties=False);save(directory/f'{stem}-schema.json',schema)
 rubric=read(ROOT/'rubric.json')
 prompt=('Grade exactly these 16 continuations independently. Use no tools, files, browsing, shell, actions or delegated agents. Assess RESPONSE in its PREFIX context. These are narrative or explanatory prose continuations, not chat instructions. Return five scores in this exact order: grammar, topical continuity, reference/entity consistency, causal/temporal consistency, local coherence. '+rubric['scale']+'. '+rubric['clarifications']+' Mark contradiction if the response contradicts a stated premise. Mark incoherent_sentence for a nonsensical sentence, impossible unexplained causal claim or major internally contradictory statement. Keep names, genders, ownership and temporal references consistent. Do not import facts from other rows. Give one short reason (at most 8 words). No corrected responses or hidden reasoning. Return only schema JSON.\nCASES:\n'+json.dumps(rows,ensure_ascii=False))
 assert len(prompt.encode())<=65536
 prompt_path=directory/f'{stem}-prompt.txt';prompt_path.write_text(prompt)
 deadline=min(time.time()+120,read(ROOT/phase/'clock.json')['deadline_epoch']-300);assert deadline>time.time()+30
 argv=[EXE,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','--cd',str(ROOT/phase),'--model','gpt-6-sol','--json','--color','never','--output-schema',str(directory/f'{stem}-schema.json'),'--output-last-message',str(directory/f'{stem}-review.json')]
 controls={k:v for k,v in OVERRIDES.items() if k!='tools.view_image'};controls['model_reasoning_effort']='high'
 for k,v in controls.items():argv+=['-c',k+'='+json.dumps(v)]
 argv+=['-'];start=time.monotonic()
 save(directory/f'{stem}-started.json',dict(requested_model='gpt-6-sol',client=version,argv=argv,deadline_epoch=deadline,epoch=time.time(),prompt_sha256=sha(prompt_path),primary_seal_sha256=sha(ROOT/phase/'primary-seal.json'),teacher_source_sha256=sha(__file__),provider_output_cap_exposed=False,observed_output_plus_reasoning_cap=8000))
 with (directory/f'{stem}-events.jsonl').open('xb') as out,(directory/f'{stem}-stderr.txt').open('x') as err:
  proc=subprocess.Popen(argv,env=clean_environment(),stdin=subprocess.PIPE,stdout=out,stderr=err,start_new_session=True)
  try:
   proc.stdin.write(prompt.encode());proc.stdin.close()
   while proc.poll() is None:
    check(phase)
    if time.time()>deadline:raise TimeoutError('TEACHER_DEADLINE')
    if (directory/f'{stem}-events.jsonl').stat().st_size>2*1024**2 or (directory/f'{stem}-stderr.txt').stat().st_size>131072:raise RuntimeError('TEACHER_BYTE_CAP')
    time.sleep(.2)
  finally:
   if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   save(directory/f'{stem}-terminal.json',dict(returncode=proc.returncode,seconds=time.monotonic()-start,worker_reaped=True))
 assert proc.returncode==0,'TEACHER_FAILED_NO_RETRY'
 review_path=directory/f'{stem}-review.json';assert review_path.stat().st_size<=131072
 answer=read(review_path);Draft202012Validator(schema).validate(answer);assert sorted(r['id'] for r in answer['reviews'])==sorted(r['id'] for r in rows)
 usage=parse_sol_events((directory/f'{stem}-events.jsonl').read_text(),review_path.read_text(),SimpleNamespace(model_id='gpt-6-sol',max_response_bytes=131072,observed_output_token_limit=8000))['usage']
 total=usage['output_tokens']+usage['reasoning_output_tokens'];assert total<=8000 and usage_prior+total<=304000,'TEACHER_USAGE_CAP'
 save(directory/f'{stem}-receipt.json',dict(status='PASS',cases=16,requested_model='gpt-6-sol',resolved_model=None,usage=usage,tool_events=0,requests=1,seconds=time.monotonic()-start,client=version))
 print(json.dumps(dict(event='teacher_complete',phase=phase,round=round_no,packet=packet_no,usage=usage)),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  save(ROOT/'STOP.json',dict(phase=sys.argv[1],reason=type(e).__name__+': '+str(e),epoch=time.time(),training_authorized=False));raise
