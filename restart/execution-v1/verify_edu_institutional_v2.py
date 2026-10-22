"""Verify frozen candidate/sample accounting, without admitting or training data."""
import bisect
import hashlib
import json
import random
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from slm.common.tokenizer import BPE

ROOT = Path(__file__).resolve().parent
D = ROOT / 'm2-intake/institutional-prose-v2'
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
    return json.loads(p.read_text())
def main():
    policy, summary = load(D/'policy.json'), load(D/'summary.json')
    assert digest(D/'policy.json') == summary['policy_sha256']
    assert digest(ROOT/'edu_institutional_filter_v2.py') == policy['filter_sha256']
    assert digest(ROOT/'prepare_edu_institutional_v2.py') == policy['builder_sha256']
    assert digest(ROOT/'tokenizer-8192/manifest.json') == policy['tokenizer_manifest_sha256']
    db = sqlite3.connect((D/'candidates.sqlite').as_uri()+'?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    rows = {r['row_index']:dict(r) for r in db.execute('SELECT * FROM candidates ORDER BY row_index')}
    db.close()
    assert len(rows) == summary['counts']['candidate_documents']
    assert sum(r['tokens'] for r in rows.values()) == summary['candidate_content_tokens']
    assert len({r['normalized_sha'] for r in rows.values()}) == len(rows)
    excluded = set(policy['excluded_discovery_hosts'])
    for r in rows.values():
        host = (urlsplit(r['url']).hostname or '').lower().removeprefix('www.')
        assert host == r['host'] and host not in excluded
        assert (urlsplit(r['url']).hostname or '').lower().endswith(('.edu','.ac.uk','.gov','.gov.uk'))
    uniform = sorted(rows, key=lambda i:hashlib.sha256((policy['uniform_seed']+':'+str(i)).encode()).digest())[:200]
    cumulative=[]; total=0
    for r in rows.values():
        total += r['tokens']; cumulative.append(total)
    rng=random.Random(policy['weighted_seed']); ids=list(rows)
    weighted=[ids[bisect.bisect_right(cumulative,rng.randrange(total))] for _ in range(200)]
    sampled={}
    for name,expected in [('uniform',uniform),('token-weighted',weighted)]:
        f=D/(name+'-sample.jsonl')
        assert digest(f)==summary['samples_sha256'][name]
        draws=[json.loads(l) for l in f.read_text().splitlines()]
        assert len(draws)==200 and [r['row_index'] for r in draws]==expected
        for position,r in enumerate(draws):
            assert r['draw']==position
            original=rows[r['row_index']]
            for key in ('text','url','host','source_id','tokens','original_sha','normalized_sha','edits'):
                assert r[key]==original[key]
            expected_probability=200/len(rows) if name=='uniform' else r['tokens']/total
            assert r['selection_probability']==expected_probability
            sampled[r['row_index']]=r
    tok=BPE.load(ROOT/'tokenizer-8192')
    for r,encoded in zip(sampled.values(),tok._core.encode_batch([r['text'] for r in sampled.values()])):
        assert len(encoded.ids)==r['tokens']
    result={'status':'CANDIDATE_SAMPLE_ACCOUNTING_PASS_NOT_ADMISSION','candidate_documents':len(rows),'candidate_content_tokens':total,'distinct_sample_documents':len(sampled),'sample_token_counts_recomputed':True,'fresh_host_exclusion_verified':True,'uniform_and_weighted_draws_reproduced':True,'candidate_database_sha256':digest(D/'candidates.sqlite'),'verifier_sha256':digest(Path(__file__)),'remaining':['full semantic reviews','factual risk','language windows','family/near/protected overlap','rights and provenance','split assignment'],'new_admitted_documents':0,'new_admitted_tokens':0}
    with (D/'verification.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
