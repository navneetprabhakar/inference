"""Exact production matcher/stream/indexed-role synthetic controls; no corpus scan."""
import collections,json,pathlib,random,sqlite3,tempfile
import overlap_core as core,sources,audit

def reference(idx,norm):
 words=norm.split();g=core.grams(words,5);out={}
 for i,value in enumerate(idx.norms):
  if norm==value:out.setdefault(i,{})['normalized_exact']=True
  n=len(g & idx.sets[i]);union=len(g|idx.sets[i])
  if union and n*5>=union*4:out.setdefault(i,{})['fivegram_Jaccard_gte_0p8']={'intersection':n,'union':union,'jaccard':n/union}
 for i,detail in idx.containment(words).items():out.setdefault(i,{})['containment']=detail
 return out

def run():
 checks=[]
 def check(name,condition):
  assert condition,name
  checks.append({'check':name,'PASS':True})
 words=['word'+str(i) for i in range(24)];idx=core.Index([' '.join(words)])
 for n in [24,25,26]:
  text=' '.join(words+['extra'+str(i) for i in range(n-20)])
  check('exact_distinct_source_cardinality_threshold_'+str(n),len(core.grams(text.split(),5))==n and idx.compare(text)==reference(idx,text))
 check('at_exact_point8_is_retained',0 in idx.compare(' '.join(words+['extra'+str(i) for i in range(5)])))
 check('one_above_exact_point8_cannot_match',0 not in idx.compare(' '.join(words+['extra'+str(i) for i in range(6)])))
 long=['long'+str(i) for i in range(44)];multi=core.Index([' '.join(words),' '.join(long)])
 for n in [49,50,51]:
  text=' '.join(long+['tail'+str(i) for i in range(n-40)])
  check('different_candidate_sizes_global_threshold_'+str(n),multi.compare(text)==reference(multi,text))
 text=' '.join(long+['tail'+str(i) for i in range(100)])
 result=multi.compare(text)
 check('early_bound_still_runs_entire_source_containment',1 in result and 'containment' in result[1] and 'fivegram_Jaccard_gte_0p8' not in result[1])
 # A distant source hit after the impossible-cardinality prefix must survive.
 text=' '.join(['prefix'+str(i) for i in range(96)]+long)
 check('containment_after_early_bound_prefix_not_truncated',multi.compare(text)==reference(multi,text) and 1 in multi.compare(text))
 rng=random.Random(1729)
 for _ in range(100):
  text=' '.join(rng.choice(['a','b','c','d','e','f','g']) for _ in range(rng.randrange(0,250)))
  small=core.Index(['a b c d e f g a b c d e','different short text'])
  assert small.compare(text)==reference(small,text)
 check('100_repeated_word_cases_equal_full_set_reference',True)
 with tempfile.TemporaryDirectory() as tmp:
  root=pathlib.Path(tmp);db=sqlite3.connect(root/'roles.sqlite');db.execute('create table pages(source_ordinal integer primary key,page_id,revision_id,family,text_sha256,holds,active)');db.execute('create table final_pages(source_ordinal integer primary key,holds)');db.execute('insert into pages values (?,?,?,?,?,?,?)',(7,8,9,'family','hash','["prior"]',1));db.execute('insert into final_pages values (?,?)',(7,'["final"]'));db.commit()
  expected={'page_id':8,'revision_id':9,'family':'family','text_sha256':'hash','prior_holds':['prior'],'global_final_holds':['final'],'active':1}
  check('actual_indexed_Wikibooks_role_preserves_all_fields_and_holds',audit.current_wikibooks_role(db,7)==expected)
  check('actual_indexed_Wikibooks_missing_ordinal_explicit_none',audit.current_wikibooks_role(db,999) is None);db.close()
  import pyarrow as pa,pyarrow.parquet as pq
  p=root/'tiny.parquet';pq.write_table(pa.table({'text':['one source','two source'],'id':['1','2'],'title':['A','B']}),p,row_group_size=2)
  original=pq.ParquetFile;calls=[];closed=[]
  class Checked:
   def __init__(self,*a,**kw):
    assert kw=={'memory_map':True,'pre_buffer':False};self.pf=original(*a,**kw);self.schema_arrow=self.pf.schema_arrow
   def iter_batches(self,*a,**kw):
    calls.append(kw);assert kw['batch_size']==1 and kw['use_threads'] is False
    yield from self.pf.iter_batches(*a,**kw)
   def close(self):closed.append(True);self.pf.close()
  pq.ParquetFile=Checked
  try:rows=list(sources.stream({'path':str(p),'adapter':'parquet_text'},lambda:None))
  finally:pq.ParquetFile=original
  check('actual_parquet_adapter_serial_one_row_scalar_values',[(i,t,m['id']) for i,t,m in rows]==[('1','one source','1'),('2','two source','2')] and bool(calls))
  check('actual_parquet_handle_closed_after_stream',closed==[True])
 return {'status':'PASS_MEMORY_REVISION_SYNTHETIC_ONLY_NO_CORPUS_SCAN','count':len(checks),'checks':checks,'exact_bound_proof':'For source unique fivegrams S and each candidate C: intersection<=|C| and union>=|S|. If |S|>floor(5*maxC/4), then |C|/|S|<4/5 for every candidate. Distinct tuple sets only; no hash approximation; full containment runs independently.','no_network_or_models':True}
if __name__=='__main__':print(json.dumps(run(),indent=2))
