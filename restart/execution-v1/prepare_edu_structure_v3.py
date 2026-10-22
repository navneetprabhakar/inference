"""Refine an immutable local cohort and freeze independent review draws."""
import bisect, collections, hashlib, json, random, shutil, sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from edu_structure_filter_v3 import reasons, VERSION
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'m2-intake/institutional-prose-v2'
DEST=ROOT/'m2-intake/institutional-structure-v3'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def main():
    if DEST.exists():raise FileExistsError('Frozen output exists')
    budget=load(ROOT/'disk-budget.json')
    floor=budget['free_disk_floor_bytes']+budget['weights_checkpoints_reserved_bytes']+budget['scratch_cap_bytes']
    if shutil.disk_usage(ROOT).free < floor+1024**3:raise ValueError('Disk reserve unavailable')
    assert sha(SOURCE/'candidates.sqlite')==load(SOURCE/'verification.json')['candidate_database_sha256']
    prior=load(SOURCE/'policy.json')
    assert sha(SOURCE/'policy.json')==load(SOURCE/'summary.json')['policy_sha256']
    assert sha(ROOT/'tokenizer-8192/manifest.json')==prior['tokenizer_manifest_sha256']
    judgments=[json.loads(l) for l in (SOURCE/'uniform-judgments.jsonl').read_text().splitlines()]
    assert sha(SOURCE/'uniform-judgments.jsonl')==load(SOURCE/'semantic-review-result.json')['judgments_sha256']
    development_hosts={urlsplit(j['url']).hostname.lower().removeprefix('www.') for j in judgments}
    connection=sqlite3.connect((SOURCE/'candidates.sqlite').as_uri()+'?mode=ro',uri=True);connection.row_factory=sqlite3.Row
    retained=[];excluded=[]
    for item in connection.execute('SELECT * FROM candidates ORDER BY row_index'):
        row=dict(item);why=reasons(row)
        if row['host'] in development_hosts:why.append('development_host_excluded')
        if why:excluded.append({'row_index':row['row_index'],'tokens':row['tokens'],'reasons':why})
        else:retained.append(row)
    connection.close()
    if len(retained)<200:raise ValueError(f'Only {len(retained)} candidates; insufficient 200-document sample')
    DEST.mkdir()
    policy={'pipeline':VERSION,'source_cohort':'institutional-prose-v2','source_database_sha256':sha(SOURCE/'candidates.sqlite'),'source_policy_sha256':sha(SOURCE/'policy.json'),'development_judgments_sha256':sha(SOURCE/'uniform-judgments.jsonl'),'filter_sha256':sha(ROOT/'edu_structure_filter_v3.py'),'builder_sha256':sha(Path(__file__)),'tokenizer_manifest_sha256':prior['tokenizer_manifest_sha256'],'excluded_development_hosts':sorted(development_hosts),'inherited_excluded_development_hosts':prior['excluded_discovery_hosts'],'uniform_seed':'institutional-structure-v3-uniform-20261021','weighted_seed':2026102104,'uniform_n':200,'weighted_n':200,'weighted_design':'Token-proportional independent draws with replacement; retain repeated draws','text_changes':False,'scope':'Subset of pinned parent cohort only; no admission, source-wide claim or factual/license clearance.'}
    (DEST/'policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    with (DEST/'candidates.jsonl').open('x') as f:
        for r in retained:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    with (DEST/'exclusions.jsonl').open('x') as f:
        for r in excluded:f.write(json.dumps(r)+'\n')
    uniform=sorted(retained,key=lambda r:hashlib.sha256((policy['uniform_seed']+':'+str(r['row_index'])).encode()).digest())[:200]
    cumulative=[];total=0
    for row in retained:total+=row['tokens'];cumulative.append(total)
    rng=random.Random(policy['weighted_seed']);weighted=[retained[bisect.bisect_right(cumulative,rng.randrange(total))] for _ in range(200)]
    for name,items in [('uniform',uniform),('token-weighted',weighted)]:
        with (DEST/(name+'-sample.jsonl')).open('x') as f:
            for draw,row in enumerate(items):
                f.write(json.dumps(row|{'draw':draw,'sampling':name,'selection_probability':200/len(retained) if name=='uniform' else row['tokens']/total,'probability_kind':'inclusion' if name=='uniform' else 'per_draw'},ensure_ascii=False)+'\n')
    result={'status':'AWAITING_FULL_SEMANTIC_REVIEW','parent_documents':len(retained)+len(excluded),'candidate_documents':len(retained),'candidate_provisional_content_tokens':total,'excluded_documents':len(excluded),'excluded_provisional_content_tokens':sum(r['tokens'] for r in excluded),'exclusion_reason_counts':dict(collections.Counter(reason for r in excluded for reason in r['reasons'])),'uniform_unique_documents':len({r['row_index'] for r in uniform}),'weighted_unique_documents':len({r['row_index'] for r in weighted}),'union_unique_documents':len({r['row_index'] for r in uniform+weighted}),'hashes':{n:sha(DEST/n) for n in ['policy.json','candidates.jsonl','exclusions.jsonl','uniform-sample.jsonl','token-weighted-sample.jsonl']},'new_admitted_documents':0,'new_admitted_tokens':0,'remaining':['fresh semantic and factual review','language windows','full near/family/protected overlap','rights/provenance','split assignment'],'token_units':'Existing M1 tokenizer content tokens, provisional for M2; no new tokenizer fitting.'}
    (DEST/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
