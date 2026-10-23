"""One read-only GPT-6 Luna grading request. No correction generation or training."""
import hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parents[1];sys.path.insert(0,str(BASE/'src'))
from slm.teacher.cli import OVERRIDES,clean_environment
from slm.teacher.sol import parse_sol_events
from jsonschema import Draft202012Validator
EXE='/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex'
def save(name,obj):(ROOT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def main():
    if (ROOT/'teacher-started.json').exists():raise RuntimeError('One teacher request; no retries')
    clock=json.loads((ROOT/'clock.json').read_text());deadline=min(time.time()+240,clock['preflight_deadline_epoch']-20)
    assert deadline>time.time()+30,'Insufficient authorized time'
    assert json.loads((ROOT/'contract.json').read_text())['training_authorized'] is False
    version=subprocess.run([EXE,'--version'],capture_output=True,text=True,check=True,timeout=10).stdout.strip();assert version=='codex-cli 0.163.0-alpha.11.2'
    login=subprocess.run([EXE,'login','status'],env=clean_environment(),capture_output=True,text=True,check=True,timeout=10);assert (login.stdout+login.stderr).strip()=='Logged in using ChatGPT'
    rows=json.loads((ROOT/'baseline/stories.json').read_text());assert len(rows)==100
    item=dict(type='object',properties={'id':{'type':'string'},'scores':{'type':'array','items':{'type':'integer','minimum':0,'maximum':2},'minItems':5,'maxItems':5},'contradiction':{'type':'boolean'},'incoherent_sentence':{'type':'boolean'},'reason':{'type':'string'}},required=['id','scores','contradiction','incoherent_sentence','reason'],additionalProperties=False)
    schema=dict(type='object',properties={'reviews':{'type':'array','items':item,'minItems':100,'maxItems':100}},required=['reviews'],additionalProperties=False);save('teacher-schema.json',schema)
    prompt=('Grade exactly these 100 base-language-model continuations independently. Use no tools, browsing, files, shell, actions or delegated agents. '
       'The prefix is given context; assess the RESPONSE, not the quality of the prefix. These are narrative continuations, not chat instructions. '
       'Return scores in this exact order: grammar, topical continuity, reference/entity consistency, causal/temporal consistency, local coherence. '
       'Each score: 0=major meaning-changing or hard-to-follow failure; 1=understandable minor error or awkwardness; 2=clear consistent natural text. '
       'Mark contradiction if the response contradicts a stated premise. Mark incoherent_sentence for a nonsensical sentence, impossible unexplained causal claim or major internally contradictory statement. '
       'Narrative development and new characters are allowed if connected plausibly to the prefix. Keep entity names, genders, ownership and the problem consistent. '
       'Do not fail a merely unfinished last sentence at the 96-token generation cap. Empty/very short responses or wholly unrelated output fail. '
       'Do not reward readable but context-ignoring repetition. Grade each case on its text without comparing it to another case or sharing its facts. '
       'Give one short reason (about 12 words). Do not provide corrected responses or hidden reasoning. Return only schema JSON.\nCASES:\n'+json.dumps(rows,ensure_ascii=False))
    (ROOT/'teacher-prompt.txt').write_text(prompt)
    argv=[EXE,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','--cd',str(ROOT),'--model','gpt-6-luna','--json','--color','never','--output-schema',str(ROOT/'teacher-schema.json'),'--output-last-message',str(ROOT/'teacher-review.json')]
    controls={k:v for k,v in OVERRIDES.items() if k!='tools.view_image'};controls['model_reasoning_effort']='high'
    for k,v in controls.items():argv+=['-c',k+'='+json.dumps(v)]
    argv+=['-'];start=time.monotonic();save('teacher-started.json',dict(requested_model='gpt-6-luna',argv=argv,deadline_epoch=deadline,client=version,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),training=False))
    with (ROOT/'teacher-events.jsonl').open('wb') as out,(ROOT/'teacher-stderr.txt').open('wb') as err:
      proc=subprocess.Popen(argv,env=clean_environment(),stdin=subprocess.PIPE,stdout=out,stderr=err,start_new_session=True)
      try:
        proc.stdin.write(prompt.encode());proc.stdin.close()
        while proc.poll() is None:
          if time.time()>deadline:raise TimeoutError('Teacher deadline')
          if (ROOT/'teacher-events.jsonl').stat().st_size>2*1024**2 or (ROOT/'teacher-stderr.txt').stat().st_size>131072:raise RuntimeError('Teacher byte cap')
          time.sleep(.2)
      finally:
        if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        save('teacher-terminal.json',dict(returncode=proc.returncode,seconds=time.monotonic()-start,worker_reaped=True))
    assert proc.returncode==0,'No retry or model substitution'
    answer=json.loads((ROOT/'teacher-review.json').read_text());Draft202012Validator(schema).validate(answer)
    assert sorted(r['id'] for r in answer['reviews'])==sorted(r['id'] for r in rows)
    usage=parse_sol_events((ROOT/'teacher-events.jsonl').read_text(),(ROOT/'teacher-review.json').read_text(),SimpleNamespace(model_id='gpt-6-luna',max_response_bytes=131072,observed_output_token_limit=16000))['usage']
    assert usage['output_tokens']+usage['reasoning_output_tokens']<=48000
    save('teacher-receipt.json',dict(requested_model='gpt-6-luna',resolved_model=None,usage=usage,tool_events=0,requests=1,seconds=time.monotonic()-start,client=version))
if __name__=='__main__':main()
