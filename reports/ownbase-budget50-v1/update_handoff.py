"""Reconcile the live handoff from reviewed, backed-up corpus receipts."""
import argparse, datetime, hashlib, json, re
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--corpus', type=Path, required=True)
a = p.parse_args()
report = Path('reports/ownbase-budget50-v1')
runtime = Path('runs/ownbase-budget50-v1')
read = lambda path: json.loads(path.read_text())
sha = hashlib.sha256((a.corpus/'manifest.json').read_bytes()).hexdigest()
manifest = read(a.corpus/'manifest.json')
verification = read(a.corpus/'verification.json')
summary = read(report/'corpus-expansion/summary.json')
version = a.corpus.name.removeprefix('long-context-corpus-')
backup = read(report/'corpus-expansion'/f'corpus-{version}-backup.json')
assert sha == summary['manifest_sha256'] == verification['manifest_sha256'] == backup['manifest_sha256']
assert backup['all_files_independent_sha_readback']
snapshot = read(runtime/'latest-snapshot.json')
now = datetime.datetime.now(datetime.timezone.utc)
coverage = verification['full_corpus_coverage']
train, dev = manifest['train'], manifest['validation']
active = []
for path in sorted((runtime/'corpus-expansion').glob('*/progress.json')):
    progress = read(path)
    if progress.get('status') == 'generating': active.append(path.parent.name)

state_path = report/'state.json'
state = read(state_path)
state.update(utc=now.isoformat(), latest_base_observation=snapshot,
             provider_status=snapshot['provider_status'],
             corpus=f'{a.corpus.name}; all files GCS SHA readback verified; untrained',
             current_long_context_corpus={
                 'path':str(a.corpus), 'manifest_sha256':sha,
                 'sessions':train['sessions']+dev['sessions'],
                 'train_targets':train['assistant_targets'], 'development_targets':dev['assistant_targets'],
                 'train_targets_after3072':coverage['train']['assistant_targets_after_3072'],
                 'development_targets_after3072':coverage['validation']['assistant_targets_after_3072'],
                 'independent_gcs_readback':True, 'trained':False,
                 'full4k_corpus_ready':verification['full_4k_extension_corpus_ready'],
                 'full4k_ready':False},  # Hardware/quality qualification is still outstanding.
             active_corpus_generation=active)
for stale in ('observed', 'observed_progress'): state.pop(stale, None)
state_path.write_text(json.dumps(state, indent=2)+'\n')

handoff = Path('OWN_BASE_HANDOFF.txt'); text = handoff.read_text()
text = re.sub(r'EXECUTIVE SUMMARY — CURRENT AT [^\n]+',
              'EXECUTIVE SUMMARY — CURRENT AT '+now.strftime('%d %B %Y, %H:%M UTC').upper(), text, count=1)
observed_at = datetime.datetime.fromisoformat(snapshot['utc']).strftime('%H:%M')
if snapshot.get('progress') and snapshot['phase'] == 'base_training':
    targets = snapshot['progress']['targets']
    ce = snapshot.get('last_heldout_ce')
    if targets is not None and ce is not None:
        text = re.sub(r'latest\d\d:\d\dUTC observation[\d,]+tokens andCE[\d.]+',
                      f'latest{observed_at}UTC observation{targets:,}tokens andCE{ce:.6f}', text, count=1)
text = re.sub(r'Compute estimate[\d.]+USD at\d\d:\d\dUTC',
              f'Compute estimate{snapshot["conservative_compute_accrual_usd"]:.2f}USD at{observed_at}UTC', text, count=1)
paragraph = (
    f'- Current immutable long-context corpus is {version.upper()}: {train["sessions"]+dev["sessions"]} sessions '
    f'({train["sessions"]} train/{dev["sessions"]} development), {train["assistant_targets"]:,} training and '
    f'{dev["assistant_targets"]:,} development targets. After 3072: '
    f'{coverage["train"]["assistant_targets_after_3072"]:,} train/{coverage["validation"]["assistant_targets_after_3072"]:,} development; '
    f'{coverage["train"]["sessions_at_least_3072"]} train/{coverage["validation"]["sessions_at_least_3072"]} development long sessions. '
    f'{summary["accepted_unique_scenarios"]} new accepted scenarios, {summary["fully_reviewed_versions"]} fully reviewed versions '
    f'across {summary["initial_unique_scenarios"]} initial scenarios. New late targets '
    f'{summary["new_train_targets_after3072"]:,} train + {summary["new_development_targets_after3072"]:,} development. '
    f'Prior rows/splits byte-preserved; every immutable V4–{version.upper()} file independently GCS SHA read back. '
    'All new data untrained; full 4K data/hardware gate unmet.')
text = re.sub(r'^- Current immutable long-context corpus is [^\n]+', lambda _:paragraph, text, count=1, flags=re.M)
text = re.sub(r'^- runs/long-context-corpus-v\d+/: current immutable corpus[^\n]+',
              f'- {a.corpus}/: current immutable corpus, verified and GCS-backed; separate from frozen 2K training inputs.', text, count=1, flags=re.M)
text = text.replace('Current combined admitted corpus:\n  runs/long-context-corpus-v3/',
                    'Historical pre-run combined admitted corpus (current version is in section 1):\n  runs/long-context-corpus-v3/')
handoff.write_text(text)
plan = Path('OWN_BASE_NEXT_STEPS.txt'); text = plan.read_text()
text = re.sub(r'^CURRENT EXECUTION DELTA — [^\n]+',
              'CURRENT EXECUTION DELTA — '+now.strftime('%d %B %Y, %H:%M UTC').upper(), text, count=1)
text = re.sub(r'V\d+ corpus is backed up but untrained', f'{version.upper()} corpus is backed up but untrained', text, count=1)
plan.write_text(text)
audit = Path('TRAINING_AUDIT.txt'); marker = f'Corpus {version.upper()} manifest {sha}'
if marker not in audit.read_text():
    with audit.open('a') as f:
        f.write(f'\n{now.isoformat()} — {marker}. {paragraph[2:]} '
                'Evidence includes full root dialogue review, executable checks where applicable, native packing/masks, '
                'split preservation and independent GCS readback. Training packet unchanged.\n')
print(json.dumps({'corpus':str(a.corpus),'manifest_sha256':sha,'active_generation':active,'handoff_updated':True}))
