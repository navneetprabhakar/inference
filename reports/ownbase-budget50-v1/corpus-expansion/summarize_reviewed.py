"""Derive review counts and accepted late supervision from immutable corpus evidence."""
import argparse,datetime,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--corpus',type=Path,required=True);a=p.parse_args();root=Path('runs/ownbase-budget50-v1/corpus-expansion');reports=Path('reports/ownbase-budget50-v1/corpus-expansion');versions=[];initial=set();selected=set();sources={}
for file in sorted(root.glob('*/root-review.json')):
 doc=json.loads(file.read_text());rows=doc.get('reviews',doc.get('rows'));assert rows is not None
 sources[str(file)]=hashlib.sha256(file.read_bytes()).hexdigest()
 for r in rows:
  assert r.get('full_dialogue_reviewed') or r.get('reviewed_all_assistant_turns')
  versions.append(r)
  if file.parent.name.startswith('cohort-'):initial.add(r['id'])
  if r.get('selected_for_supplement',r.get('admitted',False)):selected.add(r['id'])
verification=json.loads((a.corpus/'verification.json').read_text());current=json.loads((a.corpus/'manifest.json').read_text());baseline=Path('runs/long-context-corpus-v3');baseline_coverage=json.loads((baseline/'verification.json').read_text())
# V3 uses an earlier coverage schema; known counters are bound to its manifest here.
assert hashlib.sha256((baseline/'manifest.json').read_bytes()).hexdigest()=='ba6f513f6a97780f03e66b3166f897339520479a4975b5b9792e42007f8a560f'
accepted=set()
for split in ['train','validation']:
 old=(baseline/(split+'.jsonl')).read_bytes();new=(a.corpus/(split+'.jsonl')).read_bytes();assert new.startswith(old)
 for line in new[len(old):].splitlines():accepted.add(json.loads(line)['provenance']['candidate_id'])
assert accepted==selected,(accepted-selected,selected-accepted)
report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'initial_unique_scenarios':len(initial),'fully_reviewed_versions':len(versions),'content_pass_versions':sum(bool(r['content_pass']) for r in versions),'accepted_unique_scenarios':len(accepted),'new_train_targets_after3072':verification['full_corpus_coverage']['train']['assistant_targets_after_3072']-5126,'new_development_targets_after3072':verification['full_corpus_coverage']['validation']['assistant_targets_after_3072']-652,'trained_new_corpus_targets':0,'scope':'Counts derived from completed root reviews and immutable corpus; repairs/extensions are versions, not new scenarios. Unreviewed active cohorts excluded.','corpus':str(a.corpus),'manifest_sha256':hashlib.sha256((a.corpus/'manifest.json').read_bytes()).hexdigest(),'source_root_reviews_sha256':sources}
(reports/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='source_root_reviews_sha256'},indent=2))
