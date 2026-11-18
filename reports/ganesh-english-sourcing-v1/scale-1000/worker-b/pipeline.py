import concurrent.futures,hashlib,json,pathlib,subprocess,sys,time,threading
ROOT=pathlib.Path(__file__).resolve().parents[4]; R=pathlib.Path(__file__).resolve().parent; O=ROOT/'runs/ganesh-english-sourcing-v1/scale-1000/worker-b'
sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
TOK=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
GEN=ROOT/'reports/ganesh-english-sourcing-v1/terra-generation-schema.json'
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def digest(v): return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def obj(props):return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
S={'type':'string'}; I={'type':'integer'}
review_schema=obj({'reviews':{'type':'array','items':obj({'group':S,'messages_sha256':S,'decision':{'type':'string','enum':['pass','revise']},'turn_reviews':{'type':'array','items':obj({'turn':I,'verdict':{'type':'string','enum':['pass','fail']},'rationale':S})},'recall':obj({'valid':{'type':'boolean'},'last_support_turn':I,'probe_turn':I,'focus':S,'rationale':S}),'issues':{'type':'array','items':S}})}})
(R/'review-schema.json').write_text(json.dumps(review_schema))
def cli(name,prompt,schema):
 pp=O/(name+'.prompt.txt'); out=O/(name+'.raw.json')
 if out.exists():
  audit_cli(name,schema)
  return json.loads(out.read_text()),out
 pp.write_text(prompt)
 cmd=['codex','exec','--ignore-user-config','--ephemeral','--model','gpt-6.1-terra','--sandbox','read-only','--cd',str(O),'--json','--output-schema',str(schema),'--output-last-message',str(out),'-']
 with pp.open() as stdin,(O/(name+'.events.jsonl')).open('w') as events,(O/(name+'.stderr.log')).open('w') as err:
  result=subprocess.run(cmd,stdin=stdin,stdout=events,stderr=err,timeout=1200)
 if result.returncode: raise RuntimeError(name+' CLI failed')
 events=[json.loads(x) for x in (O/(name+'.events.jsonl')).read_text().splitlines()]
 assert any(x['type']=='turn.completed' for x in events)
 assert all(x.get('item',{}).get('type') in (None,'agent_message','reasoning') for x in events)
 audit_cli(name,schema)
 return json.loads(out.read_text()),out

def audit_cli(name,schema):
 pp=O/(name+'.prompt.txt');out=O/(name+'.raw.json');eventpath=O/(name+'.events.jsonl')
 events=[json.loads(x) for x in eventpath.read_text().splitlines()]
 assert any(x['type']=='turn.completed' for x in events)
 assert all(x.get('item',{}).get('type') in (None,'agent_message','reasoning') for x in events)
 receipt={'interface':'codex exec','requested_model':'gpt-6.1-terra','cli_version':'0.167.1','command':['codex','exec','--ignore-user-config','--ephemeral','--model','gpt-6.1-terra','--sandbox','read-only','--cd',str(O),'--json','--output-schema',str(schema),'--output-last-message',str(out),'-'],'artifacts':[{ 'path':str(p.relative_to(ROOT)), 'sha256':sha(p)} for p in (pp,schema,out,eventpath)],'turn_completed':True,'tool_events_absent':True,'backend_routing':'Requested model and local catalogue evidence only; events do not independently expose backend routing.'}
 rp=R/(name+'.request.json')
 if rp.exists():assert json.loads(rp.read_text())==receipt
 else:rp.write_text(json.dumps(receipt,indent=2))

def bound_schema(name,material):
 schema=json.loads(json.dumps(review_schema)); variants=[]
 for x in material:
  item=json.loads(json.dumps(review_schema['properties']['reviews']['items']));item['properties']['group']={'type':'string','enum':[x['group']]};item['properties']['messages_sha256']={'type':'string','enum':[x['messages_sha256']]};variants.append(item)
 schema['properties']['reviews']['items']={'anyOf':variants}
 path=R/(name+'.schema.json');path.write_text(json.dumps(schema));return path

def messages(c):return [{'role':role,'content':t[role]} for t in c['turns'] for role in ('user','assistant')]
def structural(c):
 errors=[];ms=messages(c); n=len(c['turns'])
 mp=R/'manual-issues.json'
 if mp.exists():
  entry=json.loads(mp.read_text()).get(c['group'],{})
  if entry.get('messages_sha256')==digest(ms):errors.extend(entry['issues'])
 if not 4<=n<=8:errors.append('Need4–8turn pairs')
 if sum(len(x['content'].split()) for x in ms)>380: errors.append('Whole conversation exceeds380words')
 if c['family']!='memory':errors.append('Required memory family')
 q=c['recall_probe']
 if not q or not 1<=q['support_turn']<q['probe_turn']<=n or q['probe_turn']-q['support_turn']<3: errors.append('Recall annotation lacks2intervening complete turns')
 stats=[]
 for enabled in (False,True):
  try:
   p=[{'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []}]*n
   enc=encode_conversation(TOK,ms,policies=p,context=2048)
   prefs=[]
   for j in range(0,len(ms),2):
    pref=encode_conversation(TOK,ms[:j+1],policies=p[:j//2+1],for_generation=True,context=2048,reply_budget=256)
    assert enc['ids'][:len(pref['ids'])]==pref['ids']; prefs.append(len(pref['ids']))
   lengths=[]; target=0
   for span in enc['spans']:
    if span['kind']=='assistant_text':target=span['end']-span['start']
    elif span['kind']=='assistant_end': lengths.append(target+span['end']-span['start'])
   if max(lengths)>256:errors.append('Reply exceeds256target tokens')
   stats.append({'enabled':enabled,'context':len(enc['ids']),'max_prompt':max(prefs),'max_reply':max(lengths),'target_positions':sum(enc['mask'])})
  except Exception as e:errors.append('Token check: '+str(e))
 return errors,stats

def run_batch(idx,plans,max_revisions=2):
 name=f'batch-{idx:02d}'; planpath=R/(name+'.plan.json');planpath.write_text(json.dumps(plans,indent=2))
 prompt='''Generate exactly the assigned scenarios, JSON only. No tools/file operations. All family memory. Produce natural varied English conversation4–8user/assistant pairs matching planned lengths; entire conversation<=380words; each assistant<=65words (prefer15–35), concise useful replies. Need native2K context including policy overhead. Real meaningful intervening discussion that does not rehearse the narrow recall focus. Same activity with different substantive subtopics is preferred to unrelated filler. No abrupt generic bookshelf/journal chores as arbitrary detours. Coherent natural topic development, not vocabulary mini-lessons. No repetitive edit/list/notice formula. No assistant invented facts, commitments, capabilities or user preferences; suggestions framed as suggestions. No unsafe/high-stakes advice. Corrections must correct user facts/preferences, not manufacture wrong assistant answers. Recall only after>=2 COMPLETE intervening turns since LAST mention by EITHER role; do not echo focus in intervening answers or probe. Focus narrowly on specific remembered fact/preference. Final question should demand retrieval without restating answer. IMPORTANT: At most2of12 may be direct 'what did I say/choose' recall questions. In the others, later user naturally needs a recommendation, decision, explanation or next action whose correct answer applies the remembered fact without echoing it in the prompt. Keep it concise; do not turn it into a generic list/notice/draft task. Do not simply paraphrase same probe across all12. Blend natural topical follow-ups with detours. Every conversation must be materially distinct, not a drill disguised by new nouns. Give support/probe1-based pair indices and exact focus. Include truthful self-review notes; self-review not acceptance. All text must be newly authored. Plans:\n'''+json.dumps(plans)
 cs,raw=cli(name+'-g0',prompt,GEN); current=cs['conversations']; history=[]; passed={}
 assert {x['group'] for x in current}=={p['group'] for p in plans}
 for revision in range(max_revisions+1):
  material=[{'group':c['group'],'messages_sha256':digest(messages(c)),'messages':messages(c)} for c in current]
  rp='''Fresh strict semantic review of English training examples. JSON only; no tools. Review EVERY assistant turn explicitly for grounded facts, correct pronouns/referents, natural useful English, instruction compliance, preserving meaning under corrections, no invented completion/actions, coherent multi-turn flow. Do not rubber stamp. Identify true delayed recall at a narrow focus: >=2complete intervening user/assistant pairs since LAST supporting mention by either speaker, absent answer in probe; meaningful intervening exchanges which avoid repeating/rehearsing the focused fact. Changing overall topic is NOT required. Same-activity subtopics such as materials, technique, emotional response or logistics are valid when they do not rehearse that narrow fact. Reject arbitrary unrelated filler or generic chore interludes. Do not reject a sound example merely because it stays within one activity. If absent, invalid. Record exact1-based last support/probe and focus, concrete rationale. Pass only if ALL targets correct AND valid recall AND distinct realistic scenario without filler. Number EVERY assistant turn and recall support/probe using1-based USER/ASSISTANT PAIR indices, NOT flat-message indices. First assistant=turn1, secondassistant=turn2. Each assistant turn requires pass/fail plus specific rationale grounded in that turn. If uncertain revise. Echo provided hash. No generator annotations supplied. Candidates:\n'''+json.dumps(material,ensure_ascii=False)
  reviewname=name+f'-review-v2-{revision}'
  schema=(R/(reviewname+'.schema.json')) if (R/(reviewname+'.schema.json')).exists() else (R/'review-schema.json' if (O/(reviewname+'.raw.json')).exists() else bound_schema(reviewname,material))
  reviews,reviewpath=cli(reviewname,rp,schema); rr={x['group']:x for x in reviews['reviews']};assert set(rr)=={c['group'] for c in current}
  review_paths={g:reviewpath for g in rr}
  mismatched=[m for m in material if rr[m['group']]['messages_sha256']!=m['messages_sha256']]
  if mismatched:
   repairname=reviewname+'-hash-recheck'
   repairprompt=rp.split('Candidates:\n')[0]+'Candidates:\n'+json.dumps(mismatched,ensure_ascii=False)
   repaired,repairpath=cli(repairname,repairprompt,bound_schema(repairname,mismatched))
   assert {v['group'] for v in repaired['reviews']}=={m['group'] for m in mismatched}
   for v in repaired['reviews']:rr[v['group']]=v;review_paths[v['group']]=repairpath
  bad=[]
  for c in current:
   errs,stats=structural(c);r=rr[c['group']];reviewpath=review_paths[c['group']];n=len(c['turns']);
   planned=next(p['turns'] for p in plans if p['group']==c['group'])
   if n!=planned:errs.append('Keep planned turn count: '+str(planned))
   assert r['messages_sha256']==digest(messages(c))
   if sorted(t['turn'] for t in r['turn_reviews'])==list(range(2,2*n+1,2)):
    r=json.loads(json.dumps(r));r['index_normalization']='flat message index converted to1-based pair index; original review preserved'
    for tr in r['turn_reviews']:tr['turn']//=2
    for key in ('last_support_turn','probe_turn'):r['recall'][key]=(r['recall'][key]+1)//2
   assert sorted(t['turn'] for t in r['turn_reviews'])==list(range(1,n+1))
   q=r['recall']; valid=q['valid'] and 1<=q['last_support_turn']<q['probe_turn']<=n and q['probe_turn']-q['last_support_turn']>=3
   if r['decision']!='pass' or any(t['verdict']!='pass' for t in r['turn_reviews']) or not valid:errs+=r['issues'] or ['Cold reviewer failed target or valid delayed recall']
   check={'group':c['group'],'revision':revision,'errors':errs,'stats':stats,'review':str(reviewpath.relative_to(ROOT)),'raw':str(raw.relative_to(ROOT))};history.append(check)
   if not errs:
    passed[c['group']]={'group':c['group'],'family':c['family'],'messages':messages(c),'generation':{'interface':'codex exec','requested_model':'gpt-6.1-terra','cli_version':'0.167.1','raw_artifact':str(raw.relative_to(ROOT)),'raw_sha256':sha(raw)},'review_receipts':[{'path':str(reviewpath.relative_to(ROOT)),'sha256':sha(reviewpath)}],'plan_receipt':{'path':str(planpath.relative_to(ROOT)),'sha256':sha(planpath)},'recall_probe':q,'native_checks':stats,'orchestrator_review':'pending','training_admitted':False}
   else:bad.append({'conversation':c,'issues':errs,'cold_review':r})
  (R/(name+'.checks-v2.json')).write_text(json.dumps(history,indent=2));(R/(name+'.staged.jsonl')).write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in passed.values()))
  if not bad:break
  if revision==max_revisions:
   (R/(name+'.rejected.json')).write_text(json.dumps(bad,indent=2));break
  currentjson,raw=cli(name+f'-g{revision+1}','Revise ONLY these conversations to fix every defect. JSON only, no tools. Preserve groups, memory family, natural varied4–8turnpairs, <=380whole-conversation words, <=65words per assistant. Need>=2complete substantive intervening turnpairs since LAST mention of narrow recall focus. Repair every assistant error, no unsupported facts. Exact raw revisions required. Return only revised conversations:\n'+json.dumps(bad,ensure_ascii=False),GEN)
  wanted={b['conversation']['group'] for b in bad}
  current=[c for c in currentjson['conversations'] if c['group'] in wanted];assert {c['group'] for c in current}==wanted
 print(name,'staged',len(passed),'of',len(plans),flush=True)
 return len(passed)
if __name__=='__main__':
 plans=[]
 for part in (0,1):plans+=json.loads((O/f'plan-{part}.raw.json').read_text())['scenarios']
 replacements={p['group']:p for p in json.loads((O/'plan-replacements.raw.json').read_text())['scenarios']}
 plans=[replacements.get(p['group'],p) for p in plans]
 assert len(plans)==240 and len({p['group'] for p in plans})==240
 (R/'plans.json').write_text(json.dumps(plans,indent=2))
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
  fs=[ex.submit(run_batch,i//12,plans[i:i+12]) for i in range(24,240,12)]
  for f in concurrent.futures.as_completed(fs):
   try:print('RESULT',f.result(),flush=True)
   except Exception as e:print('ERROR',repr(e),flush=True)
