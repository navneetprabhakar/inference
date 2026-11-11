import argparse,json,re,difflib,sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path.cwd()))
from cloud_training.nano_chat_format import encode_conversation
sys.path.insert(0,'runs/nanochat-source')
from nanochat.tokenizer import RustBPETokenizer
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);a=p.parse_args()
source=Path(a.source);state=json.loads((source/'progress.json').read_text());assert state['status']=='generation_complete_semantic_review_pending'
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
def text(row):
 t=' '.join(re.sub(r'\s+',' ',m['content'].casefold()).strip() for m in row['messages'] if m['role']=='user')
 return t,re.findall(r'\d+(?:\.\d+)?',t)
prior=[]
for f in ['reports/l4-qualification-v1/sol56-generation-v1/sol56-candidates.jsonl','reports/l4-qualification-v1/sol56-expansion-v1/candidates.jsonl','reports/l4-qualification-v1/sol56-expansion-v2/candidates.jsonl','reports/l4-qualification-v1/terra-generation-updated-cli-v1/candidates.jsonl']:
 prior.extend(text(json.loads(x)) for x in Path(f).read_text().splitlines())
kept=[];rejected=[];usage=[];seen=list(prior)
for file in sorted(source.glob('batch-*/candidates.jsonl')):
 for row in map(json.loads,file.read_text().splitlines()):
  t,nums=text(row)
  if any(nums==n and difflib.SequenceMatcher(None,t,old,autojunk=False).ratio()>.85 for old,n in seen):
   rejected.append({'batch':file.parent.name,'reason':'near_duplicate_user_prompt_with_same_numeric_signature'});continue
  seen.append((t,nums));kept.append(row)
 for event in map(json.loads,(file.parent/'events.jsonl').read_text().splitlines()):
  if event.get('usage'):usage.append(event['usage'])
positions=targets=0
for row in kept:
 r=encode_conversation(tok,row['messages'],policies=row.get('policies'));positions+=len(r['ids']);targets+=sum(r['mask'][1:])
out=Path(a.output);out.mkdir(exist_ok=False);(out/'candidates.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in kept))
receipt={'completed_utc':datetime.now(timezone.utc).isoformat(),'model':state['model'],'raw_sessions':sum(b['sessions'] for b in state['batches']),'retained_candidates':len(kept),'duplicates_removed':len(rejected),'comparison_prior_candidates':len(prior),'general_candidates':sum('policies' not in r for r in kept),'tool_candidates':sum('policies' in r for r in kept),'broker_calls_replayed_before_dedup':sum(b['broker_calls_replayed'] for b in state['batches']),'serialized_positions':positions,'assistant_targets':targets,'cli_usage':usage,'training_admitted':False,'semantic_review':'pending full human review','limits':['Dedup includes previous teacher candidates only; full training/dev filtering pending','Broker replay verifies calls/results, not paraphrase meaning'],'gcp_generation_spend':0}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');(out/'generation-progress.json').write_text(json.dumps(state,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='cli_usage'}))
