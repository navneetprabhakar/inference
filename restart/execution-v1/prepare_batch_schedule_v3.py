"""Materialize a draft three-pass schedule from verified local token data."""
import hashlib,json
from pathlib import Path
import numpy as np
from slm.restart.segments import segments
from slm.restart.batching import plan_epoch,cursor_schedule
O=Path(__file__).resolve().parent;R=O.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
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
    dest=O/'batch-schedule-draft-v3'
    if dest.exists():raise FileExistsError(dest)
    cap=3*manifest['targets'];all_stops=tuple(range(500000,cap,500000))
    dest.mkdir();path=dest/'updates.jsonl';cumulative=[0];boundaries=[0];step=0;per_pass=[]
    from slm.restart.monitor import cosine_rate
    with path.open('w') as f:
        for epoch in range(3):
            start=epoch*manifest['targets']
            stops=tuple(x-start for x in all_stops if start<x<=start+manifest['targets'])
            updates=plan_epoch(parts(),expected_targets=expected,stop_targets=stops)
            per_pass.append(len(updates))
            for u in updates:
                step+=1
                for micro in u.microbatches:cumulative.append(cumulative[-1]+sum(s.last-s.first for s in micro))
                boundaries.append(len(cumulative)-1);end=cumulative[-1]
                events=[]
                if end%500000==0:events.append('dev_loss_checkpoint')
                if end%2000000==0:events.append('full_development_diagnostics')
                if end%5000000==0:events.append('copying_probes')
                if end==2000000:events.append('pilot_continuation_gate')
                if end==cap:events.append('normal_budget_end')
                f.write(json.dumps({'step':step,'pass':epoch+1,'targets':u.targets,'cumulative_targets':end,'lr':cosine_rate(end,cap),'events_after_update':events,'microbatches':[[[s.document,s.first,s.last] for s in micro] for micro in u.microbatches]},separators=(',',':'))+'\n')
            del updates
    schedule=dest/'cursor-targets.json';schedule.write_text(json.dumps({'cumulative_targets':cumulative,'update_cursors':boundaries},separators=(',',':'))+'\n')
    assert cumulative[-1]==cap==43409847 and step<=6000
    assert set(all_stops)<={cumulative[i] for i in boundaries}
    result={'status':'FULL_SCHEDULE_DRAFT_NOT_TRAINER_INTEGRATED','source_manifest_sha256':sha(data/'manifest.json'),'training_documents':len(rows),'targets':cap,'updates':step,'updates_per_pass':per_pass,'microbatches':len(cumulative)-1,'exact_evaluation_boundaries':list(all_stops),'pilot_boundary':2000000,'target_batch':8192,'microbatch_sequences':4,'context':512,'passes':3,'order':'Same verified source order per pass; no random shuffle.','files_sha256':{p.name:sha(p) for p in [path,schedule]},'code_sha256':{str(p.relative_to(R)):sha(p) for p in [R/'src/slm/restart/batching.py',R/'src/slm/restart/segments.py',R/'src/slm/restart/monitor.py']},'limits':['Microbatch feasibility and trainer integration remain pending.','Schedule counts planned successful work only; charged crash/replay exposures can shorten it. Never reset ledger to complete three nominal passes.','Pilot continuation is conditional, not authorized by this schedule.','No model or optimizer calls.']}
    (dest/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='exact_evaluation_boundaries'},indent=2))
if __name__=='__main__':main()
