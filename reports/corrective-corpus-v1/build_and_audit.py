"""Materialize reviewed source scenarios; verify real tokenizer/masks/tool references.
Does not admit training, load a model, allocate compute or open release outputs.
"""
import sys,json,hashlib,math,datetime,collections,re,ast
from pathlib import Path
if (Path(__file__).resolve().parent/'freeze.json').exists():raise SystemExit('Frozen corpus/release packet: create a new version; do not regenerate in place.')
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runs/nanochat-source'))
from source_dialogues import NATURAL,DEV_NATURAL
from source_tools import TOOLS,DEV_TOOLS
from source_release import NATURAL_RELEASE,STATE_RELEASE,TOOL_RELEASE
from tools import execute,FixtureSession
from cloud_training.nano_chat_format import encode_conversation,training_example
from cloud_training.nano_quality import validate_suite
from nanochat.tokenizer import RustBPETokenizer
P=Path(__file__).resolve().parent;T=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,value):
 p=P/name;p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');return sha(p)
def policy(enabled):return {'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []}
def natural(items,split):
 out=[]
 for i,(ident,turns) in enumerate(items):
  category='code_state' if (split=='train' and i>=25) or (split=='development' and ident in ['dev_fabric','dev_html','dev_predicate','dev_code_set','dev_location']) else 'natural'
  out.append({'id':ident,'source_group':ident,'category':category,'turns':[{'user':u,'answer':a,'policy':policy((i+j)%3==0)} for j,(u,a) in enumerate(turns)]})
 return out
def tool(items):return [{'id':ident,'source_group':ident,'category':'tool','turns':[{**t,'policy':policy(True)} for t in turns]} for ident,turns in items]
train=natural(NATURAL,'train')+tool(TOOLS);dev=natural(DEV_NATURAL,'development')+tool(DEV_TOOLS)
release=[]
for category,items in [('natural',NATURAL_RELEASE),('code_state',STATE_RELEASE)]:
 for i,(ident,turns) in enumerate(items):release.append({'id':ident,'source_group':ident,'category':category,'turns':[{'user':u,'answer':a,'policy':policy((i+j)%2==0)} for j,(u,a) in enumerate(turns)]})
release+=tool(TOOL_RELEASE)
release+=json.loads((P/'long-release-source.json').read_text())
checks=[]
def observed(t,cid):
 call=t['call']
 try:value=execute(call['name'],call['arguments'])
 except ValueError as error:
  assert 'error' in t and str(error)==t['error'],(t,error)
  checks.append({'kind':'expected_tool_error','user':t['user'],'error':str(error)})
  return {'call_id':cid,'source':'offline fixture','schema_version':1,'name':call['name'],'ok':False,'error':str(error)}
 assert 'error' not in t and math.isclose(value,t['value'],rel_tol=1e-12,abs_tol=1e-12),(t,value)
 checks.append({'kind':'numeric_reference_replay','user':t['user'],'expected':t['value'],'actual':value})
 return {'call_id':cid,'source':'offline fixture','schema_version':1,'name':call['name'],'arguments':call['arguments'],'ok':True,'data':{'result':value}}
def canonical(s,split):
 messages=[];calls=0;broker=FixtureSession()
 for t in s['turns']:
  broker.start_turn(**t['policy'])
  messages.append({'role':'user','content':t['user']})
  if 'call' in t:
   calls+=1;cid=f'c{calls}';expected=observed(t,cid)
   actual=broker.propose(json.dumps(t['call']),assistant_call_boundary=True);actual.pop('timestamp')
   assert actual==expected,(s['id'],actual,expected)
   messages.extend([{'role':'assistant','tool_call':t['call'],'call_id':cid},{'role':'tool','call_id':cid,'record':actual}])
  messages.append({'role':'assistant','content':t['answer']})
 return {'id':s['id'],'family':s['category'],'messages':messages,'policies':[t['policy'] for t in s['turns']],'provenance':{'kind':'interactive_codex_authored','source_group':s['source_group'],'split':split,'semantic_review_receipt':'semantic-review.json','training_admitted':False}}
corpora={};stats={};prefixchecks=0
for split,items in [('train',train),('development',dev),('release_reference',release)]:
 rows=[];modes=collections.Counter();families=collections.Counter();target_mass=collections.Counter();lengths=[];answerlens=[]
 for s in items:
  row=canonical(s,split);encoded=encode_conversation(T,row['messages'],policies=row['policies'],context=4096 if split=='release_reference' else 2048);ex=training_example(encoded)
  lengths.append(len(encoded['ids']));families[s['category']]+=1;target_mass[s['category']]+=ex['assistant_target_count']
  for t in s['turns']:
   modes[('enabled' if t['policy']['permit_calls'] else 'disabled')+('_call' if 'call' in t else '_no_call')]+=1
   answerlens.append(len(T.encode(t['answer'])))
  for span in encoded['spans']:
   if span['kind'] in ['user_prompt','tool_result_json','user_start','assistant_start','tool_result_end']:assert not any(encoded['mask'][span['start']:span['end']])
   if span['kind'] in ['assistant_end','tool_call_end']:assert all(encoded['mask'][span['start']:span['end']])
  users=0
  for i,m in enumerate(row['messages']):
   if m['role']=='user':users+=1
   if m['role']=='assistant':
    prefix=encode_conversation(T,row['messages'][:i],policies=row['policies'][:users],for_generation=True,context=4096 if split=='release_reference' else 2048,reply_budget=192)
    assert prefix['ids']==encoded['ids'][:len(prefix['ids'])];prefixchecks+=1
  rows.append(row)
 corpora[split]=rows
 stats[split]={'sessions':len(rows),'turns':sum(len(s['turns']) for s in items),'policy_action_turns':dict(modes),'family_sessions':dict(families),'assistant_targets_by_family':dict(target_mass),'assistant_targets':sum(target_mass.values()),'max_framed_tokens':max(lengths),'max_reference_text_tokens':max(answerlens),'median_reference_text_tokens':sorted(answerlens)[len(answerlens)//2]}
# Exact normalized-prompt and source-group exclusion; near overlap is reviewed, not hidden.
normalize=lambda text:' '.join(text.casefold().split())
splititems={'train':train,'development':dev,'release':release};groups={k:{s['source_group'] for s in v} for k,v in splititems.items()};prompts={k:{normalize(t['user']) for s in v for t in s['turns']} for k,v in splititems.items()};overlap={}
for a,b in [('train','development'),('train','release'),('development','release')]:
 shared=groups[a]&groups[b];same=prompts[a]&prompts[b];assert not shared and not same,(a,b,shared,same);overlap[a+'/'+b]={'source_groups_shared':0,'exact_normalized_user_prompts_shared':0}
# Five-word shingles expose lexical template collisions without treating common one-word answers as leaks.
def shingles(text):
 words=re.findall(r'[a-z0-9]+',text.lower());return {tuple(words[i:i+5]) for i in range(len(words)-4)}
near=[]
for a,b in [('train','development'),('train','release'),('development','release')]:
 for sa in splititems[a]:
  for sb in splititems[b]:
   for ia,ta in enumerate(sa['turns']):
    aa=shingles(ta['user'])
    for ib,tb in enumerate(sb['turns']):
     bb=shingles(tb['user']);score=len(aa&bb)/len(aa|bb) if aa|bb else 0
     if score>=.45:near.append({'splits':[a,b],'sessions':[sa['id'],sb['id']],'turns':[ia,ib],'jaccard':score,'texts':[ta['user'],tb['user']]})
# Independent Python-semantic and literal/word-count constraints, not inferred from reference text length.
codechecks=[('code_list',len([4,9,2]),3),('code_slice','planet'[:3],'pla'),('code_slice_tail','planet'[-2:],'et'),('code_condition',7>10,False),('code_default',{'mode':'quiet'}.get('speed','slow'),'slow'),('code_loop',list(range(1,4)),[1,2,3]),('code_boolean_empty',bool([]),False),('code_boolean_nonempty',bool([0]),True),('release_filter',[x for x in [1,4,7,10] if x>5],[7,10]),('release_count','cocoa'.count('o'),2),('release_replace','cocoa'.replace('o','u'),'cucua'),('release_membership','ab' in 'cabinet',True),('release_false_membership','ba' in 'cabinet',False),('dev_set',len({2,2,5}),2)]
a=[3];b=a;b.append(8);codechecks.append(('alias',a,[3,8]));a=[[1]];b=a.copy();b[0].append(2);codechecks.extend([('shallow_copy',a,[[1,2]]),('outer_identity',a is b,False)])
for name,actual,expected in codechecks:assert actual==expected,(name,actual,expected)
for ident,index,count in [('sign',2,5),('unknown_attachment',2,6),('alternatives',2,3),('natural_stop',2,2),('dev_word_limit',0,4),('dev_word_limit',1,4)]:
 session=next(s for s in train+dev if s['id']==ident);assert len(session['turns'][index]['answer'].split())==count,(ident,session['turns'][index]['answer'])
for split,rows in corpora.items():
 if split=='release_reference':continue # Keep test references in the release suite, never an SFT JSONL.
 filename='train.jsonl' if split=='train' else 'validation.jsonl'
 (P/filename).write_text(''.join(json.dumps(row,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n' for row in rows))
def suite(items,purpose):
 sessions=[]
 for s in items:
  turns=[]
  for t in s['turns']:
   rubric='Answer the current user accurately and concisely; honor format/word/literal constraints, corrections and earlier state. End the answer. Do not invent facts. '
   rubric+=('Use the actual requested tool with correct operation, arguments, observed result/error and grounded final text; equivalent commutative operand order is valid.' if 'call' in t else 'No tool call is needed or allowed by this rubric, even if tools are available.')
   turns.append({'user':t['user'],'policy':t['policy'],'exact_answers':[t['answer']],'reference_answer':t['answer'],'expected_calls':[t['call']] if 'call' in t else [],'rubric':rubric,'semantic_equivalents_allowed':True,'reference_error':t.get('error')})
  sessions.append({'id':s['id'],'source_group':s['source_group'],'category':s['category'],'turns':turns,'evaluation_kind':s.get('evaluation_kind','short_conversation')})
 result={'schema':1,'purpose':purpose,'sessions':sessions,'required_context_tokens':4096 if purpose=='heldout_release_never_train' else 2048,'scope':'Short conversation evaluation plus three explicitly structured long-record release stress cases. Exact match is diagnostic; full semantic/workflow review mandatory. Not a broad knowledge benchmark.'}
 validate_suite(result,release=purpose=='heldout_release_never_train');return result
devsha=write('development-suite.json',suite(dev,'development_only_never_train'));releasesha=write('release-suite.json',suite(release,'heldout_release_never_train'))
write('audit.json',{'schema':1,'statistics':stats,'prefix_equality_checks':prefixchecks,'tool_checks':len(checks),'tool_reference_results':checks,'split_overlap':overlap,'near_prompt_flags':near,'independent_python_checks':len(codechecks),'explicit_word_count_checks':6,'source_sha256':{p.name:sha(p) for p in [P/'source_dialogues.py',P/'source_tools.py',P/'source_release.py',P/'make_long_release.py',P/'long-release-source.json']},'tokenizer_sha256':sha(ROOT/'runs/ownbase-v2-data/tokenizer/tokenizer.pkl'),'scope_limits':['Checks do not replace semantic review.','Distinct source groups do not prove zero semantic similarity or zero overlap with unavailable historical data.','Release not executed against any model; same author as training, not an independent human evaluation team.']})
print(json.dumps({'statistics':stats,'prefix_checks':prefixchecks,'tool_checks':len(checks),'near_flags':near},indent=2))
