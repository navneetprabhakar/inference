"""Freeze only parent-reviewed teacher batches; source labels alone are not admission."""
import argparse,hashlib,json
from pathlib import Path
from audit_teacher_fixture_trajectories import audit
from sft_common import ROOT

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(a):
 out=ROOT/a.output;out.mkdir(parents=True,exist_ok=True)
 if (out/'manifest.json').exists():raise RuntimeError('Already frozen; choose a new output')
 source=ROOT/'data/eight-hour-improvement-v5-authored';run=ROOT/'runs/eight-hour-improvement-v1';accepted=[];decisions=[];hashes={}
 prior=[json.loads(x) for x in (ROOT/'data/eight-hour-improvement-v6/records.jsonl').read_text().splitlines() if x.strip()];prior={r['id']:r for r in prior if r['training_group']=='fresh_authored'}
 for p in sorted(source.glob('batch-*.jsonl')):
  number=int(p.stem.split('-')[1]);rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
  if number<=2:
   for r in rows:
    if r['id'] not in prior or r['messages']!=prior[r['id']]['messages']:raise RuntimeError('Previously admitted source changed')
    accepted.append(r);decisions.append({'id':r['id'],'decision':'keep_prior_parent_review','batch':number})
  else:
   ledger=run/f'parent-batch{number:03d}-review.json'
   if not ledger.exists():continue
   review=json.loads(ledger.read_text())
   if review['after_sha256']!=sha(p):raise RuntimeError('Source changed after review '+p.name)
   by_id={r['id']:r for r in review['decisions']}
   if len(by_id)!=len(rows) or set(by_id)!={r['id'] for r in rows}:raise RuntimeError('Review coverage mismatch')
   for r in rows:
    decision=by_id[r['id']];decisions.append({**decision,'batch':number})
    if decision['decision']!='exclude':accepted.append(r)
   hashes[str(ledger.relative_to(ROOT))]=sha(ledger)
  hashes[str(p.relative_to(ROOT))]=sha(p)
 if len({r['id'] for r in accepted})!=len(accepted):raise RuntimeError('Duplicate admitted ID')
 target=out/'records.jsonl';target.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in accepted))
 replay=audit([target]);(out/'fixture-context-audit.json').write_text(json.dumps(replay,indent=2)+'\n')
 if replay['errors']:raise RuntimeError(replay['errors'])
 (out/'decisions.json').write_text(json.dumps(decisions,indent=2)+'\n')
 manifest={'reviewed':len(decisions),'admitted':len(accepted),'excluded':sum(r['decision']=='exclude' for r in decisions),'source_hashes':hashes,'files':{name:sha(out/name) for name in ['records.jsonl','decisions.json','fixture-context-audit.json']},'reviewer':'parent assistant, not independent human review','limitation':'Task families may repeat despite distinct text. No claim of200unique skills. Excluded near-duplicates retained in source and decisions.'}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);main(p.parse_args())
