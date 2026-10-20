"""Explicit check of older Smol-SmolTalk heldouts/nonapprovals absent from prose index."""
# Creator: Navneet Prabhakar
import json,struct,sqlite3
from pathlib import Path
from slm.data.conversation_grouping import Query,facets
from slm.data.prose_screen import word_key,RequestGuard
from slm.data.stream_hash import sha
ROOT=Path('data/prior-conversation-protection-audit-v1')
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 ROOT.mkdir();order={}
 with Path('data/prefix-near-benchmark-v1/ordering-counts.bin').open('rb') as f:
  while b:=f.read(36):order[b[:32]]=struct.unpack('<I',b[32:])[0]
 stage=Path('data/smol-content-review-v2/staged');sample=[json.loads(x) for x in Path('data/smol-content-review-v2/sample.jsonl').open()];journal=[json.loads(x) for x in Path('data/smol-content-review-v2/direct-judgments.jsonl').open()]
 protected=[s['record'] for s,j in zip(sample,journal) if j['judgment']!='consider']
 for part in ('validation','test'):
  for path in stage.glob(part+'-*.jsonl'):
   protected +=[r for r in map(json.loads,path.open()) if r['source']=='HuggingFaceTB/smol-smoltalk']
 train=[json.loads(x) for x in Path('data/local-conversation-sft-v2/train.jsonl').open()];groups={r['split_group'] for r in train};trainids={r['row_index'] for r in train}
 q=Query('data/conversation-groups-v1/index',order);db=sqlite3.connect('file:'+str(Path('data/conversation-groups-v1/families.sqlite').resolve())+'?mode=ro',uri=True);hits=[];texts=[]
 for r in protected:
  fs=facets(r['messages']);texts+=list(fs.values())
  for t in fs.values():
   for facet in q.matches(t):
    for sid, in q.db.execute('SELECT source_sid FROM facet_sources WHERE sid=?',(facet,)):
     eid,root=db.execute('SELECT eid,root FROM records WHERE sid=?',(sid,)).fetchone();group=db.execute('SELECT group_id FROM components WHERE root=?',(root,)).fetchone()[0]
     if group in groups:hits.append(dict(prior_example_id=r['example_id'],new_row_index=int(eid),new_group=group))
 guard=RequestGuard(texts);contain=[]
 for r in train:
  if guard.matches('\n'.join(m['content'] for m in r['messages'])):contain.append(r['row_index'])
 q.close();db.close();report=dict(creator='Navneet Prabhakar',complete=True,passed=not hits and not contain,older_protected_rows=len(protected),protected_facets=len(texts),training_rows=len(train),near_component_hits=hits,whole_text_containment_hits=contain,query_pairs=q.pairs,train_sha256=sha('data/local-conversation-sft-v2/train.jsonl'),scope='Explicit older36 Smol heldouts and32 prior exclude/defer rows, separate from prose-population index; exact/full17-of20-shingle near checks plus whole normalized text containment.')
 (ROOT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))
 if not report['passed']:raise ValueError('Prior protected conversation exposure detected')
if __name__=='__main__':main()
