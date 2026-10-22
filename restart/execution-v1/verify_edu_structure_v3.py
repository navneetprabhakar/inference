"""Independently check refinement lineage, sample selection and token counts."""
import bisect, hashlib, json, random, sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from slm.common.tokenizer import BPE
ROOT=Path(__file__).resolve().parent
D=ROOT/'m2-intake/institutional-structure-v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def lines(p):return [json.loads(l) for l in p.read_text().splitlines()]
def main():
    summary=read(D/'summary.json');policy=read(D/'policy.json')
    for name,h in summary['hashes'].items():assert sha(D/name)==h
    assert sha(ROOT/'edu_structure_filter_v3.py')==policy['filter_sha256']
    assert sha(ROOT/'prepare_edu_structure_v3.py')==policy['builder_sha256']
    assert sha(ROOT/'tokenizer-8192/manifest.json')==policy['tokenizer_manifest_sha256']
    source=ROOT/'m2-intake/institutional-prose-v2/candidates.sqlite';assert sha(source)==policy['source_database_sha256']
    db=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    original={r['row_index']:dict(r) for r in db.execute('SELECT * FROM candidates')};db.close()
    rows=lines(D/'candidates.jsonl');exclusions=lines(D/'exclusions.jsonl')
    ids={r['row_index'] for r in rows};excluded_ids={r['row_index'] for r in exclusions}
    assert len(ids)==len(rows) and len(excluded_ids)==len(exclusions)
    assert ids.isdisjoint(excluded_ids) and ids|excluded_ids==set(original)
    assert len(rows)==summary['candidate_documents']
    assert sum(r['tokens'] for r in rows)==summary['candidate_provisional_content_tokens']
    assert sum(r['tokens'] for r in exclusions)==summary['excluded_provisional_content_tokens']
    forbidden=set(policy['excluded_development_hosts']+policy['inherited_excluded_development_hosts'])
    for r in rows:
        assert r==original[r['row_index']]
        assert (urlsplit(r['url']).hostname or '').lower().removeprefix('www.') not in forbidden
    for r in exclusions:assert r['tokens']==original[r['row_index']]['tokens'] and r['reasons']
    selected={}
    uniform=sorted(rows,key=lambda r:hashlib.sha256((policy['uniform_seed']+':'+str(r['row_index'])).encode()).digest())[:200]
    cumulative=[];total=0
    for r in rows:total+=r['tokens'];cumulative.append(total)
    rng=random.Random(policy['weighted_seed']);weighted=[rows[bisect.bisect_right(cumulative,rng.randrange(total))] for _ in range(200)]
    for name,expected in [('uniform',uniform),('token-weighted',weighted)]:
        draws=lines(D/(name+'-sample.jsonl'));assert len(draws)==200
        for i,(r,parent) in enumerate(zip(draws,expected)):
            assert r['draw']==i and r['sampling']==name
            assert all(r[k]==v for k,v in parent.items())
            assert r['selection_probability']==(200/len(rows) if name=='uniform' else r['tokens']/total)
            selected[r['row_index']]=r
    assert len(selected)==summary['union_unique_documents']
    tokenizer=BPE.load(ROOT/'tokenizer-8192')
    for r,encoding in zip(selected.values(),tokenizer._core.encode_batch([r['text'] for r in selected.values()])):assert r['tokens']==len(encoding.ids)
    receipt={'status':'LINEAGE_AND_SAMPLE_ACCOUNTING_PASS_NOT_ADMISSION','candidate_documents':len(rows),'candidate_provisional_content_tokens':total,'sample_unique_documents':len(selected),'checks':['Whole parent partition accounted for without duplicate/missing identities','Every candidate field and text exactly equals immutable parent','All known development hosts excluded','Both probability sample sequences independently reproduced','All unique sampled content token counts recomputed'],'verifier_sha256':sha(Path(__file__)),'new_admitted_documents':0,'new_admitted_tokens':0,'semantic_review':'pending'}
    with (D/'verification.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
