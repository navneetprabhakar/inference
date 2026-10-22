"""Materialize a draft one-epoch schedule from verified local token data."""
import hashlib,json
from pathlib import Path
import numpy as np
from slm.restart.segments import segments
from slm.restart.batching import plan_epoch,cursor_schedule
O=Path(__file__).resolve().parent;R=O.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    dest=O/'batch-schedule-draft-v1'
    if dest.exists():raise FileExistsError(dest)
    data=O/'data-train';manifest=json.loads((data/'manifest.json').read_text())
    receipt=json.loads((O/'loss-data-receipt.json').read_text())
    assert manifest==receipt['streams']['data-train']
    for name,digest in manifest['files'].items():assert sha(data/name)==digest
    rows=[json.loads(x) for x in (data/'index.jsonl').read_text().splitlines()]
    tokens=np.memmap(data/'tokens.u16',mode='r',dtype='<u2')
    expected={r['audit_id']:r['targets'] for r in rows};assert len(expected)==len(rows)==72116
    assert len({r['family_id'] for r in rows})==len(rows)
    def parts():
        offset=0
        for r in rows:
            assert r['split']=='train' and not r['partial'] and r['targets']==r['full_document_targets'] and r['offset']==offset
            ids=tokens[offset:offset+r['targets']].tolist();assert ids[-1]==1
            yield from segments(r['audit_id'],ids[:-1])
            offset+=r['targets']
        assert offset==len(tokens)==manifest['targets']
    updates=plan_epoch(parts(),expected_targets=expected)
    cumulative,boundaries=cursor_schedule(updates)
    dest.mkdir();path=dest/'updates.jsonl'
    with path.open('w') as f:
        for step,u in enumerate(updates,1):
            f.write(json.dumps({'step':step,'targets':u.targets,'microbatches':[[[s.document,s.first,s.last] for s in micro] for micro in u.microbatches]},separators=(',',':'))+'\n')
    schedule=dest/'cursor-targets.json';schedule.write_text(json.dumps({'cumulative_targets':cumulative,'update_cursors':boundaries},separators=(',',':'))+'\n')
    result={'status':'DATA_SCHEDULE_VERIFIED_NOT_TRAINER_INTEGRATED','source_manifest_sha256':sha(data/'manifest.json'),'training_documents':len(rows),'one_pass_targets':cumulative[-1],'updates_per_pass':len(updates),'microbatches_per_pass':len(cumulative)-1,'tail_update_targets':updates[-1].targets,'target_batch':8192,'microbatch_sequences':4,'context':512,'files_sha256':{p.name:sha(p) for p in [path,schedule]},'code_sha256':{str(p.relative_to(R)):sha(p) for p in [R/'src/slm/restart/batching.py',R/'src/slm/restart/segments.py']},'limits':['One-pass deterministic draft; full three-pass/exposure schedule and measured microbatch feasibility remain pending.','No weights allocated, no optimizer or training calls.','Document/family identity comes from the hash-bound data index; schedule spans must be reserved before execution.']}
    assert cumulative[-1]==14469949
    (dest/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
