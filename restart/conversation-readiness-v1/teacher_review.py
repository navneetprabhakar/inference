"""One bounded GPT-6 Luna review and correction-data request; no student training."""
import hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
from types import SimpleNamespace
BASE=Path(__file__).resolve().parents[2];sys.path.insert(0,str(BASE/'src'))
from slm.teacher.cli import OVERRIDES,clean_environment
from slm.teacher.sol import parse_sol_events
from jsonschema import Draft202012Validator
ROOT=Path(__file__).resolve().parent
EXE='/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex'
def save(name,obj):(ROOT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def main():
    if (ROOT/'teacher-started.json').exists():raise RuntimeError('One request only; preserve prior attempt')
    assert json.loads((ROOT/'verification.json').read_text())['status']=='PASS'
    version=subprocess.run([EXE,'--version'],capture_output=True,text=True,check=True,timeout=10).stdout.strip()
    assert version=='codex-cli 0.163.0-alpha.11'
    login=subprocess.run([EXE,'login','status'],env=clean_environment(),capture_output=True,text=True,check=True,timeout=10)
    assert (login.stdout+login.stderr).strip()=='Logged in using ChatGPT'
    seeds=[('greeting','Hello, can we talk for a moment?'),('name','My name is Rohan. Please tell me my name.'),
      ('color','The kite is orange. What color is it?'),('count','There are three pears. I add two pears. How many pears are there now?'),
      ('negation','Leela dislikes tea. Does she like tea?'),('correction','My cat is called Snow. Actually, her name is Mist. What is her name?'),
      ('clarification','Please move it over there.'),('copy','Write exactly: Welcome home.'),
      ('steps','Give two simple steps for brushing teeth.'),('story','Tell me a two-sentence story about a kind bird.'),
      ('honesty','Have you booked my train ticket?'),('constraint','Name a fruit using just one word.'),
      ('context','I have a rabbit named Cocoa. What animal is Cocoa?'),('yesno','Can five children sit on three seats if each seat holds one child?'),
      ('comfort','I lost my favorite pencil and feel sad.'),('explanation','Explain why we use an umbrella in the rain in one short sentence.')]
    # Unused future evaluation families. Never sent to this teacher, never training examples.
    holdouts=[dict(id='holdout-'+str(i),family=f,user=q) for i,(f,q) in enumerate([
      ('provided_fact','A lunchbox contains a sandwich. What is inside the lunchbox?'),
      ('changed_destination','We were going to the zoo, but now we are going to the beach. Where are we going?'),
      ('missing_date','Remind me about the meeting.'),('verbatim','Reply with exactly: Thank you, friend.'),
      ('quantity_comparison','A basket has four balls and another has six. Which basket has more?'),
      ('unperformed_action','Did you switch off my bedroom light?'),
      ('contextual_reference','Asha gave Ravi a book. Who received the book?'),('length_format','Write a three-word sentence about sunshine.')])]
    save('future-holdouts.json',dict(status='FROZEN_UNUSED',student_evaluated=False,teacher_seen=False,training_allowed=False,examples=holdouts))
    properties={
      'reviews':dict(type='array',items=dict(type='object',properties={'id':{'type':'string'},'language_ok':{'type':'boolean'},'coherent':{'type':'boolean'},'answers_request':{'type':'boolean'},'reason':{'type':'string'}},required=['id','language_ok','coherent','answers_request','reason'],additionalProperties=False)),
      'corrections':dict(type='array',items=dict(type='object',properties={'id':{'type':'string'},'assistant':{'type':'string'}},required=['id','assistant'],additionalProperties=False)),
      'assessment':dict(type='object',properties={'ready_for_conversation_sft':{'type':'boolean'},'reason':{'type':'string'},'next_step':{'type':'string'}},required=['ready_for_conversation_sft','reason','next_step'],additionalProperties=False)}
    schema=dict(type='object',properties=properties,required=list(properties),additionalProperties=False)
    save('teacher-schema.json',schema)
    seeds=[dict(id=f'correction-{i}',family=f,user=q) for i,(f,q) in enumerate(seeds)];save('correction-seeds.json',seeds)
    responses=json.loads((ROOT/'responses.json').read_text())
    prompt=('Review the attached outputs of our own 15.19M-parameter base English LM trained from random weights for 78,774,272 target exposures. '
      'This is a TinyStories base LM, not yet instruction tuned. No tools, browsing, files, execution, delegation or external actions. '
      'For EACH diagnostic ID, mark language_ok (mostly readable English), coherent (internally sensible and maintains prompt entities), '
      'answers_request (chat: directly and correctly follows user request; story: plausible consistent continuation). Explain briefly. '
      'Do not penalize lack of EOS or an unfinished final sentence at the explicit generation limit; assess the text present. '
      'Two turn_context cases have identical prompts: report both, not independent successes. Templates were never trained, so template failure alone does not prove lack of language. '
      'Assess whether immediate conversation SFT is warranted or base language needs further learning. Do not claim guaranteed training outcomes. '
      'Then produce one concise correct natural assistant response for each NEW correction seed, normally 1-2 short sentences, following exact formatting constraints. '
      'Never claim to have acted in the real world. Clarify missing actionable information. No hidden reasoning. '
      'These are provisional correction examples, not proof the student learned. Return schema JSON.\nDIAGNOSTICS:\n'+json.dumps(responses,ensure_ascii=False)+'\nCORRECTION_SEEDS:\n'+json.dumps(seeds,ensure_ascii=False))
    (ROOT/'teacher-prompt.txt').write_text(prompt)
    controls={k:v for k,v in OVERRIDES.items() if k!='tools.view_image'};controls['model_reasoning_effort']='high'
    argv=[EXE,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','--cd',str(ROOT),
      '--model','gpt-6-luna','--json','--color','never','--output-schema',str(ROOT/'teacher-schema.json'),'--output-last-message',str(ROOT/'teacher-answer.json')]
    for k,v in controls.items():argv+=['-c',k+'='+json.dumps(v)]
    argv+=['-']
    save('teacher-started.json',dict(model='gpt-6-luna',client=version,requests=1,timeout_seconds=240,student_training=False,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),argv=argv))
    start=time.monotonic()
    with (ROOT/'teacher-events.jsonl').open('wb') as out,(ROOT/'teacher-stderr.txt').open('wb') as err:
      proc=subprocess.Popen(argv,env=clean_environment(),stdin=subprocess.PIPE,stdout=out,stderr=err,start_new_session=True)
      try:
        proc.stdin.write(prompt.encode());proc.stdin.close()
        while proc.poll() is None:
          if time.monotonic()-start>240 or (ROOT/'teacher-events.jsonl').stat().st_size>2*1024**2:raise TimeoutError('Teacher cap')
          time.sleep(.2)
      finally:
        if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        save('teacher-terminal.json',dict(returncode=proc.returncode,seconds=time.monotonic()-start))
    assert proc.returncode==0,'Teacher failed; no automatic retry or substitute'
    answer=json.loads((ROOT/'teacher-answer.json').read_text());Draft202012Validator(schema).validate(answer)
    assert sorted(r['id'] for r in answer['reviews'])==sorted(r['id'] for r in responses)
    assert sorted(r['id'] for r in answer['corrections'])==sorted(r['id'] for r in seeds)
    receipt=parse_sol_events((ROOT/'teacher-events.jsonl').read_text(),(ROOT/'teacher-answer.json').read_text(),SimpleNamespace(model_id='gpt-6-luna',max_response_bytes=131072,observed_output_token_limit=16000))
    save('teacher-receipt.json',dict(requested_model='gpt-6-luna',resolved_model=None,usage=receipt['usage'],tool_events=0,seconds=time.monotonic()-start,note='CLI metadata does not identify resolved backend model; exact requested model pinned.'))
if __name__=='__main__':main()
