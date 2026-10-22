"""Read-only stored-token diagnostic; no body reads, inference, or admission."""
import datetime, hashlib, json, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def load(p):
    return json.loads(p.read_text())

def run():
    assert not (OUT / 'counts.json').exists()
    prior = ROOT / 'm2-intake/hansard-current-semantic-rights-hold-diagnostics-v1/counts.json'
    uniform = ROOT / 'hansard-uniform20-team-review-progress-v2/review.json'
    byte = ROOT / 'hansard-byte10-parent-whole-review-progress-v1/review.json'
    proof = ROOT / 'hansard-language-token-terminal-parent-verification-v1/verification.json'
    sql = ROOT / 'm2-intake/hansard-two-complete-raw-language-M1-diagnostics-v1/screening.sqlite'
    assert sha(uniform) == '65dbcb27d726190f754129dd057546b67148f9a7e31d6ea9e67400e59df40a42'
    assert sha(byte) == 'c848bfc7c9c382a7913c1b1d25f828920134a4f333e50ae7e2987b6371841067'
    assert sha(proof) == '33118a41188cdcc7acba2ec013a6f9618842d72351a6adad1d121f2cbc326066'
    previous = load(prior)
    assert sha(sql) == previous['source_token_SQLite_SHA256']
    before = sql.stat()
    u, b = load(uniform), load(byte)
    holds = {x['text_SHA256'] for x in previous['exact_semantic_holds']}
    holds.update(x['text_SHA256'] for x in u['new_exact_semantic_hold_targets'])
    holds.update(x['text_SHA256'] for x in b['reviews'] if x['all_exact_text_copies_current_review_hold'])
    assert len(holds) == 7
    db = sqlite3.connect(sql.as_uri() + '?mode=ro&immutable=1', uri=True)
    rows = db.execute('SELECT hex(text_SHA256),UTF8_bytes,content_tokens,language_pass,occurrences,explicit_hold_flags,rights_unclear_flags FROM texts').fetchall()
    assert len(rows) == 15800
    def total(selected):
        return dict(distinct_text_SHA=len(selected), M1_content_tokens=sum(r[2] for r in selected),
                    UTF8_bytes=sum(r[1] for r in selected), raw_occurrences=sum(r[4] for r in selected),
                    EOS_separate=len(selected), usable_or_admitted=False)
    all_counts = total(rows)
    assert all_counts == previous['summaries']['all_distinct_not_usable']
    old = {x['text_SHA256'] for x in previous['exact_semantic_holds']}
    assert total([r for r in rows if r[3] and r[0].lower() not in old]) == previous['summaries']['language_pass_after_all4_known_semantic_holds_not_usable']
    for r in rows:
        if r[5]: assert r[0].lower() in holds
    selected = [r for r in rows if r[3] and r[0].lower() not in holds]
    held = [dict(text_SHA256=r[0].lower(), UTF8_bytes_onecopy=r[1], M1_content_tokens_onecopy=r[2], language_pass=bool(r[3]), raw_occurrences=r[4], hold_all_exactcopies=True) for r in rows if r[0].lower() in holds]
    assert len(held) == 7
    db.close()
    assert sql.stat() == before
    inputs = [prior, uniform, byte, proof, sql, Path(__file__).resolve()]
    report = dict(status='VERIFIED_READONLY_STORED_TOKEN_RECOUNT_AFTER7_EXACT_SEMANTIC_HOLDS_NO_ADMISSION',
                  UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  token_units='Frozen M1 8192 BPE content tokens; EOS separate. No tokenizer fit or retokenization.',
                  inputs_SHA256={str(p): sha(p) for p in inputs},
                  summaries={'all_distinct_not_usable': all_counts,
                             'language_pass_after_all7_known_semantic_holds_not_usable': total(selected),
                             'language_pass_after_all7_holds_and_localized_NI_London_flags_STILL_UNCLEARED': total([r for r in selected if r[6] == 0])},
                  exact_semantic_holds=held,
                  review_scope='16/20 uniform and 1/10 UTF8-byte-weighted development captures; ongoing review, not fresh cohort acceptance.',
                  rights_status='ALL UNCLEARED, including flags zero. Localized flag exclusions are diagnostics only.',
                  unresolved=['Remaining semantic review and extraction repair', 'Rights and component grant/attribution', 'Family/near duplicate/protected overlap', 'Fresh probability cohort review', 'Source/genre/split freeze and M3 recount'],
                  source_body_reads=0, new_admitted_documents=0, new_admitted_tokens=0)
    assert sql.stat() == before
    with (OUT / 'counts.json').open('x') as f:
        json.dump(report, f, indent=2); f.write('\n')
    print(json.dumps(report['summaries']))

if __name__ == '__main__':
    run()
