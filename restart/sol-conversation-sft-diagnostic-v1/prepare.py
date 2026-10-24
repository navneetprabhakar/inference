"""Freeze a small directly inspected SFT subset; no student operations."""
import hashlib,json,random
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1]
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def read(p):return json.loads(p.read_text())
def main():
 private=ROOT/'private';private.mkdir(exist_ok=False)
 source=PROJECT/'restart/sol-conversation-data-1000-v1/private/final-candidates.jsonl'
 rows=[json.loads(s) for s in source.read_text().splitlines()];prior=read(PROJECT/'restart/sol-conversation-data-1000-v1/private/primary-notes.json')
 chosen=[]
 for split,n in [('train',4),('development',5),('test',5)]:
  for family in sorted({r['family'] for r in rows if r['split']==split}):
   candidates=[r for r in rows if r['split']==split and r['family']==family and r['quality_clear_candidate'] and r['fits_current_context256']]
   candidates.sort(key=lambda r:(0 if prior.get(r['id'],{}).get('decision')=='pass' else 1,hashlib.sha256(('sft-diagnostic-20261024'+r['id']).encode()).hexdigest()))
   chosen+=candidates[:n]
 assert Counter(r['split'] for r in chosen)==dict(train=64,development=10,test=10)
 save(private/'selection.json',chosen)
 notes={r['id']:prior[r['id']] for r in chosen if prior.get(r['id'],{}).get('decision')=='pass'}
 save(private/'review.json',notes)
 save(ROOT/'selection-freeze.json',dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),selection_sha256=hashlib.sha256((private/'selection.json').read_bytes()).hexdigest(),documents=84,planned_splits=dict(train=64,development=10,test=10),previously_directly_reviewed=len(notes),remaining_direct_review=84-len(notes),replacement_after_draw=False))
 print(json.dumps(read(ROOT/'selection-freeze.json')))
if __name__=='__main__':main()
