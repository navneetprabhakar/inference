"""Recover previously reviewed individual candidates; no cohort extrapolation."""
import collections,hashlib,json,pathlib,sqlite3
from slm.common.tokenizer import BPE
from slm.restart.edu_filter import normalized
O=pathlib.Path(__file__).resolve().parent;I=O/'m2-intake';D=I/'individual-salvage-v1'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    if D.exists():raise FileExistsError('Preserve immutable salvage inventory')
    tok=BPE.load(O/'tokenizer-8192')
    old=sqlite3.connect((O.parents[1]/'restart/corpus-audit-v1/audit.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
    known={r[0] for r in old.execute('SELECT sha FROM docs')}
    known.update(hashlib.sha256(r[0].encode()).hexdigest() for r in old.execute('SELECT normalized FROM protections'));old.close()
    records=[];inputs={};seen=set();counts={};genres=collections.Counter();hits=[]
    for source,cohort in [('fineweb_edu','prose-cohort-v1'),('wikipedia','wikipedia-prose-v1')]:
        root=I/cohort
        for name in ['uniform-sample.jsonl','uniform-judgments.jsonl','policy.json','summary.json']:inputs[cohort+'/'+name]=sha(root/name)
        summary=json.loads((root/'summary.json').read_text())
        if summary['samples_sha256']['uniform']!=sha(root/'uniform-sample.jsonl'):raise ValueError('Changed reviewed sample')
        samples={r['row_index']:r for r in map(json.loads,(root/'uniform-sample.jsonl').read_text().splitlines())}
        counts[source]={'documents':0,'content_tokens':0}
        for judgment in map(json.loads,(root/'uniform-judgments.jsonl').read_text().splitlines()):
            if judgment['label'] not in ('pass','minor'):continue
            item=samples[judgment['row_index']];h=hashlib.sha256(normalized(item['text']).encode()).hexdigest()
            for key in ['original_sha','normalized_sha','tokens','url']:
                if item[key]!=judgment[key]:raise ValueError('Review identity mismatch')
            if h!=item['normalized_sha']:raise ValueError('Changed candidate text')
            tokens=len(tok._core.encode(item['text']).ids)
            if tokens!=item['tokens']:raise ValueError('Changed token count')
            if h in seen or h in known:hits.append({'source':source,'row_index':item['row_index'],'normalized_sha':h});continue
            seen.add(h);counts[source]['documents']+=1;counts[source]['content_tokens']+=tokens;genres[judgment['primary_genre']]+=tokens
            records.append({'source':source,'source_cohort':cohort,'row_index':item['row_index'],'source_id':item.get('source_id'),
                'url':item['url'],'text':item['text'],'original_sha':item['original_sha'],'normalized_sha':h,
                'text_sha256':hashlib.sha256(item['text'].encode()).hexdigest(),'tokens':tokens,'prior_review':judgment,
                'training_admitted':False,'pending':['rights/provenance exceptions','family/near overlap and frozen evaluation screening','factual-risk disposition','split assignment']})
    D.mkdir()
    with (D/'candidates.jsonl').open('w') as f:
        for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    result={'status':'INDIVIDUALLY_REVIEWED_CANDIDATES_NOT_ADMITTED','source_counts':counts,'documents':len(records),
        'content_tokens':sum(r['tokens'] for r in records),'genre_content_tokens':dict(genres),'exact_exclusions':hits,
        'inputs_sha256':inputs,'candidates_sha256':sha(D/'candidates.jsonl'),'tokenizer_manifest_sha256':sha(O/'tokenizer-8192/manifest.json'),
        'new_admitted_documents':0,'new_admitted_tokens':0,'scope':'Existing full-document judgments reused by exact identity; no new semantic review or cohort acceptance claimed.'}
    (D/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['source_counts','documents','content_tokens','exact_exclusions']},indent=2))
if __name__=='__main__':main()
