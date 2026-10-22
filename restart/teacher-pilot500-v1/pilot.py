"""Owner-approved 500-conversation Luna pilot; never imports a student backend."""
# Creator: Navneet Prabhakar
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shutil
import signal
import subprocess
import time
from types import SimpleNamespace

from jsonschema import Draft202012Validator
from slm.teacher.cli import OVERRIDES, clean_environment
from slm.teacher.sol import parse_sol_events
from slm.common.tokenizer import BPE

ROOT = Path(os.environ.get('SLM_PILOT500_ROOT',str(Path(__file__).resolve().parent))).resolve()
MODEL = 'gpt-6-luna'
TOPICS = [
 ('pottery class','clay','studio'),('cycling meetup','helmet','park'),
 ('book exchange','book','library'),('garden workshop','gloves','greenhouse'),
 ('cooking lesson','apron','kitchen'),('chess club','chessboard','hall'),
 ('photography walk','camera','courtyard'),('birdwatching trip','binoculars','lake'),
 ('knitting circle','yarn','lounge'),('music practice','instrument','rehearsal room'),
 ('painting session','brush','art room'),('repair workshop','screwdriver','workshop'),
 ('running group','water bottle','track'),('writing circle','notebook','reading room'),
 ('origami class','paper','classroom'),('dance rehearsal','towel','dance studio'),
 ('language exchange','dictionary','meeting room'),('coding club','laptop','computer room'),
 ('history talk','notepad','auditorium'),('science activity','pencil','lab'),
 ('puppet workshop','fabric','craft room'),('board game evening','game','clubhouse'),
 ('poetry reading','poem','cafe'),('mapmaking session','ruler','design room'),
 ('sewing lesson','thread','sewing room'),('puzzle meetup','puzzle','common room'),
 ('calligraphy class','pen','gallery'),('woodworking lesson','safety goggles','tool shed'),
 ('baking class','oven mitt','bakery'),('paper craft session','scissors','maker room'),
 ('seed swap','seed packet','garden'),('astronomy talk','star chart','planetarium'),
 ('film discussion','notes','screening room'),('walking group','walking shoes','square'),
 ('storytelling circle','story','community room'),('robotics club','cable','technology room'),
 ('embroidery lesson','needle','textile room'),('scrapbooking session','photo','activity room'),
 ('clay modelling lesson','modelling tool','ceramics room'),('drumming circle','drum','music room'),
 ('volunteer briefing','ID card','reception'),('kite making class','string','assembly room'),
 ('composting workshop','bucket','allotment'),('creative reading group','short story','bookshop'),
 ('printmaking session','roller','print studio'),('weaving lesson','wool','weaving room'),
 ('nature journaling walk','sketchbook','meadow'),('collage workshop','magazine','project room'),
 ('memory game session','card deck','recreation room'),('community choir','song sheet','chapel'),
]
CATEGORIES = ['grounded','correction','planning','comparison','extraction','rewrite',
              'summary','clarification','reasoning','honesty']

def digest(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n')

def seeds():
    order = sorted(range(50),key=lambda i:digest(['luna-pilot500-split-v1',i]))
    splits = {i:('train' if j<40 else 'development' if j<45 else 'test') for j,i in enumerate(order)}
    result=[]
    for i,(topic,item,place) in enumerate(TOPICS):
        name=['Mira','Leo','Asha','Omar','Nina','Ben','Tara','Eli','Ravi','Zoe'][i%10]
        day=['Monday','Tuesday','Wednesday','Thursday','Friday'][i%5]
        capacity=12+i; a=20+2*i; b=a+7; room=f'{name} Room {i+1}'
        note=(f'Fictional event note: {topic}; coordinator {name}; {day} at 10:00; '
              f'location {place}, {room}; capacity {capacity}; bring a {item}. '
              f'Option A costs {a} credits; option B costs {b} credits. '
              'No other information is supplied.')
        tasks=[
          (f'{note} Where and when is the event?', 'What is its capacity, and what should I bring?',
           [[place,day,'10:00'],[str(capacity),item]], [None,None]),
          (f'{note} I think it starts at 11:00. Is that right?',
           f'The coordinator has now moved it to 12:00. Restate the updated time and original location.',
           [['10:00'],['12:00',place]], [None,None]),
          (f'I am preparing for a {topic}. I have 30 minutes from 09:00. Setup takes 10 minutes and practice takes 20 minutes. Give a schedule that finishes on time.',
           'Setup will take 15 minutes instead. Keep the same finish time and shorten practice. Give the revised schedule.',
           [['09:00','09:10','09:30'],['09:00','09:15','09:30']], [None,None]),
          (f'{note} Which option is cheaper and by how many credits?',
           f'Option A now costs {b+3} credits; B stays the same. Which is cheaper now, and by how much?',
           [['A','7'],['B','3']], [None,None]),
          (f'{note} Return just the coordinator and room, with labels.',
           'Now return just the capacity and required item, with labels.',
           [[name,room],[str(capacity),item]], [None,None]),
          (f'Rewrite this as a polite request without adding facts: "Give me the {item} for the {topic}."',
           'Make that request no more than 12 words. Keep the required item.',
           [[item],[item]], [None,12]),
          (f'{note} Summarize the event in no more than 25 words. Include its time and required item.',
           'Now summarize it in no more than 10 words, keeping the time.',
           [['10:00',item],['10:00']], [25,10]),
          (f'I want to join a {topic}. Help me write a request. Ask me one question about a missing detail before drafting it.',
           f'My name is {name}, and I want one place on {day}. Draft the request now. Do not claim it has been sent.',
           [[],[name,day]], [None,None]),
          (f'The {topic} has {capacity} seats. There are {capacity-4} confirmed participants and 3 newcomers. Can everyone fit? State how many seats remain.',
           'Two more newcomers arrive. Can everyone fit now? State the shortfall.',
           [['1'],['1']], [None,None]),
          (f'{note} What is the building\'s opening time? Use only this note.',
           'Please book a place for me now. Can you actually make the booking in this chat?',
           [[],[]], [None,None]),
        ]
        for j,(u1,u2,required,wordcaps) in enumerate(tasks):
            result.append(dict(id=f'p{i:02d}-{j:02d}',family=f'topic-{i:02d}',split=splits[i],
                category=CATEGORIES[j],users=[u1,u2],required=required,wordcaps=wordcaps))
    return result

def prepare():
    ROOT.mkdir(exist_ok=True)
    if (ROOT/'seeds.json').exists():raise FileExistsError('Frozen seeds already exist')
    rows=seeds();save(ROOT/'seeds.json',rows)
    rng=random.Random(2210500)
    selected=[]
    for category in CATEGORIES:
        selected.extend(rng.sample([r['id'] for r in rows if r['category']==category],10))
    save(ROOT/'review-selection.json',dict(seed=2210500,ids=selected,selection='10 uniform without replacement per category, frozen before generation'))
    save(ROOT/'authorization.json',dict(owner_instruction='Approved 500 conversation pilot via Codex CLI GPT6 Luna; quality/count review before scaling; conditional student training after readiness assessment.',
        model=MODEL,conversations=500,requests=50,automatic_retries=0,per_request_seconds=180,
        aggregate_seconds=7200,per_request_output_bytes=65536,per_request_observed_output_tokens=8192,
        observed_output_gate_is_not_server_generation_limit=True,aggregate_observed_output_tokens=250000,
        source='ChatGPT saved login; no API keys or provider fallback',student_operations=False,
        split_families=dict(train=40,development=5,test=5),seeds_sha256=digest(rows),
        quality_gate=dict(automated_valid_fraction_min=.95,reviewed_semantic_pass_fraction_min=.95,
                          critical_errors_max=0,reviewed_examples=100),
        scope='Small fictional event/task curriculum; no broad-English sufficiency claim. All prior experiments and caps preserved.',
        created_utc=datetime.now(timezone.utc).isoformat()))

def run():
    rows=json.loads((ROOT/'seeds.json').read_text());auth=json.loads((ROOT/'authorization.json').read_text())
    if digest(rows)!=auth['seeds_sha256']:raise ValueError('Seeds changed')
    if (ROOT/'started.json').exists():raise ValueError('One attempt only; never replay automatically')
    env=clean_environment();exe=os.environ.get('SLM_PILOT500_CLI') or shutil.which('codex')
    version=subprocess.run([exe,'--version'],env=env,capture_output=True,text=True,check=True,timeout=10).stdout.strip()
    if version!=auth.get('cli_version','codex-cli 0.144.4'):raise ValueError('CLI differs from pinned authorization')
    login=subprocess.run([exe,'login','status'],env=env,capture_output=True,text=True,check=True,timeout=10)
    if (login.stdout+login.stderr).strip()!='Logged in using ChatGPT':raise ValueError('Saved ChatGPT auth required')
    start=time.monotonic();save(ROOT/'started.json',dict(utc=datetime.now(timezone.utc).isoformat(),pid=os.getpid(),cli=version))
    completed=0;total_usage=Counter()
    try:
      for batch_index in range(50):
        if time.monotonic()-start>=7200:raise TimeoutError('Aggregate deadline')
        if shutil.disk_usage(ROOT).free<20*1024**3:raise ValueError('Disk floor')
        batch=rows[batch_index*10:(batch_index+1)*10]
        folder=ROOT/f'batch-{batch_index:02d}';folder.mkdir()
        answer_schema=dict(type='object',properties={f'a{k}':dict(type='string') for k in (1,2)},required=['a1','a2'],additionalProperties=False)
        schema=dict(type='object',properties={r['id']:answer_schema for r in batch},required=[r['id'] for r in batch],additionalProperties=False)
        save(folder/'schema.json',schema)
        submitted=[dict(id=r['id'],user_turn_1=r['users'][0],user_turn_2=r['users'][1]) for r in batch]
        prompt=('Generate English conversational training demonstrations, not code. For each independent scenario return a1 responding to user_turn_1, then a2 responding to user_turn_2 in the context of a1. '
          'Use clear natural English and usually 1-2 short sentences per reply, at most 60 words. Follow explicit shorter word limits. '
          'Respect evidence, corrections, uncertainty and negation. Compute arithmetic correctly. When asked to clarify, ask exactly one useful question; once the missing details arrive, answer. '
          'For unprovided facts say the note does not specify them. You have no ability to book, send messages or act outside this conversation: do not claim an action occurred. '
          'Do not add invented real-world facts to supplied fictional notes. No generic AI disclaimers. Do not expose hidden reasoning. '
          'Use no tools, files, browsing, commands, MCP, delegated agents or external actions. Return only the schema-conforming JSON object.\nSCENARIOS:\n'+json.dumps(submitted,ensure_ascii=False))
        (folder/'prompt.txt').write_text(prompt)
        argv=[exe,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only',
              '--cd',str(folder),'--model',MODEL,'--json','--color','never','--output-schema',str(folder/'schema.json'),
              '--output-last-message',str(folder/'last.json')]
        controls={k:v for k,v in OVERRIDES.items() if k!='tools.view_image'}
        for key,value in controls.items():argv+=['-c',key+'='+json.dumps(value)]
        argv+=['-'];save(folder/'request.json',dict(model=MODEL,argv=argv,prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest()))
        t=time.monotonic()
        with (folder/'events.jsonl').open('wb') as out,(folder/'stderr.txt').open('wb') as err,(folder/'prompt.txt').open('rb') as inp:
          proc=subprocess.Popen(argv,cwd=folder,env=env,stdin=inp,stdout=out,stderr=err,start_new_session=True)
          try:
            while proc.poll() is None:
              if time.monotonic()-t>180 or time.monotonic()-start>7200:raise TimeoutError('Teacher deadline')
              if (folder/'events.jsonl').stat().st_size>1024**2 or (folder/'stderr.txt').stat().st_size>131072:raise ValueError('Log byte cap')
              if (folder/'last.json').exists() and (folder/'last.json').stat().st_size>65536:raise ValueError('Response byte cap')
              time.sleep(.1)
          finally:
            if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
            save(folder/'terminal.json',dict(returncode=proc.returncode,seconds=time.monotonic()-t))
        if proc.returncode:raise ValueError(f'Teacher exit {proc.returncode}; retained, no automatic retry')
        recipe=SimpleNamespace(model_id=MODEL,observed_output_token_limit=8192,max_response_bytes=65536)
        raw=parse_sol_events((folder/'events.jsonl').read_text(),(folder/'last.json').read_text(),recipe)
        answers=json.loads((folder/'last.json').read_text());Draft202012Validator(schema).validate(answers)
        total_usage.update(raw['usage']);save(folder/'receipt.json',dict(usage=raw['usage'],requested_model=MODEL,resolved_model=None,tools_used=False,
              files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}))
        completed+=10
        save(ROOT/'progress.json',dict(completed_conversations=completed,completed_requests=batch_index+1,elapsed_seconds=time.monotonic()-start,usage=dict(total_usage)))
        print(json.dumps(dict(batch=batch_index,conversations=completed,seconds=round(time.monotonic()-start,1))),flush=True)
        if total_usage['output_tokens']+total_usage['reasoning_output_tokens']>250000:raise ValueError('Aggregate observed output token cap')
      save(ROOT/'generation-result.json',dict(status='COMPLETE',conversations=completed,requests=50,usage=dict(total_usage),elapsed_seconds=time.monotonic()-start))
    except BaseException as e:
      save(ROOT/'generation-result.json',dict(status='STOPPED',error=type(e).__name__,detail=str(e),conversations=completed,usage=dict(total_usage),elapsed_seconds=time.monotonic()-start))
      raise

def word_count(text):return len(text.split())

def inspect():
    rows=json.loads((ROOT/'seeds.json').read_text());bpe=BPE.load(ROOT.parent/'execution-v1/tokenizer-8192')
    seen={};records=[];totals=Counter();split_counts={};flags=Counter()
    for r in rows:
      file=ROOT/f"batch-{int(r['id'][1:3]):02d}"/'last.json'
      if not file.exists():continue
      a=json.loads(file.read_text())[r['id']];messages=[];issues=[]
      for k in range(2):
        reply=a[f'a{k+1}'];messages.extend([dict(role='user',content=r['users'][k]),dict(role='assistant',content=reply)])
        if not reply.strip():issues.append('empty')
        if word_count(reply)>60:issues.append('reply_word_cap')
        if r['wordcaps'][k] is not None and word_count(reply)>r['wordcaps'][k]:issues.append('explicit_word_cap')
        for needle in r['required'][k]:
          if re.search(r'(?<!\w)'+re.escape(needle)+r'(?!\w)',reply,re.I) is None:issues.append(f'missing_required_turn{k+1}:{needle}')
        if re.search(r'(?i)\b(as an ai|language model|https?://|i (?:have )?(?:booked|sent|reserved))\b',reply):issues.append('disclaimer_external_action_or_url')
      text='\n'.join(m['content'] for m in messages);key=digest(' '.join(text.lower().split()))
      if key in seen:issues.append('exact_duplicate')
      seen[key]=r['id']
      x,y,mask=bpe.serialize(messages)
      count=dict(content_tokens=sum(len(bpe.encode(m['content'])) for m in messages),
                 serialized_predicted_positions=len(y),assistant_supervised_targets=sum(mask),utf8_bytes=len(text.encode()))
      if len(y)>512:issues.append('exceeds_M1_context512')
      record={**r,'messages':messages,'counts':count,'automated_issues':issues,'exact_sha256':key}
      records.append(record);flags.update(issues)
      if not issues:
        totals.update(count);s=split_counts.setdefault(r['split'],Counter());s.update(count);s.update(documents=1)
    with (ROOT/'candidates.jsonl').open('w') as f:
      for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    save(ROOT/'automated-review.json',dict(generated=len(records),automated_clear=sum(not r['automated_issues'] for r in records),issues=dict(flags),
       provisional_counts=dict(totals),splits={s:dict(c) for s,c in split_counts.items()},
       tokenizer='existing M1 BPE 8192; not teacher usage tokens',semantic_acceptance=False,
       scope='Keyword/arithmetic constraints, formatting, exact dedup and context checks; no general semantic correctness certification'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','inspect']);args=p.parse_args()
    globals()[args.action]()
