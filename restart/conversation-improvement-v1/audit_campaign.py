"""Read-only end-of-campaign accounting and immutable-input checks."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ledger=read(ROOT/'ledger.json');assert 'active_segment' not in ledger
counts={k:sum(e.get(k,0) for e in ledger['reservations']) for k in ['updates','positions','sft_targets','narrative_targets']}
assert all(ledger[k]==v for k,v in counts.items())
assert abs(sum(x['seconds'] for x in ledger['segments'])-ledger['model_seconds'])<1e-6
fail=[];checked=0
for manifest in ROOT.glob('*freeze.json'):
 d=read(manifest);d=d.get('files',d)
 for raw,h in d.items():
  if not isinstance(h,str) or len(h)!=64:continue
  p=Path(raw)
  if not p.is_absolute():p=(PROJECT/p) if raw.startswith('restart/') else ROOT/p
  checked+=1
  if not p.exists() or sha(p)!=h:fail.append(dict(manifest=manifest.name,path=str(p)))
journals=[]
for prefix in ROOT.glob('ledger-prefix-*.json'):
 phase=prefix.stem.removeprefix('ledger-prefix-');jp=ROOT/('reservations-'+phase+'.jsonl');d=read(prefix);events=d['reservations']
 for line in jp.read_text().splitlines():
  event=json.loads(line);assert event['index']==len(events);events.append(event['event'])
 assert events==ledger['reservations'][:len(events)];journals.append(dict(phase=phase,reservations=len(events)))
assert not fail,fail
out=dict(status='PASS',immutable_files_checked=checked,immutable_failures=fail,counts=counts,prior_updates=614,total_tracked_updates=614+counts['updates'],model_seconds=ledger['model_seconds'],peak_rss=ledger['peak_rss'],journal_prefixes_verified=journals,artifact_bytes=sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file()),final_test_used=any(e['phase']=='final' for e in ledger['reservations']),active_segment=False)
(ROOT/'audit.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
