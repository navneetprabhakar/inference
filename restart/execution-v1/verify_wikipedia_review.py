"""Independently verify transformations, counts and frozen probability samples."""
import bisect,hashlib,json,random,sqlite3
import pyarrow.parquet as pq
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.restart.wikipedia_filter import normalized
O=Path(__file__).resolve().parent;D=O/'m2-intake/wikipedia-prose-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    summary=json.loads((D/'summary.json').read_text());policy=json.loads((D/'policy.json').read_text())
    assert sha(D/'policy.json')==summary['policy_sha256']
    assert sha(O.parents[1]/'src/slm/restart/wikipedia_filter.py')==policy['filter_sha256']
    assert sha(O.parents[1]/'src/slm/restart/edu_filter.py')==policy['shared_normalizer_sha256']
    assert sha(O/'tokenizer-8192/manifest.json')==policy['tokenizer_manifest_sha256']
    tok=BPE.load(O/'tokenizer-8192');db=sqlite3.connect(f'file:{D}/candidates.sqlite?mode=ro',uri=True)
    eligible=[];seen=set();total=0;transformed=0
    for idx,sid,text,original,norm,n,rawedits in db.execute('SELECT row_index,source_id,text,original_sha,normalized_sha,tokens,edits FROM candidates ORDER BY row_index'):
        edits=json.loads(rawedits);suffix=edits['retained_removed_suffix']
        assert hashlib.sha256((text+suffix).encode()).hexdigest()==original
        assert hashlib.sha256(normalized(text).encode()).hexdigest()==norm
        assert norm not in seen;seen.add(norm)
        assert sid not in policy['excluded_discovery_page_ids']
        assert len(tok._core.encode(text).ids)==n
        for edit in edits['transformations']:
            assert edit['kept_characters']==len(text)
            assert edit['removed_characters']==len(suffix)
            assert edit['removed_sha256']==hashlib.sha256(suffix.encode()).hexdigest()
        eligible.append((idx,n));total+=n;transformed+=bool(edits['transformations'])
    source_receipt=json.loads((O/'m2-intake/wikipedia-pilot-download.json').read_text())
    source=Path(source_receipt['local_file']);assert sha(source)==policy['source_sha256']
    identities={r[0]:r[1:] for r in db.execute('SELECT row_index,source_id,url,original_sha FROM candidates')}
    raw_index=0;matched=0
    for batch in pq.ParquetFile(source).iter_batches(batch_size=128):
        for raw in batch.to_pylist():
            if raw_index in identities:
                assert (raw['id'],raw['url'],hashlib.sha256(raw['text'].encode()).hexdigest())==identities[raw_index]
                matched+=1
            raw_index+=1
    assert matched==len(eligible)
    assert raw_index==summary['counts']['raw_documents']
    assert len(eligible)==summary['counts']['candidate_documents']
    assert total==summary['candidate_content_tokens']
    assert transformed==summary['counts']['transformed_documents']
    uniform=sorted(eligible,key=lambda x:hashlib.sha256((policy['uniform_seed']+':'+str(x[0])).encode()).digest())[:200]
    c=[];s=0
    for _,n in eligible:s+=n;c.append(s)
    rng=random.Random(policy['weighted_seed'])
    weighted=[eligible[bisect.bisect_right(c,rng.randrange(total))] for _ in range(200)]
    for name,selected in [('uniform',uniform),('token-weighted',weighted)]:
        p=D/(name+'-sample.jsonl');assert sha(p)==summary['samples_sha256'][name]
        records=[json.loads(x) for x in p.read_text().splitlines()];assert len(records)==200
        for draw,(r,(idx,n)) in enumerate(zip(records,selected)):
            assert (r['draw'],r['row_index'],r['tokens'])==(draw,idx,n)
            expected=db.execute('SELECT source_id,url,host,text,original_sha,normalized_sha,tokens,edits FROM candidates WHERE row_index=?',(idx,)).fetchone()
            assert tuple(r[k] for k in ['source_id','url','host','text','original_sha','normalized_sha','tokens','edits'])==expected
            assert r['selection_probability']==(200/len(eligible) if name=='uniform' else n/total)
    receipt={'status':'PASS','candidate_documents':len(eligible),'candidate_content_tokens':total,'reconstructed_originals_verified':len(eligible),'token_counts_independently_reencoded':len(eligible),'sampling_draws_verified':400,'policy_sha256':sha(D/'policy.json'),'candidates_sha256':sha(D/'candidates.sqlite'),'scope':'Integrity and probability sampling only; not semantic, leakage, license or training admission.'}
    (D/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
