"""Preserve reviewed source evidence in Git without weights or raw CLI logs."""
import argparse,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--corpus',type=Path,required=True);p.add_argument('--folders',nargs='+',required=True);args=p.parse_args()
root=Path('reports/ownbase-budget50-v1/corpus-expansion');index=json.loads((root/'evidence-index.json').read_text());known={r['copy']:r for r in index}
def preserve(source,dest):
 digest=hashlib.sha256(source.read_bytes()).hexdigest()
 if str(dest) in known:
  assert known[str(dest)]['sha256']==digest and hashlib.sha256(dest.read_bytes()).hexdigest()==digest,'Refuse to change archived evidence'
  return
 dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest);index.append({'source':str(source),'copy':str(dest),'sha256':digest})
for folder in args.folders:
 src=Path('runs/ownbase-budget50-v1/corpus-expansion')/folder
 reviews={r['id']:r for r in json.loads((src/'root-review.json').read_text())['reviews']}
 for row in map(json.loads,(src/'candidates.jsonl').read_text().splitlines()):
  digest=hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode()).hexdigest();assert reviews[row['id']]['sha256']==digest and reviews[row['id']]['full_dialogue_reviewed']
 for name in ['candidates.jsonl','root-review.json','cli-review.json','code-verification.json','progress.json']:
  if (src/name).exists():preserve(src/name,root/'evidence'/folder/name)
for name in ['manifest.json','admission.json','verification.json','independent-verification.json','supplement-train.jsonl','supplement-validation.jsonl']:
 preserve(args.corpus/name,root/(args.corpus.name.removeprefix('long-context-')+'-'+name))
(root/'evidence-index.json').write_text(json.dumps(index,indent=2)+'\n');print(json.dumps({'indexed_files':len(index),'corpus':str(args.corpus),'folders':args.folders}))
