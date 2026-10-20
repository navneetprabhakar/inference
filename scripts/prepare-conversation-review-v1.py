"""Freeze a source-stratified direct review sample before any new gradients."""
# Creator: Navneet Prabhakar
import collections,json
from pathlib import Path
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/conversation-review-v1')
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 candidates=[json.loads(l) for l in Path('data/conversation-screen-v1/candidates.jsonl').open()];pools={}
 for r in candidates:pools.setdefault(r['source'],[]).append(r)
 for s in pools:pools[s].sort(key=lambda r:digest(['conversation-direct-review-v1',r['row_index']]))
 # Review64 complete dialogues across sources; grouping may remove additional rows later.
 selected=[]
 while len(selected)<64:
  for s in sorted(pools):
   if pools[s] and len(selected)<64:selected.append(pools[s].pop())
 ROOT.mkdir()
 with (ROOT/'sample.jsonl').open('x') as f:
  for i,r in enumerate(selected):f.write(json.dumps(dict(index=i,record=r,record_sha256=digest(r)),ensure_ascii=False,sort_keys=True)+'\n')
 (ROOT/'preparation.json').write_text(json.dumps(dict(creator='Navneet Prabhakar',sample_sha256=sha(ROOT/'sample.jsonl'),candidate_sha256=sha('data/conversation-screen-v1/candidates.jsonl'),selection='Deterministic round-robin original constituent strata before direct review; final component dedup/protected-family exclusion still required',training_approved=False),indent=2)+'\n')
 for i,r in enumerate(selected):
  print('\nREVIEW',i,'ROW',r['row_index'],'SOURCE',r['source'])
  for m in r['messages']:print(m['role']+': '+m['content'])
if __name__=='__main__':main()
