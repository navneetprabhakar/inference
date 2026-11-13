import json,hashlib,collections,datetime
from pathlib import Path
from cloud_training.nano_sft import JsonlConversations,BestFitConversations,NATIVE_IGNORE,load_manifest
from cloud_training.nano_tool_lessons import validate_lesson
from nanochat.tokenizer import RustBPETokenizer
R=Path('reports/l4-qualification-v1/natural-dialogue-4k-v1');ROOT=Path('runs/natural-dialogue-4k-v1');P=ROOT/'admitted-v2'
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
source={r['id']:r for f in ROOT.glob('cohort-*/candidates.jsonl') for r in map(json.loads,f.read_text().splitlines())}
reviews={r['id']:r for f in R.glob('root-review-cohort-*.json') for r in json.loads(f.read_text())['reviews']}
assert len(source)==len(reviews)==200 and source.keys()==reviews.keys()
for k,r in reviews.items():assert r['full_dialogue_reviewed'] and r['sha256']==digest(source[k])
t=RustBPETokenizer.from_directory(str(ROOT.parent/'ownbase-v2-data/tokenizer'))
m=json.loads((P/'manifest.json').read_text());load_manifest(P/'manifest.json',m['tokenizer_sha256'],4096)
prep=json.loads((P/'preparation.json').read_text());out={};groups={};ids=set();turns=collections.Counter();families={};long_targets=0
for s in ('train','validation'):
 d=JsonlConversations(P/(s+'.jsonl'),t,m[s]['sha256'],4096)
 rows=list(map(json.loads,(P/(s+'.jsonl')).read_text().splitlines()));g=set();local=collections.Counter()
 original_tools={digest(r) for r in map(json.loads,(Path('runs/literal-state-repair-v1/admitted-v1')/(s+'.jsonl')).read_text().splitlines())}
 for i,r in enumerate(rows):
  if r['family']=='natural_dialogue_4k':
   assert set(r)=={'messages','family','provenance'}
   k=r['provenance']['candidate_id'];v=reviews[k]
   assert v['pass'] and k not in ids;ids.add(k)
   assert r['messages']==source[k]['messages'][:v.get('keep_message_count',len(source[k]['messages']))]
   assert r['provenance']['candidate_sha256']==digest(source[k])
   n=sum(x['role']=='assistant' for x in r['messages']);assert n>=2;turns[n]+=1
   assert not any('Forge' in x['content'] for x in r['messages'])
   g.add(r['provenance']['group']);local['natural']+=1
   if s=='train':long_targets+=sum(d.get(i)[1][2048:])
  else:
   assert digest(r) in original_tools;validate_lesson(r);local['tool_replay']+=1
 pack=BestFitConversations(d);target_count=0
 while True:
  try:x,y=pack.next_row()
  except StopIteration:break
  assert len(x)==len(y)==4096;target_count+=sum(v!=NATIVE_IGNORE for v in y)
 assert target_count==sum(d.target_counts)==m[s]['assistant_targets']
 assert pack.consumed==len(rows)==m[s]['sessions']
 groups[s]=g
 out[s]={'sessions':len(rows),'natural_dialogues':local['natural'],'tool_replay_dialogues':local['tool_replay'],'assistant_targets':target_count,'packed_4096_rows':pack.rows,'maximum_dialogue_tokens':max(d.lengths)}
assert not groups['train']&groups['validation']
for old in ('admitted-v1','review-batch-v2'):
 prior={r['provenance']['group'] for r in map(json.loads,(ROOT/old/'validation.jsonl').read_text().splitlines()) if r['family']=='natural_dialogue_4k'}
 assert not prior&groups['train']
assert len(ids)==147 and prep['root_reviewed']==200
state={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':'all_200_root_reviewed_final_pilot_verified','generated':200,'root_reviewed':200,'root_content_passed':186,'root_rejected':14,'awaiting_root_review':0,'natural_dialogues_admitted':len(ids),'single_exchange_excluded':39,'tool_replay_dialogues':338,'actual_trained_targets':0,'local_manifest':str((P/'manifest.json').resolve()),'length_bands':{k:sum(v.get(k,0) for v in prep['counts'].values()) for k in ('under_2048','2048_to_3071','3072_to_4096')},'substantive_assistant_turn_distribution':dict(turns),'train_assistant_targets_after_position_2048':long_targets,'packing':out,'full_4k_extension_corpus_ready':False,'maximum_admitted_dialogue_tokens':max(v['maximum_dialogue_tokens'] for v in out.values()),'generator_running':False,'vm':'No VM or cloud commands issued; VM remains required OFF. Last verified TERMINATED; live verification previously blocked by auth.','gcs_backup':'Prior admitted-v1 backup preserved. Final admitted-v2 backup pending GCP authentication; local review and validation complete.','prior_split_drift_fixed':prep['prior_cross_split_groups_quarantined_to_development'],'next_gate':'Review complete. For 4K extension, prepare clean3072-4096token substantive conversations and long tool workflows; benchmark full-model memory before training.','limitations':prep['limitations']+['Most candidates are structured planning/document-grounded conversations, not a broad casual dialogue corpus.','All five3K+generated examples rejected; zero admitted3K+coverage.','Content passes exclude39single-answer examples; no inference of model improvement from data admission.']}
for p in [R/'corpus-state.json',R/'final-review-verification.json',P/'verification.json']:p.write_text(json.dumps(state,indent=2)+'\n')
print(json.dumps(state,indent=2))
