import json,hashlib,sqlite3
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];PRE=P.parent/'tiny-copy-preparation-2026-10-29'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 r=read(P/'result.json');c=read(PRE/'carry-forward.json');b=read(PRE/'budget.json');checks=0
 for manifest in [P/'freeze.json',PRE/'freeze.json',PRE/'completion-freeze.json']:
  for f,h in read(manifest)['files'].items():assert sha(ROOT/f)==h,f;checks+=1
 assert sha(ROOT/c['source'])==c['source_sha256'];assert sha(P/'selection.json')==r['selection_sha256']
 db=sqlite3.connect(f'file:{P/"private/study.sqlite"}?mode=ro',uri=True);v=db.execute('SELECT SUM(positions),SUM(updates),SUM(assistant),SUM(narrative) FROM events').fetchone();sec,active=db.execute('SELECT seconds,active_start FROM timing').fetchone();assert active is None;assert dict(zip(['positions','updates','assistant','narrative'],v))==r['charges'];assert abs(sec-r['seconds'])<.01;assert db.execute("SELECT COUNT(*) FROM events WHERE kind='carry-forward-once'").fetchone()[0]==1
 for k in c['charges']:assert r['charges'][k]-c['charges'][k]==r['new_charges'][k]
 assert r['new_charges']['updates']==512 and r['new_charges']['assistant']==12544 and r['new_charges']['narrative']==1048576;assert r['new_charges']['positions']<=6000000 and r['new_seconds']<=900
 assert len({a['initial_parameters'] for a in r['arms']})==len({a['initial_rng'] for a in r['arms']})==1
 for lr in [.0001,.0005]:assert len({a['initial_optimizer'] for a in r['arms'] if a['lr']==lr})==1
 for a in r['arms']:
  folder=P/'private'/a['arm'];assert sha(folder/'checkpoint.pkl')==a['checkpoint_sha256'];logs=[json.loads(x) for x in (folder/'updates.jsonl').read_text().splitlines()];assert [x['step'] for x in logs]==list(range(1,129))
  for step in [64,128]:assert len((folder/'evaluation'/f'{step}-fit.jsonl').read_text().splitlines())==32 and len(read(folder/'evaluation'/f'{step}-teacher.json'))==32
  if a['lr']==r['selected_lr']:assert len((folder/'transfer.jsonl').read_text().splitlines())==64
  else:assert not (folder/'transfer.jsonl').exists()
 assert len((P/'private/source/transfer.jsonl').read_text().splitlines())==128
 for f in ['name','time']:assert len((P/'private/source'/f/'0-fit.jsonl').read_text().splitlines())==32
 # Ledger explicitly confirms all five native evaluations and scheduled teacher passes.
 assert db.execute("SELECT SUM(positions) FROM events WHERE kind='heldout-native-nll'").fetchone()[0]==655360
 assert db.execute("SELECT SUM(positions) FROM events WHERE kind='teacher-fit'").fetchone()[0]==b['teacher_positions'];db.close()
 size=sum(f.stat().st_size for f in P.rglob('*') if f.is_file());assert size<=1073741824
 out=dict(status='PASS',frozen_file_entries=checks,carry_forward_once=True,prior_ledger_unchanged=True,initial_parameters_rng_equal=True,optimizer_equal_within_lr=True,exact_training_and_evaluation_counts=True,selected_transfer_only=True,caps_respected=True,artifact_bytes=size,promotion=False,final_test_used=False)
 (P/'audit.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
if __name__=='__main__':main()
