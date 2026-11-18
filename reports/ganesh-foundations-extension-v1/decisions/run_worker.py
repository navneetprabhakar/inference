import concurrent.futures, hashlib, json, os, pathlib, subprocess, sys, threading, time, traceback
ROOT=pathlib.Path('/Users/navneetprabhakar/Documents/git/image/inference'); R=ROOT/'reports/ganesh-foundations-extension-v1/decisions'; O=ROOT/'runs/ganesh-foundations-extension-v1/decisions'
sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
TOK=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
LOCK=threading.Lock()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
GEN_SCHEMA=R/'generation-schema.json'
REVIEW_SCHEMA=R/'review-schema.json'
item={'type':'object','properties':{'group':{'type':'string'},'content_sha256':{'type':'string'},'decision':{'type':'string','enum':['accept','revise','reject']},'reason':{'type':'string'},'turn_reviews':{'type':'array','items':{'type':'object','properties':{'turn':{'type':'integer'},'decision':{'type':'string','enum':['pass','fail']},'rationale':{'type':'string'}},'required':['turn','decision','rationale'],'additionalProperties':False}},'memory_annotation_valid':{'type':'boolean'},'distinct_scenario':{'type':'boolean'}},'required':['group','content_sha256','decision','reason','turn_reviews','memory_annotation_valid','distinct_scenario'],'additionalProperties':False}
write(REVIEW_SCHEMA,{'type':'object','properties':{'reviews':{'type':'array','items':item}},'required':['reviews'],'additionalProperties':False})
RULES="""Create natural, varied, low-stakes decision conversations. Clarify objectives when necessary, explore tradeoffs and reversible trials, adapt to updated constraints, state uncertainty and do not invent user priorities or consent. Do not claim actual tool calls or external actions. Avoid medical, legal and financial advice; avoid repetitive You could openings. No opaque chain-of-thought: concise useful reasons only. No memory probes: recall_probe must be null. 4–6 exchanges as planned; each assistant reply under 70 words. Use no tools. Return exactly schema JSON."""
def cli(label,prompt,schema):
    pp=O/(label+'.prompt.txt'); pp.write_text(prompt)
    raw=O/(label+'.raw.json'); events=O/(label+'.events.jsonl'); err=O/(label+'.stderr.log')
    cmd=['codex','exec','--model','gpt-6.1-terra','--ignore-user-config','--ephemeral','--sandbox','read-only','--cd',str(O),'--json','--output-schema',str(schema),'--output-last-message',str(raw),'-']
    with pp.open() as inp,events.open('w') as out,err.open('w') as errors:
      p=subprocess.run(cmd,stdin=inp,stdout=out,stderr=errors,timeout=900)
    if p.returncode or not raw.exists():raise RuntimeError(f'CLI failed {label}: {p.returncode}')
    ev=[json.loads(l) for l in events.read_text().splitlines()]
    bad=[x for x in ev if x.get('type','').startswith('item.') and x.get('item',{}).get('type') not in ['agent_message','reasoning']]
    if bad:raise RuntimeError('Unexpected CLI tool event '+label)
    if not any(x.get('type')=='turn.completed' for x in ev):raise RuntimeError('No completed CLI event '+label)
    write(O/(label+'.request.json'),{'command':cmd,'cli_version':'codex-cli 0.167.1','raw_sha256':sha(raw),'prompt_sha256':sha(pp),'events_sha256':sha(events),'tool_events':len(bad),'backend_routing_independently_verified':False})
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
    prompt=RULES+'\nYou are a fresh-session rigorous FULL reviewer. Only actual dialogue messages establish facts; hidden author plans are not provided and must never be inferred. Generator self-review notes are deliberately absent. Review EVERY assistant reply, with one turn_reviews entry per1-based exchange and specific content-aware rationale. Find omissions, contradictions, wrong English, unsupported assertion/consent, timing errors, unnatural quiz scaffolding, duplicate/cosmetic scenario, and inaccurate recall support (including later echoes). Do not rubberstamp. decision accept ONLY all turns pass and plan followed/distinct; any issue decision revise or reject, provide exact repair instructions. memory_annotation_valid=true for null nonmemory, otherwise only if actual target needs earlier state and latest support gap>=2intervening. If memoryinvalid revise. Do not write dialogue; describe defects. Echo exact supplied content_sha256. Review all supplied rows:\n'+json.dumps(inputs,ensure_ascii=False)
    out,path=cli(label,prompt,REVIEW_SCHEMA)
    by={x['group']:x for x in out['reviews']}
    if set(by)!={x['group'] for x in convs}:raise RuntimeError('review group coverage '+label)
    for c in convs:
      rr=by[c['group']]; n=len(c['turns'])
      if rr['content_sha256']!=digest(messages(c)) or sorted(x['turn'] for x in rr['turn_reviews'])!=list(range(1,n+1)):raise RuntimeError('review binding/turn coverage '+c['group'])
      if any(not x['rationale'].strip() for x in rr['turn_reviews']):raise RuntimeError('empty rationale')
    return by,path

def batch(index,plans):
    label=f'b{index:02d}'; planp=R/(label+'.plan.json');write(planp,plans);planmap={x['group']:x for x in plans}
    generation,raw=cli(label+'-g0',RULES+'\nGenerate exactly these preassigned distinct plans, preserve group/family/exchange count. author_review_notes may record rationale but will not be shown to fresh reviewer. Output all and only these plans:\n'+json.dumps(plans),GEN_SCHEMA)
    pending=generation['conversations'];accepted=[];history=[]
    for revision in range(3):
      if {x['group'] for x in pending} != set(planmap):raise RuntimeError('generation plan coverage '+label)
      checks={c['group']:validate(c,planmap[c['group']]) for c in pending}
      rev,rp=review(label+f'-r{revision}',pending,planmap)
      defects=[]
      for c in pending:
        rr=rev[c['group']];err,enc=checks[c['group']]
        if rr['decision']!='accept' or any(t['decision']!='pass' for t in rr['turn_reviews']) or not rr['memory_annotation_valid'] or not rr['distinct_scenario']:err=err+[rr]
        if err: defects.append({'conversation':c,'defects':err,'plan':planmap[c['group']]})
        else:
          row={'group':c['group'],'family':c['family'],'messages':messages(c),'recall_probe':c['recall_probe'],'generation':{'interface':'codex exec','requested_model':'gpt-6.1-terra','cli_version':'codex-cli 0.167.1','raw_artifact':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw)},'review_receipts':[{'path':str(rp.relative_to(ROOT)),'sha256':sha(rp)}],'plan_receipt':{'path':str(planp.relative_to(ROOT)),'sha256':sha(planp)},'content_sha256':digest(messages(c)),'training_admitted':False,'independent_release_review':False,**enc}
          accepted.append(row)
      history.append({'revision':revision,'review':str(rp),'failed_groups':[d['conversation']['group'] for d in defects]})
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
      (R/'accepted.jsonl').write_text(''.join(json.dumps(a,ensure_ascii=False)+'\n' for a in allrows))
      write(R/'progress.json',{'accepted':len(allrows),'assistant_turns':sum(len(x['messages'])//2 for x in allrows),'completed_batches':[p.name for p in R.glob('b*.accepted.jsonl')],'goal':24,'staging_only':True,'time':time.time()})
      print(label,len(accepted),'accepted; cumulative',len(allrows),flush=True)
    return accepted

if __name__=='__main__':
  plans=json.loads((O/'plan.raw.json').read_text())['scenarios']
  assert len(plans)==24 and len({p['group'] for p in plans})==24
  for i,p in enumerate(plans):p['turns']=[4,5,6][i%3]
  write(R/'scenario-plan.json',{'plans':plans,'raw_artifact':str((O/'plan.raw.json').relative_to(ROOT)),'raw_sha256':sha(O/'plan.raw.json'),'planned_before_generation':True})
  futures=[]
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for i in range(4):
      if not (R/f'b{i+1:02d}.accepted.jsonl').exists():futures.append(pool.submit(batch,i+1,plans[i*6:(i+1)*6]))
    for f in concurrent.futures.as_completed(futures):
      try:f.result()
      except Exception as ex:
        print('BATCH ERROR',repr(ex),flush=True);traceback.print_exc()
