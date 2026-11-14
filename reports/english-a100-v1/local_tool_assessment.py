"""Protected development tool probes for the already selected diagnostic model."""
import json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];P=Path(__file__).parent
s=json.loads((P/'selected-diagnostic.json').read_text())
if not s.get('local_independent_readback'):raise ValueError('Local checkpoint not verified')
conversation=json.loads((P/'diagnostic2-conversation.json').read_text())
if conversation['status'] not in ('development_checks_complete','incomplete_timeout','incomplete_worker_error'):raise ValueError('Conversation worker still active')
tokenizer=json.loads((ROOT/'reports/english-first-v1/diagnostic-manifest.json').read_text())['tokenizer_sha256']
a=[sys.executable,'-m','cloud_training.nano_quality','--repo',str(ROOT/'runs/nanochat-source'),'--checkpoint',s['local_path'],'--checkpoint-manifest-sha256',s['manifest_sha256'],'--tokenizer',str(ROOT/'runs/ownbase-v2-data/tokenizer'),'--tokenizer-sha256',tokenizer,'--suite',str(ROOT/'reports/corrective-corpus-v1/protected-suite.json'),'--output',str(P/'diagnostic2-tools.json'),'--device','mps','--seconds','600','--reply-budget','128']
raise SystemExit(subprocess.run(a,cwd=ROOT).returncode)
