"""Single conservative repair; CPU only, fail closed on insufficient supply."""
import collections, hashlib, json, re, sqlite3
from pathlib import Path
P = Path(__file__).resolve().parent
ROOT = P.parents[2]
def write(name, value):
    (P / name).write_text(json.dumps(value, indent=2) + '\n')
def main():
    assert not (P / 'repair-result.json').exists(), 'single repair already spent'
    policy = {
        'batch': 1,
        'hold_text_regex': 'learning objectives|critical thinking questions|general discussion instructions|discussion grading rubric|read this article|personal application questions',
        'everyday_to_educational_title_regex': 'psycholog|sociolog|soil science|western civilization|neuroscience|sensation|anatomy|physiology|grammar|student writers',
        'rationale': 'Conservative quarantine of assignment/link-dependent units and academic book strata; reassignment is not semantic certification.',
        'no_second_repair': True,
    }
    write('repair-policy.json', policy)
    src = json.loads((P / 'policy.json').read_text())['source']
    db = sqlite3.connect(f'file:{ROOT/src}?mode=ro', uri=True)
    rows = json.loads((P / 'private/candidate-manifest.json').read_text())
    accepted, held = [], []
    for row in rows:
        text = db.execute('SELECT text FROM docs WHERE h=?', (row['h'],)).fetchone()[0]
        assert hashlib.sha256(text.encode()).hexdigest() == row['h']
        if re.search(policy['hold_text_regex'], text, re.I):
            held.append({**row, 'reason': 'conservative extraction/dependency hold'})
            continue
        if row['domain'] == 'everyday' and re.search(policy['everyday_to_educational_title_regex'], row['title'], re.I):
            row = {**row, 'original_domain': row['domain'], 'domain': 'educational'}
        accepted.append(row)
    db.close()
    counts = {s: {d: sum(r['tokens'] for r in accepted if r['split']==s and r['domain']==d) for d in ['everyday','procedural','educational']} for s in ['train','development','reserve']}
    supply = sum(counts['train'].values()) >= 4000000 and min(counts['train'].values()) >= 1000000
    write('private/repaired-candidate-manifest.json', accepted)
    write('private/repair-holds.json', held)
    write('repair-result.json', dict(status='SUPPLY_PASS_SEMANTIC_RECHECK_REQUIRED' if supply else 'STOP_DATA_ADMISSION', repair_batch_used=True, token_counts=counts, held_documents=len(held), held_training_tokens=sum(r['tokens'] for r in held if r['split']=='train'), supply_pass=supply, admitted_tokens=0, semantic_recheck_completed=False, reason='Fixed supply floor fails; no fresh semantic recheck can repair insufficient quantity.' if not supply else 'Awaiting the one permitted fresh semantic recheck.'))
    print((P / 'repair-result.json').read_text())
if __name__ == '__main__':
    main()
