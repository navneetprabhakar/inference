import json,hashlib,sqlite3
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];PRE=P.parent/'paired-fit-preparation-2026-10-29'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 result=read(P/'result.json');budget=read(PRE/'budget.json');carry=read(PRE/'carry-forward.json');checked=0
 for manifest in [P/'freeze.json',PRE/'freeze.json',PRE/'completion-freeze.json']:
  for f,h in read(manifest)['files'].items():assert sha(ROOT/f)==h,f;checked+=1
 for f,h in carry['sources'].items():assert sha(ROOT/f)==h
 db=sqlite3.connect(f'file:{P/"private/study.sqlite"}?mode=ro',uri=True);vals=db.execute('SELECT SUM(positions),SUM(updates),SUM(assistant),SUM(narrative) FROM events').fetchone();seconds,active=db.execute('SELECT seconds,active_start FROM timing').fetchone();assert active is None
 totals=dict(zip(['positions','updates','assistant','narrative'],vals));assert totals==result['charges'];assert abs(seconds-result['seconds'])<.01
 assert db.execute("SELECT COUNT(*) FROM events WHERE kind='carry-forward-once'").fetchone()[0]==1
 for k in totals:assert totals[k]-carry['charges'][k]==result['new_charges'][k]
 assert result['new_charges']['updates']==512 and result['new_charges']['assistant']==24808 and result['new_charges']['narrative']==1048576
 assert result['new_charges']['positions']<=20000000 and result['new_seconds']<=3600
 assert result['arms'][0]['initial_state_digest']==result['arms'][1]['initial_state_digest']
 for arm in result['arms']:
  folder=P/'private'/arm['arm'];assert sha(folder/'checkpoint.pkl')==arm['checkpoint_sha256'];logs=[json.loads(x) for x in (folder/'updates.jsonl').read_text().splitlines()];assert [r['step'] for r in logs]==list(range(1,257))
  ev=folder/'evaluation';assert len((ev/'fit.jsonl').read_text().splitlines())==1408;assert len((ev/'development.jsonl').read_text().splitlines())==176
 db.close();size=sum(f.stat().st_size for f in P.rglob('*') if f.is_file());assert size<=2*1024**3
 out=dict(status='PASS',frozen_file_checks=checked,old_ledgers_unchanged=True,carry_forward_imports=1,identical_initial_parameters_optimizer_rng=True,new_updates=512,caps_respected=True,artifact_bytes=size,final_test_used=False,promotion=False)
 (P/'audit.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
if __name__=='__main__':main()
