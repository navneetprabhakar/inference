import sys,json,sqlite3
from pathlib import Path
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P));from run import verify,CAPS
from runner import Meter,read,sha,atomic

def main():
 verify();result=read(P/'result.json');carry=read(P/'carry-forward.json');meter=Meter(P/'private/study.sqlite',CAPS,True);tot=meter.totals();cursor=meter.cursor()
 assert tot==result['charges'] and tot['updates']==4612
 assert sha(P.parents[1]/carry['source'])==carry['source_sha256']
 assert meter.db.execute("SELECT COUNT(*) FROM events WHERE kind='import-all-calibration-12-plus600-and-timing'").fetchone()[0]==1
 assert meter.db.execute("SELECT COUNT(*) FROM events WHERE kind='training-step'").fetchone()[0]==4000
 for a in result['arms']:
  folder=P/'private'/f"arm-{a['arm']}";updates=[json.loads(s) for s in (folder/'updates.jsonl').read_text().splitlines()];assert [r['step'] for r in updates]==list(range(1,1001));assert sha(folder/'checkpoint.pkl')==a['checkpoint_sha256']
  for step,expected in [(250,176),(500,176),(1000,1408)]:
   summary=read(folder/'evaluation'/f'{step}-summary.json');assert summary['matrix']['total']==expected;assert summary['preservation']['total']==80;assert summary['native_narrative']['targets']==131072
  assert read(folder/'evaluation/1000-summary.json')['counterfactual']['total']==352
 assert len({a['source_parameters'] for a in result['arms']})==1
 assert tot['assistant']==221052 and tot['narrative']==4722688
 assert tot['positions']<=50000000 and result['seconds']<=9000
 try:meter.reserve('forbidden-extra-update',0,updates=1)
 except RuntimeError as e:assert str(e)=='CAP_updates'
 else:raise AssertionError('EXTRA_UPDATE_ALLOWED')
 assert meter.totals()==tot and meter.cursor()==cursor
 receipt={'status':'PASS','exact_main_updates':4000,'calibration_updates_carried_once':612,'all_four_fresh_source_hashes_identical':True,'all_endpoint_and_sentinel_counts_verified':True,'all_source_inputs_and_calibration_ledger_unchanged':True,'checkpoint_hashes_verified':True,'extra_update_denied_without_work':True,'charges':tot,'seconds':result['seconds'],'final_test_used':False,'automatic_promotion':False}
 atomic(P/'audit.json',json.dumps(receipt,indent=2).encode());print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
