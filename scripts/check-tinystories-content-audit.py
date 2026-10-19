"""Reconcile direct decisions against their actual fixed source selection."""
# Creator: Navneet Prabhakar
from collections import Counter
import hashlib
import json
from pathlib import Path
from slm.data.schema import digest
from slm.data.tokenized import sha

plan=json.loads(Path('configs/tinystories-direct-audit-v1.json').read_text())
root=Path('data/tinystories-range-intake-v1')
assert sha(root/'report.json')==plan['intake_report_sha256']
for i,judgment in enumerate(plan['records']):
    rows=[json.loads(line) for line in (root/'cache'/(digest('records/train-range-'+str(i).zfill(2))+'.bin')).read_bytes().splitlines()]
    selected=min(rows,key=lambda r:hashlib.sha256((plan['selection_seed']+str(r['row']['start'])).encode()).digest())
    assert judgment['range']==i and judgment['file']==selected['file']
    assert judgment['start']==selected['row']['start'] and judgment['raw_text_sha256']==selected['row']['raw_text_sha256']
    assert judgment['human_attestation'] is False and judgment['training_approved'] is False
    assert judgment['judgment'] in ('consider','exclude','defer') and judgment['note']
report=json.loads(Path('reports/tinystories-content-audit.json').read_text())
assert Counter(r['judgment'] for r in plan['records'])=={k:report[k] for k in ('consider','exclude','defer')}
assert sha('data/tinystories-direct-audit-v1/direct-judgments.jsonl')==report['judgments_sha256']
assert [json.loads(s) for s in Path('data/tinystories-direct-audit-v1/direct-judgments.jsonl').read_text().splitlines()]==plan['records']
print('All eight actual source selections and direct decisions reconcile; no admission.')
