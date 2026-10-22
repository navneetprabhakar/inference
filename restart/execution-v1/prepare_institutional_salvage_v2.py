"""Identity-bound strict-pass salvage from rejected institutional cohorts; no admission."""
import collections,hashlib,json,pathlib,sqlite3
from slm.common.tokenizer import BPE
from slm.restart.edu_filter import normalized
O=pathlib.Path(__file__).resolve().parent; I=O/'m2-intake';D=I/'individual-salvage-v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 if D.exists():raise FileExistsError('Preserve immutable salvage inventory')
 tok=BPE.load(O/'tokenizer-8192');db=sqlite3.connect((O.parents[1]/'restart/corpus-audit-v1/audit.sqlite').as_uri()+'?mode=ro',uri=True)
 known={r[0] for r in db.execute('SELECT sha FROM docs')};known.update(hashlib.sha256(r[0].encode()).hexdigest() for r in db.execute('SELECT normalized FROM protections'));db.close()
 prior=[json.loads(l) for l in (I/'individual-salvage-v1/candidates.jsonl').read_text().splitlines()];known.update(r['normalized_sha'] for r in prior)
 records=[];seen=set();inputs={};hits=[]
 for cohort in ['institutional-prose-v2','institutional-structure-v3']:
  p=I/cohort;result=json.loads((p/'semantic-review-result.json').read_text());assert result['status']=='REJECTED_EARLY_UNIFORM_QUALITY_GATE'
  assert sha(p/'uniform-sample.jsonl')==result['sample_sha256'];assert sha(p/'uniform-judgments.jsonl')==result['judgments_sha256']
  for f in ['uniform-sample.jsonl','uniform-judgments.jsonl','semantic-review-result.json']:inputs[cohort+'/'+f]=sha(p/f)
  sample={r['row_index']:r for r in map(json.loads,(p/'uniform-sample.jsonl').read_text().splitlines())}
  for judgment in map(json.loads,(p/'uniform-judgments.jsonl').read_text().splitlines()):
   if judgment['label']!='pass':continue
   r=sample[judgment['row_index']]
   for k in ['original_sha','normalized_sha','url','tokens']:assert r[k]==judgment[k]
   normhash=hashlib.sha256(normalized(r['text']).encode()).hexdigest();assert normhash==r['normalized_sha']
   assert len(tok._core.encode(r['text']).ids)==r['tokens']
   if normhash in known or normhash in seen:hits.append({'cohort':cohort,'row_index':r['row_index'],'normalized_sha':normhash});continue
   seen.add(normhash)
   records.append({'source':'fineweb_edu','source_cohort':cohort,**{k:r[k] for k in ['row_index','source_id','url','text','original_sha','normalized_sha','tokens']},'text_sha256':hashlib.sha256(r['text'].encode()).hexdigest(),'prior_review':judgment,'training_admitted':False,'pending':['full overlap/family and protected text screening','language windows','factual-risk disposition','rights/provenance','split assignment']})
 D.mkdir()
 with (D/'candidates.jsonl').open('w') as f:
  for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 receipt={'status':'STRICT_PASS_CANDIDATES_NOT_ADMITTED','documents':len(records),'content_tokens':sum(r['tokens'] for r in records),'cohort_counts':dict(collections.Counter(r['source_cohort'] for r in records)),'exact_exclusions':hits,'inputs_sha256':inputs,'candidates_sha256':sha(D/'candidates.jsonl'),'tokenizer_manifest_sha256':sha(O/'tokenizer-8192/manifest.json'),'new_admitted_documents':0,'new_admitted_tokens':0,'scope':'Unchanged individually reviewed strict-pass text only; not representative quality evidence or factual certification.'}
 (D/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
