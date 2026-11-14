"""Reproducible full-packet audit using the actual tokenizer, renderer and packer."""
import sys,json,hashlib,collections,math
from pathlib import Path
sys.path.insert(0,str(Path('.').resolve()));sys.path.insert(0,str(Path('runs/nanochat-source').resolve()))
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,training_example
from cloud_training.nano_sft import JsonlConversations,FiniteEpochDataset,BestFitConversations
from tools import execute
root=Path('runs/ownbase-budget50-v1/sft-2k');tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();splits={};fingerprints={};shapes={}
for split in ['train','validation']:
 rows=[json.loads(x) for x in (root/(split+'.jsonl')).read_text().splitlines()];families={};policy=collections.Counter();prefix_checks=0;tool_checks=0;fingerprints[split]=set();shapes[split]=set()
 for row in rows:
  rendered=encode_conversation(tok,row['messages'],policies=row.get('policies'));targets=training_example(rendered)['assistant_target_count'];family=row['family'];f=families.setdefault(family,{'sessions':0,'assistant_targets':0,'user_turns':0,'max_context':0});f['sessions']+=1;f['assistant_targets']+=targets;f['max_context']=max(f['max_context'],len(rendered['ids']))
  assert all(not any(rendered['mask'][s['start']:s['end']]) for s in rendered['spans'] if s['kind'] in ['user_prompt','tool_result_json','user_start','assistant_start'])
  policies=row.get('policies');users=0;called=False
  for i,m in enumerate(row['messages']):
   if m['role']=='user':
    if users:policy[('enabled' if enabled else 'disabled')+('_call' if called else '_no_call')]+=1
    users+=1;f['user_turns']+=1;enabled=bool(policies and policies[users-1]['permit_calls']);called=False
   if m['role']=='assistant':
    pre=encode_conversation(tok,row['messages'][:i],policies=policies[:users] if policies else None,for_generation=True,reply_budget=1)
    assert pre['ids']==rendered['ids'][:len(pre['ids'])];prefix_checks+=1
    if 'tool_call' in m:
     called=True;call=m['tool_call'];obs=row['messages'][i+1]['record'];actual=execute(call['name'],call['arguments']);assert obs['ok'] and math.isclose(actual,obs['data']['result'],rel_tol=1e-12,abs_tol=1e-12);tool_checks+=1
  policy[('enabled' if enabled else 'disabled')+('_call' if called else '_no_call')]+=1
  fingerprints[split].add(hashlib.sha256(json.dumps(row['messages'],sort_keys=True).encode()).hexdigest())
 splits[split]={'sessions':len(rows),'families':families,'policy_turn_counts':dict(policy),'train_serve_prefix_checks':prefix_checks,'tool_result_replays':tool_checks,'assistant_targets':sum(x['assistant_targets'] for x in families.values()),'jsonl_sha256':sha(root/(split+'.jsonl'))}
train=JsonlConversations(root/'train.jsonl',tok,sha(root/'train.jsonl'));epochs=FiniteEpochDataset(train,8);pack=BestFitConversations(epochs);rows=[json.loads(x) for x in (root/'train.jsonl').read_text().splitlines()];updates=[];parts=[]
while True:
 try:parts.append(pack.next_indices())
 except StopIteration:break
for start in range(0,len(parts),4):
 counts=collections.Counter()
 for ids in parts[start:start+4]:
  for i in ids:counts[rows[i%len(rows)]['family']]+=train.target_counts[i%len(rows)]
 updates.append({'step':len(updates)+1,'assistant_targets_by_family':dict(counts)})
report={'schema':1,'manifest_sha256':sha(root/'manifest.json'),'splits':splits,'exact_train_dev_message_overlap':len(fingerprints['train']&fingerprints['validation']),'packed_rows':len(parts),'updates':len(updates),'last_update':updates[-1],'packing_update_target_mix':updates,'limits':'Semantic correctness of natural answers and near-duplicate/semantic split leakage are not established by prefix, mask and exact-overlap checks.'}
Path('reports/quality-rca-v1/packet-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='packing_update_target_mix'},indent=2))
