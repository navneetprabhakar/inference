"""Freeze the narrower rule and component-disjoint review; no admission."""
# Creator: Navneet Prabhakar
import collections,json
from pathlib import Path
from slm.data.conversation_scope import scope
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/conversation-review-v2')
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 source=Path('data/conversation-groups-v1/eligible.jsonl');report=json.loads(Path('data/conversation-groups-v1/report.json').read_text())
 if not report['complete']:raise ValueError('Complete grouping required')
 rows=[json.loads(x) for x in source.open()];prior=[json.loads(x) for x in Path('data/conversation-review-v1/direct-judgments.jsonl').open()]
 db=__import__('sqlite3').connect('file:'+str(Path('data/conversation-groups-v1/families.sqlite').resolve())+'?mode=ro',uri=True)
 blocked=set()
 for p in prior:
  if p['judgment']!='consider':
   result=db.execute('SELECT root FROM records WHERE eid=?',(str(p['row_index']),)).fetchone()
   if result:blocked.add(result[0])
 blocked_groups={v[0] for root in blocked for v in db.execute('SELECT group_id FROM components WHERE root=?',(root,))};db.close()
 eligible=[r for r in rows if r['split_group'] not in blocked_groups and not scope(r)]
 priorids={p['row_index'] for p in prior};pools={}
 for r in eligible:
  if r['row_index'] not in priorids:pools.setdefault(r['source'],[]).append(r)
 for s in pools:pools[s].sort(key=lambda r:digest(['conversation-direct-review-v2',r['split_group']]))
 selected=[]
 while len(selected)<64:
  before=len(selected)
  for s in sorted(pools):
   if pools[s] and len(selected)<64:selected.append(pools[s].pop())
  if len(selected)==before:raise ValueError('Insufficient independent new review families')
 ROOT.mkdir()
 for name,values in [('candidates.jsonl',eligible),('sample.jsonl',[dict(index=i,record=r,record_sha256=digest(r)) for i,r in enumerate(selected)])]:
  with (ROOT/name).open('x') as f:
   for r in values:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 (ROOT/'preparation.json').write_text(json.dumps(dict(creator='Navneet Prabhakar',source_sha256=sha(source),rule_sha256=sha('src/slm/data/conversation_scope.py'),prior_failed_review_sha256=sha('data/conversation-review-v1/report.json'),prior_journal_sha256=sha('data/conversation-review-v1/direct-judgments.jsonl'),sample_sha256=sha(ROOT/'sample.jsonl'),candidate_sha256=sha(ROOT/'candidates.jsonl'),candidates=len(eligible),by_source=dict(collections.Counter(r['source'] for r in eligible)),sample_by_source=dict(collections.Counter(r['source'] for r in selected)),training_approved=False,selection='New deterministic stratified64 group-distinct eligible dialogues; prior sampled rows excluded from new sample. Narrower rule fixed before reading. Purposive sample not a corpus reliability estimate.'),indent=2)+'\n')
 for i,r in enumerate(selected):
  print('\nREVIEW',i,'ROW',r['row_index'],'SOURCE',r['source'])
  for m in r['messages']:print(m['role']+': '+m['content'])
if __name__=='__main__':main()
