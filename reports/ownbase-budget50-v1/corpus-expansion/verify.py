"""Verify qualification traces, token lengths and source overlap; never admit."""
import sys,json,hashlib
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
from tools import FixtureSession
root=Path(sys.argv[1] if len(sys.argv)>1 else 'runs/long-context-qualification-v1')
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
def grams(messages):
 words=' '.join(m.get('content','').lower() for m in messages).split()
 return set(zip(*(words[i:] for i in range(5))))
prior=[]
for split in ['train','validation']:
 for line in Path(f'runs/long-context-corpus-v3/{split}.jsonl').read_text().splitlines():
  r=json.loads(line);prior.append((split,grams(r['messages'])))
rows=[]
for line in (root/'candidates.jsonl').read_text().splitlines():
 s=json.loads(line);b=FixtureSession();p=iter(s['policies']);pending=None;calls=0
 for m in s['messages']:
  if m['role']=='user':b.start_turn(**next(p))
  if m['role']=='assistant' and 'tool_call' in m:
   pending=b.propose(json.dumps(m['tool_call']),assistant_call_boundary=True);pending.pop('timestamp',None);assert pending['call_id']==m['call_id'];calls+=1
  if m['role']=='tool':assert pending==m['record'];pending=None
 assert pending is None
 g=grams(s['messages']);overlap=max((len(g&h)/max(1,len(g|h)) for _,h in prior),default=0)
 row={'id':s['id'],'sha256':hashlib.sha256(json.dumps(s,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'replayed_calls':calls,'max_prior_5gram_jaccard':overlap,'substantive_review_required':True}
 try:
  e=encode_conversation(tok,s['messages'],policies=s['policies'],context=4096)
  row.update(context_tokens=len(e['ids']),assistant_targets=sum(e['mask'][1:]),assistant_targets_after_2048=sum(e['mask'][2048:]),assistant_targets_after_3072=sum(e['mask'][3072:]),fits=True)
 except ValueError as ex:
  if 'Context overflow' not in str(ex):raise
  row.update(fits=False,reason='context_overflow')
 rows.append(row)
 prior.append(('current_cohort',g))
assert len({r['id'] for r in rows})==len(rows)
report={'rows':rows,'generated':len(rows),'trained':0,'admitted_by_this_script':0}
(root/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
