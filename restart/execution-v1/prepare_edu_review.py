"""Freeze candidate pipeline and draw uniform/PPS-with-replacement review samples."""
import collections,hashlib,json,math,pathlib,random,sqlite3,shutil,time,bisect
from urllib.parse import urlsplit
import pyarrow.parquet as pq
from slm.restart.edu_filter import transform,normalized,VERSION
from slm.common.tokenizer import BPE
O=pathlib.Path(__file__).resolve().parent;R=O.parents[1];I=O/'m2-intake';D=I/'prose-cohort-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if D.exists():raise FileExistsError('Frozen cohort exists; no in-place rerun')
    disk=json.loads((O/'disk-budget.json').read_text());minimum=disk['free_disk_floor_bytes']+disk['weights_checkpoints_reserved_bytes']+disk['scratch_cap_bytes']
    if shutil.disk_usage(O).free<minimum+2*1024**3:raise ValueError('Insufficient reserved disk headroom')
    D.mkdir();receipt=json.loads((I/'edu-pilot-download.json').read_text());source=pathlib.Path(receipt['local_file'])
    if sha(source)!=receipt['sha256']:raise ValueError('Raw source changed')
    code=R/'src/slm/restart/edu_filter.py';tokenizer=O/'tokenizer-8192';tok=BPE.load(tokenizer)
    discovery=[json.loads(x) for x in (I/'discovery-sample.jsonl').read_text().splitlines()]
    excluded_hosts={urlsplit(x['url']).hostname.lower().removeprefix('www.') for x in discovery}
    old=sqlite3.connect(f'file:{R}/restart/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
    known={r[0] for r in old.execute('SELECT sha FROM docs')}
    known.update(hashlib.sha256(r[0].encode()).hexdigest() for r in old.execute('SELECT normalized FROM protections'));old.close()
    policy={'pipeline':VERSION,'filter_sha256':sha(code),'source_sha256':receipt['sha256'],'source_revision':receipt['revision'],'tokenizer_manifest_sha256':sha(tokenizer/'manifest.json'),'excluded_discovery_hosts':sorted(excluded_hosts),'uniform_seed':'edu-v1-uniform-20261021','weighted_seed':2026102102,'uniform_n':200,'weighted_n':200,'weighted_design':'independent token-proportional draws with replacement; duplicates are retained and not counted as unique reviews','status':'candidate eligibility only; no admission','scope':'one pinned pilot shard; no extrapolation to other shards/source'}
    (D/'policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    db=sqlite3.connect(D/'candidates.sqlite');db.execute('CREATE TABLE candidates (row_index INTEGER PRIMARY KEY,source_id TEXT,url TEXT,host TEXT,text TEXT,original_sha TEXT,normalized_sha TEXT UNIQUE,tokens INTEGER,edits TEXT)')
    counts=collections.Counter();eligible=[];row_index=0;started=time.time();token_total=0
    with (D/'exclusions.jsonl').open('w') as rejected:
        for batch in pq.ParquetFile(source).iter_batches(batch_size=256):
            pending=[]
            for row in batch.to_pylist():
                idx=row_index;row_index+=1;counts['raw_documents']+=1
                text,reasons,edits=transform(row)
                host=(urlsplit(row['url']).hostname or '').lower().removeprefix('www.')
                if host in excluded_hosts:reasons.append('discovery_host_excluded')
                norm=normalized(text) if text else '';h=hashlib.sha256(norm.encode()).hexdigest()
                if h in known:reasons.append('previously_seen_or_protected_exact')
                if reasons:
                    counts.update(reasons);rejected.write(json.dumps({'row_index':idx,'reasons':reasons})+'\n');continue
                known.add(h);pending.append((idx,row,host,text,h,edits))
            encodings=tok._core.encode_batch([x[3] for x in pending])
            for (idx,row,host,text,h,edits),encoding in zip(pending,encodings):
                n=len(encoding.ids)
                db.execute('INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?)',(idx,row['id'],row['url'],host,text,hashlib.sha256(row['text'].encode()).hexdigest(),h,n,json.dumps(edits)))
                eligible.append((idx,n));counts['candidate_documents']+=1;token_total+=n;counts['transformed_documents']+=bool(edits)
            db.commit()
            if row_index%25600==0:print(row_index,'rows',counts['candidate_documents'],'candidates',flush=True)
    if len(eligible)<200:raise ValueError('Insufficient candidate supply')
    uniform=sorted(eligible,key=lambda x:hashlib.sha256((policy['uniform_seed']+':'+str(x[0])).encode()).digest())[:200]
    cumulative=[];total=0
    for _,n in eligible:total+=n;cumulative.append(total)
    rng=random.Random(policy['weighted_seed']);weighted=[eligible[bisect.bisect_right(cumulative,rng.randrange(total))] for _ in range(200)]
    for name,selected in [('uniform',uniform),('token-weighted',weighted)]:
        with (D/(name+'-sample.jsonl')).open('w') as out:
            for draw,(idx,n) in enumerate(selected):
                rec=db.execute('SELECT source_id,url,host,text,original_sha,normalized_sha,tokens,edits FROM candidates WHERE row_index=?',(idx,)).fetchone()
                out.write(json.dumps(dict(zip(['source_id','url','host','text','original_sha','normalized_sha','tokens','edits'],rec))|{'row_index':idx,'draw':draw,'sampling':name,'selection_probability':200/len(eligible) if name=='uniform' else n/total,'probability_kind':'inclusion' if name=='uniform' else 'per_draw'},ensure_ascii=False)+'\n')
    db.close()
    summary={'status':'AWAITING_FULL_SEMANTIC_REVIEW','counts':dict(counts),'candidate_content_tokens':token_total,'tokenizer':'M1 8192-ID, provisional M2 accounting; final M3 tokenizer not selected','uniform_unique_documents':len(set(i for i,n in uniform)),'weighted_unique_documents':len(set(i for i,n in weighted)),'union_unique_documents':len(set(i for i,n in uniform+weighted)),'policy_sha256':sha(D/'policy.json'),'samples_sha256':{n:sha(D/(n+'-sample.jsonl')) for n in ['uniform','token-weighted']},'elapsed_seconds':time.time()-started,'admitted_documents':0,'remaining_checks':['semantic quality','factual-risk audit','language windows','full family/near/protected overlap','source/genre mixture','split assignment']}
    (D/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
