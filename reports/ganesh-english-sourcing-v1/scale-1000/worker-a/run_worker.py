import concurrent.futures, hashlib, json, os, pathlib, subprocess, sys, threading, time, traceback
ROOT=pathlib.Path('/Users/navneetprabhakar/Documents/git/image/inference'); R=ROOT/'reports/ganesh-english-sourcing-v1/scale-1000/worker-a'; O=ROOT/'runs/ganesh-english-sourcing-v1/scale-1000/worker-a'
sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
TOK=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
LOCK=threading.Lock()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
GEN_SCHEMA=ROOT/'reports/ganesh-english-sourcing-v1/terra-generation-schema.json'
REVIEW_SCHEMA=R/'review-schema.json'
item={'type':'object','properties':{'group':{'type':'string'},'content_sha256':{'type':'string'},'decision':{'type':'string','enum':['accept','revise','reject']},'reason':{'type':'string'},'turn_reviews':{'type':'array','items':{'type':'object','properties':{'turn':{'type':'integer'},'decision':{'type':'string','enum':['pass','fail']},'rationale':{'type':'string'}},'required':['turn','decision','rationale'],'additionalProperties':False}},'memory_annotation_valid':{'type':'boolean'},'distinct_scenario':{'type':'boolean'}},'required':['group','content_sha256','decision','reason','turn_reviews','memory_annotation_valid','distinct_scenario'],'additionalProperties':False}
write(REVIEW_SCHEMA,{'type':'object','properties':{'reviews':{'type':'array','items':item}},'required':['reviews'],'additionalProperties':False})
RULES='''English conversation train CANDIDATES only. Use NO tools. Return exactly schema JSON. Every assistant target must be correct WHEN GIVEN: user changes/corrects their OWN facts or intent; never deliberately wrong assistant then correction. Natural useful short replies, not repeated generic acknowledgement or state quizzes. No external actions or unsupported facts, invented user motivations/consent/ownership/conditions; suggestions explicitly tentative. Preserve uncertainty and exact user constraints, pronouns, scope. If asked shorter really shorten; do not change meaning when asked tone. No factual specialism or maths expansion; no positive tool calls. 4–8 exchanges as plan, max70 words/reply; total<=330 words for4–6 turns, <=260 words for7–8turns. Diverse turns, no canned filler. Memory recall only after>=2 COMPLETE intervening exchanges since latest support, including assistant echoes; use latest support_turn (1-based), not first mention. Nonmemory recall_probe=null. Correction dialogs should include useful explanation, clarification, comparison or meaningful collaboration, not merely accumulating list changes. Avoid forcing final quiz.'''
def cli(label,prompt,schema):
    pp=O/(label+'.prompt.txt')
    existing=O/(label+'.raw.json'); request=O/(label+'.request.json')
    if existing.exists() and request.exists():
      saved=json.loads(request.read_text())
      if saved['raw_sha256']==sha(existing) and saved['prompt_sha256']==hashlib.sha256(prompt.encode()).hexdigest():return json.loads(existing.read_text()),existing
      raise RuntimeError('Existing artifact collision '+label)
    pp.write_text(prompt)
    raw=O/(label+'.raw.json'); events=O/(label+'.events.jsonl'); err=O/(label+'.stderr.log')
    cmd=['codex','exec','--model','gpt-6.1-terra','--ignore-user-config','--ephemeral','--sandbox','read-only','--cd',str(O),'--json','--output-schema',str(schema),'--output-last-message',str(raw),'-']
    with pp.open() as inp,events.open('w') as out,err.open('w') as errors:
      p=subprocess.run(cmd,stdin=inp,stdout=out,stderr=errors,timeout=900)
    if p.returncode or not raw.exists():raise RuntimeError(f'CLI failed {label}: {p.returncode}')
    ev=[json.loads(l) for l in events.read_text().splitlines()]
    bad=[x for x in ev if x.get('type','').startswith('item.') and x.get('item',{}).get('type') not in ['agent_message','reasoning']]
    if bad:raise RuntimeError('Unexpected CLI tool event '+label)
    if not any(x.get('type')=='turn.completed' for x in ev):raise RuntimeError('No completed CLI event '+label)
    write(O/(label+'.request.json'),{'command':cmd,'cli_version':'codex-cli 0.167.1','raw_sha256':sha(raw),'prompt_sha256':sha(pp),'events_sha256':sha(events),'schema_sha256':sha(schema),'tool_events':len(bad),'backend_routing_independently_verified':False})
    return json.loads(raw.read_text()),raw

def messages(c):return [dict(role=role,content=t[key]) for t in c['turns'] for role,key in [('user','user'),('assistant','assistant')]]
def validate(c,plan):
    errs=[]; m=messages(c); turns=c['turns']
    if c['family']!=plan['family']:errs.append('family differs from plan')
    if len(turns)!=plan['turns']:errs.append(f"must have planned {plan['turns']} exchanges, got {len(turns)}")
    if sum(len(x['content'].split()) for x in m)>380:errs.append('conversation exceeds380 words')
    if any(len(t['assistant'].split())>70 for t in turns):errs.append('reply exceeds70 words')
    probe=c['recall_probe']
    if c['family']=='memory' and (not probe or not (1<=probe['support_turn']<probe['probe_turn']<=len(turns)) or probe['probe_turn']-probe['support_turn']<3):errs.append('memory annotation missing or gap<2 intervening')
    encs=[]; prompts=[]; lens=[]
    try:
      for enabled in [False,True]:
        policies=[{'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []}]*len(turns)
        e=encode_conversation(TOK,m,policies=policies,context=2048)
        a=[s['end']-s['start'] for s in e['spans'] if s['kind']=='assistant_text']; b=[s['end']-s['start'] for s in e['spans'] if s['kind']=='assistant_end']
        assert len(a)==len(b)==len(turns)
        lens.extend(x+y for x,y in zip(a,b));assert max(lens)<=256
        for j in range(0,len(m),2):
          p=encode_conversation(TOK,m[:j+1],policies=policies[:j//2+1],for_generation=True,context=2048,reply_budget=256)
          assert e['ids'][:len(p['ids'])]==p['ids'];prompts.append(len(p['ids']))
        encs.append({'tools_enabled':enabled,'tokens':len(e['ids']),'assistant_targets':sum(e['mask'])})
    except Exception as ex:errs.append('Actual native2048 encoding/prefix/reserve failure: '+str(ex)+'. Shorten naturally without removing required reasoning/state; no truncation.')
    return errs,{'encoding':encs,'max_generation_prompt':max(prompts,default=0),'max_reply_targets':max(lens,default=0),'reply_budget':256}

def review(label,convs,plans):
    inputs=[{'group':c['group'],'family':c['family'],'content_sha256':digest(messages(c)),'messages':messages(c),'recall_probe':c['recall_probe']} for c in convs]
    prompt=RULES+'\nYou are a fresh-session rigorous FULL reviewer. Generator notes and hidden scenario plans are absent. Judge factual support ONLY from the messages shown; never supply unstated facts from a family label or guessed intended scenario. Review EVERY assistant reply, with one turn_reviews entry per1-based exchange and specific content-aware rationale. Find omissions, contradictions, wrong English, unsupported assertion/consent, timing errors, unnatural quiz scaffolding, duplicate/cosmetic scenario, and inaccurate recall support (including later echoes). Do not rubberstamp. decision accept ONLY all turns pass and plan followed/distinct; any issue decision revise or reject, provide exact repair instructions. memory_annotation_valid=true for null nonmemory, otherwise only if actual target needs earlier state and latest support gap>=2intervening. If memoryinvalid revise. Do not write dialogue; describe defects. Echo exact supplied content_sha256. Review all supplied rows:\n'+json.dumps(inputs,ensure_ascii=False)
    specialized=[]
    for inp in inputs:
      variant=json.loads(json.dumps(item));variant['properties']['group']['enum']=[inp['group']];variant['properties']['content_sha256']['enum']=[inp['content_sha256']];specialized.append(variant)
    schema_path=R/(label+'.schema.json');write(schema_path,{'type':'object','properties':{'reviews':{'type':'array','items':{'anyOf':specialized}}},'required':['reviews'],'additionalProperties':False})
    retained_prompt=O/(label+'.prompt.txt')
    cached_request=O/(label+'.request.json')
    actual_prompt=retained_prompt.read_text() if cached_request.exists() else prompt
    out,path=cli(label,actual_prompt,schema_path)
    by={x['group']:x for x in out['reviews']}; receipts={c['group']:path for c in convs}
    if set(by)!={x['group'] for x in convs}:raise RuntimeError('review group coverage '+label)
    for c in convs:
      rr=by[c['group']]; n=len(c['turns'])
      if rr['content_sha256']!=digest(messages(c)) or sorted(x['turn'] for x in rr['turn_reviews'])!=list(range(1,n+1)):
        single=[x for x in inputs if x['group']==c['group']]
        single_prompt=prompt[:prompt.rfind('\n')+1]+json.dumps(single,ensure_ascii=False)
        single_schema=R/(label+'-binding-retry-'+c['group']+'.schema.json');variant=next(v for v in specialized if v['properties']['group']['enum']==[c['group']]);write(single_schema,{'type':'object','properties':{'reviews':{'type':'array','items':variant}},'required':['reviews'],'additionalProperties':False})
        replacement,repair_path=cli(label+'-binding-retry-'+c['group'],single_prompt,single_schema)
        assert len(replacement['reviews'])==1 and replacement['reviews'][0]['group']==c['group']
        rr=replacement['reviews'][0];by[c['group']]=rr;receipts[c['group']]=repair_path
      if rr['content_sha256']!=digest(messages(c)) or sorted(x['turn'] for x in rr['turn_reviews'])!=list(range(1,n+1)):raise RuntimeError('review binding/turn coverage '+c['group'])
      if any(not x['rationale'].strip() for x in rr['turn_reviews']):raise RuntimeError('empty rationale')
    return by,receipts

def batch(index,plans):
    label=f'b{index:02d}'; overrides=json.loads((R/'plan-overrides.json').read_text()) if (R/'plan-overrides.json').exists() else {}; plans=[overrides.get(x['group'],x) for x in plans]; planp=R/(label+'.plan.json');write(planp,plans);planmap={x['group']:x for x in plans}
    generation,raw=cli(label+'-g0',RULES+'\nGenerate exactly these preassigned distinct plans, preserve group/family/exchange count. author_review_notes may record rationale but will not be shown to fresh reviewer. Output all and only these plans:\n'+json.dumps(plans),GEN_SCHEMA)
    pending=generation['conversations'];accepted=[];history=[]
    for revision in range(3):
      if {x['group'] for x in pending} != set(planmap):raise RuntimeError('generation plan coverage '+label)
      checks={c['group']:validate(c,planmap[c['group']]) for c in pending}
      rev,rp=review(label+f'-r{revision}',pending,planmap)
      defects=[]
      for c in pending:
        rr=rev[c['group']];review_path=rp[c['group']];err,enc=checks[c['group']]
        if rr['decision']!='accept' or any(t['decision']!='pass' for t in rr['turn_reviews']) or not rr['memory_annotation_valid'] or not rr['distinct_scenario']:err=err+[rr]
        if err: defects.append({'conversation':c,'defects':err,'plan':planmap[c['group']]})
        else:
          row={'group':c['group'],'family':c['family'],'messages':messages(c),'recall_probe':c['recall_probe'],'generation':{'interface':'codex exec','requested_model':'gpt-6.1-terra','cli_version':'codex-cli 0.167.1','raw_artifact':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw)},'review_receipts':[{'path':str(review_path.relative_to(ROOT)),'sha256':sha(review_path)}],'plan_receipt':{'path':str(planp.relative_to(ROOT)),'sha256':sha(planp)},'content_sha256':digest(messages(c)),'training_admitted':False,'independent_release_review':False,**enc}
          accepted.append(row)
      history.append({'revision':revision,'reviews':sorted({str(x) for x in rp.values()}),'failed_groups':[d['conversation']['group'] for d in defects]})
      write(R/(label+'.history.json'),history)
      if not defects:break
      if revision==2:
        write(R/(label+'.rejected.json'),defects);break
      planmap={d['conversation']['group']:d['plan'] for d in defects}
      generation,raw=cli(label+f'-g{revision+1}',RULES+'\nRevise ONLY these failing scenarios. Preserve planned group/family/turn count, fix every supplied issue. Return complete revised conversations; do not add others. This is the last repair if revision2.\n'+json.dumps(defects,ensure_ascii=False),GEN_SCHEMA)
      pending=generation['conversations']
    (R/(label+'.accepted.jsonl')).write_text(''.join(json.dumps(a,ensure_ascii=False)+'\n' for a in accepted))
    with LOCK:
      allrows=[]
      for p in sorted(R.glob('b*.accepted.jsonl')):allrows.extend(json.loads(l) for l in p.read_text().splitlines())
      quarantine=json.loads((R/'quarantine.json').read_text()) if (R/'quarantine.json').exists() else {}
      allrows=[a for a in allrows if a['group'] not in quarantine]
      (R/'accepted.jsonl').write_text(''.join(json.dumps(a,ensure_ascii=False)+'\n' for a in allrows))
      write(R/'progress.json',{'accepted':len(allrows),'assistant_turns':sum(len(x['messages'])//2 for x in allrows),'completed_batches':[p.name for p in R.glob('b*.accepted.jsonl')],'goal':240,'staging_only':True,'time':time.time()})
      print(label,len(accepted),'accepted; cumulative',len(allrows),flush=True)
    return accepted

if __name__=='__main__':
  plans=json.loads((O/'plans.raw.json').read_text())['plans']
  assert len(plans)==240 and len({p['group'] for p in plans})==240
  write(R/'scenario-plan.json',{'plans':plans,'raw_artifact':str((O/'plans.raw.json').relative_to(ROOT)),'raw_sha256':sha(O/'plans.raw.json'),'existing_scenarios_sha256':sha(R.parent/'existing-scenarios.json'),'planned_before_generation':True})
  futures=[]
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for i in range(12):
      if not (R/f'b{i+1:02d}.accepted.jsonl').exists():futures.append(pool.submit(batch,i+1,plans[i*20:(i+1)*20]))
    for f in concurrent.futures.as_completed(futures):
      try:f.result()
      except Exception as ex:
        print('BATCH ERROR',repr(ex),flush=True);traceback.print_exc()
