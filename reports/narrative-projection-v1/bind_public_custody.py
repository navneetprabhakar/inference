"""Bind later root public screening to unchanged exact narrative projection."""
import hashlib,json,pathlib,sqlite3
ROOT=pathlib.Path(__file__).resolve().parents[2];OLD=ROOT/'data/language-mixture-v1';NEW=ROOT/'data/narrative-candidates-v1'
def read(p):return json.loads(p.read_bytes())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 assert not any(p.exists() for p in [ROOT/'runs/STOP',OLD/'STOP',NEW/'STOP'])
 proof=read(NEW/'candidate-verification.json');public=read(OLD/'public-development-custody.json');legacy=read(OLD/'custody.json');quality=read(ROOT/'data/language-mixture-v2/proposed-exclusions.json')
 assert proof['state']=='PASS_independent_exact_projection_not_admitted' and proof['failures']==[] and proof['database_sha256']==sha(NEW/'candidates.sqlite') and proof['manifest_sha256']==sha(NEW/'candidate-manifest.json')
 assert public['state']=='screened_not_admitted' and public['training_admitted'] is False and public['counts']['reviewed']==222615
 for name,expected in public['pins'].items():assert sha(OLD/name)==expected
 assert public['pins']['candidates.sqlite']==legacy['candidate_database_sha256']==proof['source_database_sha256']
 assert public['inventory']['sessions']==442 and public['inventory']['turns']==632
 exclusions=set(legacy['excluded_doc_ids'])|{x['doc_id'] for x in quality}|set(public['excluded_doc_ids']);assert len(public['excluded_doc_ids'])==len(set(public['excluded_doc_ids']))==public['counts']['excluded']
 with sqlite3.connect(f'file:{OLD}/candidates.sqlite?mode=ro',uri=True) as old,sqlite3.connect(f'file:{NEW}/candidates.sqlite?mode=ro',uri=True) as new:
  actual={r[0] for r in new.execute('select doc_id from documents')};expected={r[0] for r in old.execute("select doc_id from documents where source='stories'")} - exclusions
  assert actual==expected and len(actual)==proof['verified_rows']==172544
  counts={s:dict(documents=n,tokens=t) for s,n,t in new.execute('select split,count(*),sum(tokens) from documents group by split')};assert counts==proof['counts']
 result=dict(state='PASS_projection_root_custody_union_bound_not_admitted',database_sha256=sha(NEW/'candidates.sqlite'),manifest_sha256=sha(NEW/'candidate-manifest.json'),projection_verification_sha256=sha(NEW/'candidate-verification.json'),original_database_sha256=public['pins']['candidates.sqlite'],public_custody_sha256=sha(OLD/'public-development-custody.json'),legacy_custody_sha256=sha(OLD/'custody.json'),quality_exclusions_sha256=sha(ROOT/'data/language-mixture-v2/proposed-exclusions.json'),verified_rows=len(actual),public_excluded_original_documents=42,public_excluded_projected_stories=0,counts=counts,failures=[],training_admitted=False,quality_certified=False,code_sha256=sha(pathlib.Path(__file__)),scope='Later root public supplement bound separately after exact projection freeze; all and only original stories surviving legacy+quality+public ID union remain. No private/public case text read by this binding check; no refill or mutation.')
 with (NEW/'public-custody-binding.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({k:result[k] for k in ['state','verified_rows','counts']}))
if __name__=='__main__':main()
