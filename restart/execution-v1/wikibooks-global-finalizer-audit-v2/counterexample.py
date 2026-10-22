import hashlib,json,pathlib,sys
from unittest.mock import patch
D=pathlib.Path(__file__).resolve().parent;S=D.parent/'wikibooks-global-finalizer-preparation-v2';sys.path.insert(0,str(S));import finalize as f
source=(S/'check_pipeline.py').read_text();needle="(i,i,i+10,'old-unreconciled',json.dumps(r))";assert needle in source;changed=source.replace(needle,"(i,999,9999,'old-unreconciled',json.dumps(r))");real=f.run;observed=[]
def watch(*args,**kwargs):
 value=real(*args,**kwargs);out=args[1]
 if (out/'result.json').exists() and json.loads((out/'result.json').read_text())['status']=='COMPLETE_GLOBAL_STRUCTURAL_RECONCILIATION_PROVISIONAL_NO_ADMISSION':
  import sqlite3
  db=sqlite3.connect(out/'finalized.sqlite3');observed.extend(db.execute('select source_ordinal,page_id,revision_id from pages order by source_ordinal').fetchall());db.close()
 return value
with patch.object(f,'run',side_effect=watch):exec(compile(changed,str(S/'check_pipeline.py'),'exec'),{'__name__':'__counterexample__','__file__':str(S/'check_pipeline.py')})
assert observed[:2]==[(1,999,9999),(2,999,9999)]
report={'status':'CONFIRMED_COUNTEREXAMPLE_TOPLEVEL_IDENTITIES_NOT_CHECKED','synthetic_only':True,'trigger':'Synthetic rendered SQLite outer page_id/revision_id changed to999/9999; canonical source and JSON payload retain correct identities1/11 and2/12. Recipe pins updated consistently for synthetic fixture.','observed_complete_output_page_rows':observed,'expected_page_rows':[[1,1,11],[2,2,12]],'finding':'run verifies JSON provenance against canonical but copies unchecked outer SQL page/revision into final pages. COMPLETE status can contain incorrect/duplicate page identities.','minimal_fix':'For every rendered row require outer page==r[page_id], outer rev==r[revision_id]; for active canonical rows require these match e too. Preserve intended family override from canonical. Add focused outer-page/outer-revision tamper refusals.','no_real_corpus_processed':True,'no_source_preparation_modified':True}
(D/'identity-counterexample.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
