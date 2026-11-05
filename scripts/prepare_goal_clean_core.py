"""Quarantine a source group after an explicit parent semantic spot audit."""
import hashlib,json
from pathlib import Path
from sft_common import ROOT
from audit_teacher_fixture_trajectories import audit

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
source=ROOT/'data/eight-hour-dialogue-expansion-v1'
out=ROOT/'data/eight-hour-clean-core-v1'
out.mkdir(exist_ok=False)
rows=[json.loads(s) for s in (source/'records.jsonl').read_text().splitlines()]
kept=[];quarantined=[]
for row in rows:
    if row['training_group']=='reviewed_natural' and 'local-author' in row['id']:
        quarantined.append({'id':row['id'],'reason':'Legacy local-teacher source fails fresh semantic spot audit; group quarantined, not a claim every record is wrong.'})
    else: kept.append(row)
(out/'records.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in kept))
(out/'quarantine-decisions.json').write_text(json.dumps(quarantined,indent=2)+'\n')
result=audit([out/'records.jsonl']);assert not result['errors'],result['errors']
(out/'fixture-context-audit.json').write_text(json.dumps(result,indent=2)+'\n')
manifest={'state':'cleaner_core_prepared_not_claimed_error_free','records':len(kept),'quarantined':len(quarantined),'source':str(source.relative_to(ROOT)),'source_manifest_sha256':sha(source/'manifest.json'),'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'limitations':['Retained 200 originally assistant-authored dialogues: 30 random records freshly inspected without substantive failures; not a new full review.','383 fresh teacher records retain their explicit per-case admission reviews.','Generated QA/tool records retain previous fixture and construction checks.','Source exclusions do not reverse prior checkpoint exposure; start from V11 best, not interrupted V13.','No protected prompts used to author these records; subset of previously screened source.']}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'kept':len(kept),'quarantined':len(quarantined),'fixture_errors':len(result['errors'])}))
