"""One reserved, bounded, blinded GPT-6 Sol review; never generates training data."""
import json,os,random,signal,subprocess,sys,time
from types import SimpleNamespace
from common import *
sys.path.insert(0,str(PROJECT/'src'))
from slm.teacher.cli import OVERRIDES,clean_environment
from slm.teacher.sol import parse_sol_events
from jsonschema import Draft202012Validator
EXE='/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex'
def cases(phase):
 anchors=read(ROOT/'anchors-private.json');groups=[]
 if phase=='R0':groups=[('baseline',read(ROOT/'baseline/stories.json'))]
 elif phase=='R1':groups=[(s,read(ROOT/s/'stories.json')) for s in ['baseline','A','B']]
 else:
  selected=read(ROOT/'R1-result.json')['selected_arm']
  groups=[('current-original',read(ROOT/'R2/original-stories.json')),('current-new',read(ROOT/'R2/stories.json')),('selected',read(ROOT/selected/'stories.json'))]
 return [(group,r) for group,items in groups for r in items]+[('anchor',a) for a in anchors]
def main():
 phase=sys.argv[1];index=int(sys.argv[2]);assert phase in ['R0','R1','R2'] and index in [1,2]
 check(phase);freeze_check(phase)
 sealed=read(ROOT/f'{phase}-primary-seal.json')
 assert sha(ROOT/f'{phase}-primary.json')==sealed['sha256'],'PRIMARY_REVIEW_NOT_SEALED'
 assert not (ROOT/f'{phase}-teacher-{index}-started.json').exists(),'NO_RETRY'
 prior=list(ROOT.glob('*-teacher-*-started.json'));assert len(prior)<6
 assert sum(p.name.startswith(phase+'-') for p in prior)<2
 if index==2:assert read(ROOT/f'{phase}-teacher-1-receipt.json')['status']=='PASS'
 usage_prior=sum(read(p)['usage']['output_tokens']+read(p)['usage']['reasoning_output_tokens'] for p in ROOT.glob('*-teacher-*-receipt.json'))
 assert usage_prior<72000
 version=subprocess.run([EXE,'--version'],capture_output=True,text=True,check=True,timeout=10).stdout.strip();assert version=='codex-cli 0.163.0-alpha.11.2'
 login=subprocess.run([EXE,'login','status'],env=clean_environment(),capture_output=True,text=True,check=True,timeout=10);assert (login.stdout+login.stderr).strip()=='Logged in using ChatGPT'
 full=cases(phase);random.Random(2026102300+index+{'R0':0,'R1':10,'R2':20}[phase]).shuffle(full)
 n={'R0':60,'R1':140,'R2':200}[phase];assert len(full)==n
 rows=[dict(id=f'blind-{i:03d}',prefix=r['prefix'],response=r['response']) for i,(group,r) in enumerate(full)]
 stem=f'{phase}-teacher-{index}'
 save(ROOT/f'{stem}-map.json',{f'blind-{i:03d}':dict(group=g,id=r['id']) for i,(g,r) in enumerate(full)})
 item=dict(type='object',properties={'id':{'type':'string'},'scores':{'type':'array','items':{'type':'integer','minimum':0,'maximum':2},'minItems':5,'maxItems':5},'contradiction':{'type':'boolean'},'incoherent_sentence':{'type':'boolean'},'reason':{'type':'string'}},required=['id','scores','contradiction','incoherent_sentence','reason'],additionalProperties=False)
 schema=dict(type='object',properties={'reviews':{'type':'array','items':item,'minItems':n,'maxItems':n}},required=['reviews'],additionalProperties=False);save(ROOT/f'{stem}-schema.json',schema)
 rubric=read(ROOT/'rubric.json')
 prompt=(f'Grade exactly these {n} narrative continuations independently. Use no tools, files, browsing, shell, actions or delegated agents. Assess RESPONSE in the given prefix context. These are narrative continuations, not chat instructions. '
 'Return five scores in exact order: grammar, topical continuity, reference/entity consistency, causal/temporal consistency, local coherence. '
 +rubric['scale']+'. '+rubric['clarifications']+' '
 'Mark contradiction if the response contradicts a stated premise. Mark incoherent_sentence for a nonsensical sentence, impossible unexplained causal claim or major internally contradictory statement. Keep names, genders, ownership and temporal references consistent. Grade each case independently without borrowing facts from any other case. '
 'Give one short reason (at most 8 words). No corrected responses or hidden reasoning. Return only schema JSON.\nCASES:\n'+json.dumps(rows,ensure_ascii=False))
 assert len(prompt.encode())<=524288
 (ROOT/f'{stem}-prompt.txt').write_text(prompt)
 deadline=min(time.time()+240,read(ROOT/'clock.json')['deadline_epoch']-300);assert deadline>time.time()+30
 argv=[EXE,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','--cd',str(ROOT),'--model','gpt-6-sol','--json','--color','never','--output-schema',str(ROOT/f'{stem}-schema.json'),'--output-last-message',str(ROOT/f'{stem}-review.json')]
 controls={k:v for k,v in OVERRIDES.items() if k!='tools.view_image'};controls['model_reasoning_effort']='high'
 for k,v in controls.items():argv+=['-c',k+'='+json.dumps(v)]
 argv+=['-'];start=time.monotonic()
 save(ROOT/f'{stem}-started.json',dict(requested_model='gpt-6-sol',client=version,argv=argv,deadline_epoch=deadline,epoch=time.time(),prompt_sha256=sha(ROOT/f'{stem}-prompt.txt'),primary_seal_sha256=sha(ROOT/f'{phase}-primary-seal.json'),teacher_source_sha256=sha(__file__),output_control='No provider output-token limit exposed by this CLI transport; enforce observed usage after response, no later dispatch on breach.'))
 with (ROOT/f'{stem}-events.jsonl').open('xb') as out,(ROOT/f'{stem}-stderr.txt').open('x') as err:
  proc=subprocess.Popen(argv,env=clean_environment(),stdin=subprocess.PIPE,stdout=out,stderr=err,start_new_session=True)
  try:
   proc.stdin.write(prompt.encode());proc.stdin.close()
   while proc.poll() is None:
    check(phase)
    if time.time()>deadline:raise TimeoutError('TEACHER_DEADLINE')
    if (ROOT/f'{stem}-events.jsonl').stat().st_size>2*1024**2 or (ROOT/f'{stem}-stderr.txt').stat().st_size>131072:raise RuntimeError('TEACHER_BYTE_CAP')
    time.sleep(.2)
  finally:
   if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   save(ROOT/f'{stem}-terminal.json',dict(returncode=proc.returncode,seconds=time.monotonic()-start,worker_reaped=True))
 assert proc.returncode==0,'TEACHER_FAILED_NO_RETRY'
 review_path=ROOT/f'{stem}-review.json';assert review_path.stat().st_size<=131072
 answer=read(review_path);Draft202012Validator(schema).validate(answer)
 assert sorted(r['id'] for r in answer['reviews'])==sorted(r['id'] for r in rows)
 usage=parse_sol_events((ROOT/f'{stem}-events.jsonl').read_text(),review_path.read_text(),SimpleNamespace(model_id='gpt-6-sol',max_response_bytes=131072,observed_output_token_limit=12000))['usage']
 total=usage['output_tokens']+usage['reasoning_output_tokens'];assert total<=12000 and usage_prior+total<=72000,'TEACHER_USAGE_CAP'
 save(ROOT/f'{stem}-receipt.json',dict(status='PASS',cases=n,requested_model='gpt-6-sol',resolved_model=None,usage=usage,tool_events=0,requests=1,seconds=time.monotonic()-start,client=version))
 print(json.dumps(dict(event='teacher_complete',phase=phase,request=index,usage=usage)),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  save(ROOT/'STOP.json',dict(phase=sys.argv[1],reason=type(e).__name__+': '+str(e),epoch=time.time(),training_authorized=False));raise
