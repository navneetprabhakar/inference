"""Prepare a deterministic English curriculum and an exposed development split."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent
OUT = ROOT / 'runs/ganesh-english-readiness-v1'
SOURCE = ROOT / 'runs/ganesh-english-sourcing-v1/scale-1000/reviewed-1000-v1.jsonl'
EXPECTED = '4c19b20fc0de517b5846c203c2d73864923e377085927267283acd52c06c0a8a'
# Entire topic clusters and the earlier parent-authoring source are withheld from training.
DOMAINS = {
    'performance': r'\b(theat\w*|rehears\w*|stage|concert|perform\w*|choir)\b',
    'food': r'\b(meal\w*|food|cook\w*|allerg\w*|lunch|dinner|recipe\w*)\b',
    'library': r'\b(librar\w*|borrow\w*|lend\w*)\b',
    'travel': r'\b(train station|train ticket|flight\w*|hotel\w*|itinerar\w*|airport\w*)\b',
    'exhibition': r'\b(galler\w*|exhibit\w*|museum\w*|portrait\w*)\b',
}
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if digest(SOURCE) != EXPECTED:
        raise ValueError('Reviewed parent changed')
    OUT.mkdir(parents=True, exist_ok=True)
    pools = {'train': [], 'development': []}
    ledger = []
    mass = Counter()
    rows = sorted(map(json.loads, SOURCE.read_text().splitlines()), key=lambda row: row['id'])
    audits = ROOT/'reports/ganesh-english-sourcing-v1/scale-1000/worker-c'
    audit = json.loads((audits/'cross-plan-triage.json').read_text())
    replacements = json.loads((audits/'replacement-crossplan-receipt-v1.json').read_text())
    review = json.loads((ROOT/replacements['review_path']).read_text())
    clusters = audit['shared_template_clusters'] + audit['triage'] + review.get('clusters', [])
    # Conservatively reserve every row identified in an existing cross-template review.
    linked = {group for cluster in clusters for group in cluster['groups']}
    for row in rows:
        text = ' '.join(message['content'] for message in row['messages']).lower()
        domains = [name for name, pattern in DOMAINS.items() if re.search(pattern, text)]
        earlier = row.get('source') == 'original Codex authoring' and not row.get('generation')
        targets = row['encoding'][0]['assistant_targets']
        split = 'reserve'
        reason = 'Withheld source or topic'
        plan = row.get('plan_receipt',{}).get('path','')
        held_batch = '/root/' in plan and Path(plan).name in {'b03.plan.json','b08.plan.json','b12.plan.json'}
        if row['group'] in linked:
            reason = 'Prior cross-template review'
        elif held_batch or (earlier and domains):
            split = 'development'
            reason = 'Withheld scenario-plan batch' if held_batch else 'Withheld authoring source and topic'
        elif not held_batch and row.get('generation', {}).get('interface') == 'codex exec' and not domains:
            reason = 'Family target budget'
            if row['family'] not in ('memory','correction') or mass[row['family']] + targets <= 9000:
                split = 'train'
                reason = 'Reviewed English breadth'
                mass[row['family']] += targets
        ledger.append(dict(group=row['group'], id=row['id'], domains=domains, split=split, reason=reason))
        if split == 'reserve':
            continue
        # Keep the reviewed transcript verbatim; assign one authoritative policy per turn.
        turns = len(row['messages']) // 2
        enabled = int(row['id'][:8], 16) % 2 == 1
        pools[split].append(dict(group=row['group'], family=row['family'], messages=row['messages'],
            policies=[dict(permit_calls=enabled, allowed_names=['calculate','convert'] if enabled else []) for _ in range(turns)],
            source_id=row['id'], target_positions=targets))
    receipt = {'parent_sha256':EXPECTED, 'training_admitted':False, 'release_eligible':False}
    for split, data in pools.items():
        if not data:
            raise ValueError('Empty split')
        path = OUT / (split + '.jsonl')
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in data))
        receipt[split] = dict(path=str(path.relative_to(ROOT)), sha256=digest(path), sessions=len(data),
            turns=sum(len(r['messages'])//2 for r in data), targets=sum(r['target_positions'] for r in data),
            families=dict(Counter(r['family'] for r in data)), policy_sessions=dict(Counter(str(r['policies'][0]['permit_calls']) for r in data)))
    (REPORT/'split-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
    receipt['reserve_sessions'] = sum(r['split']=='reserve' for r in ledger)
    receipt['ledger_sha256'] = digest(REPORT/'split-ledger.json')
    (REPORT/'curriculum.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__ == '__main__':
    main()
