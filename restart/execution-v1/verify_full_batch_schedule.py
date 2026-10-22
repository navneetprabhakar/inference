"""Independent saved-span audit and ledger dry run. NO model or optimizer."""
import collections,hashlib,json
from pathlib import Path
from slm.restart.ledger import Ledger,BudgetError
O=Path(__file__).resolve().parent;D=O/'batch-schedule-draft-v3'
def main():
    receipt=json.loads((D/'receipt.json').read_text())
    for rel,digest in receipt['files_sha256'].items():assert hashlib.sha256((D/rel).read_bytes()).hexdigest()==digest
    expected={r['audit_id']:r['targets'] for r in map(json.loads,(O/'data-train/index.jsonl').read_text().splitlines())}
    ledger_path=D/'dry-run-only-ledger.sqlite'
    if ledger_path.exists():raise FileExistsError('Preserve dry-run evidence')
    ledger=Ledger(ledger_path,'SCHEDULE_VALIDATION_ONLY_NO_OPTIMIZER',target_cap=43409847,update_cap=6000,presentation_cap=3,deadline=1e9)
    seen={i:collections.Counter() for i in (1,2,3)};total=0;step=0;cursor=[0];bounds=[0];ends=[];pilot=None
    for u in map(json.loads,(D/'updates.jsonl').read_text().splitlines()):
        step+=1;assert u['step']==step and u['pass'] in seen
        spans=[];count=0
        for micro in u['microbatches']:
            assert 1<=len(micro)<=4
            n=0
            for doc,first,last in micro:
                assert doc in expected and first==seen[u['pass']][doc] and 0<last-first<=512 and last<=expected[doc]
                seen[u['pass']][doc]=last;spans.append((doc,first,last));n+=last-first
            cursor.append(cursor[-1]+n);count+=n
        assert 0<count<=8192 and count==u['targets']
        previous=total;total+=count;ends.append(total);bounds.append(len(cursor)-1)
        assert total==u['cumulative_targets']
        assert not any(previous<b<total for b in receipt['exact_evaluation_boundaries'])
        events=[]
        if total%500000==0:events.append('dev_loss_checkpoint')
        if total%2000000==0:events.append('full_development_diagnostics')
        if total%5000000==0:events.append('copying_probes')
        if total==2000000:events.append('pilot_continuation_gate');pilot=step
        if total==43409847:events.append('normal_budget_end')
        assert events==u['events_after_update']
        # No optimizer work: completion below means only the validation reservation was processed.
        ledger.reserve(str(step),spans,now=0);ledger.complete(str(step))
    assert total==43409847 and all(dict(v)==expected for v in seen.values())
    assert set(receipt['exact_evaluation_boundaries'])<=set(ends)
    assert json.loads((D/'cursor-targets.json').read_text())=={'cumulative_targets':cursor,'update_cursors':bounds}
    totals=ledger.totals();assert totals['targets_reserved']==total and totals['updates_reserved']==step
    doc=next(iter(expected))
    try:ledger.reserve('beyond-plan',[(doc,0,1)],now=0)
    except BudgetError:pass
    else:raise AssertionError('Over-budget reservation accepted')
    assert ledger.totals()==totals
    snapshot=ledger.snapshot();ledger.close()
    result={'status':'FULL_SAVED_SCHEDULE_AND_LEDGER_DRY_RUN_PASS','documents':len(expected),'targets':total,'updates':step,'pilot_updates':pilot,'checkpoint_boundaries':len(receipt['exact_evaluation_boundaries']),'each_target_presentations':3,'cursor_verified':True,'post_budget_reservation_rejected':True,'ledger_snapshot':snapshot,'scope':'Isolated schedule validation ledger only; completed reservations represent no optimizer work. This is not the execution ledger and may not be loaded by a trainer.','model_initialized':False,'training_started':False}
    (D/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
