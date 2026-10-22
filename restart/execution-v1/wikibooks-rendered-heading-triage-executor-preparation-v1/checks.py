"""Synthetic only: actual frame/core/output/supervisor paths; never source feature execution."""
import pathlib,tempfile,json,sqlite3,sys,time,signal,os,random,importlib.util,types
import feature_core as core,supervisor_core as supervisor,triage
HERE=pathlib.Path(__file__).resolve().parent

def run():
 tests=[]
 def ok(name,fn):fn();tests.append(name)
 def no(name,fn):
  try:fn()
  except (ValueError,TimeoutError,OSError):tests.append(name);return
  raise AssertionError(name)
 def blockrows(kinds):
  rows=[];at=0
  for i,(kind,n) in enumerate(kinds):rows.append((i,kind,'a'*64,n,at,at+n));at+=n+2
  return rows,at-2
 for name,kinds,n in [('empty_leaf',[('h2',3)],1),('empty_parent_leaf',[('h2',3),('h3',3)],2),('short_definition',[('h2',3),('p',1)],0),('code_positive',[('h2',3),('pre',1)],0),('reference_li_positive',[('h2',3),('li',1)],0),('procedure_li_positive',[('h2',3),('li',1)],0),('unknown_positive',[('h2',3),('future_kind',1)],0),('historical_prose_positive',[('h2',3),('p',1)],0),('zero_chars_not_content',[('h2',3),('p',0)],1),('close_neighbor',[('h2',3),('h2',3),('p',1)],1)]:
  rows,chars=blockrows(kinds);assert core.summarize(rows,chars)['empty_subtrees']==n;tests.append(name)
 # Exact equivalence to previously frozen metadata diagnostic core across1k traces.
 spec=importlib.util.spec_from_file_location('prior',HERE.parent/'wikibooks-rendered-heading-triage-preparation-v1/triage_core.py');prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior);rng=random.Random(104)
 for _ in range(1000):
  rows,chars=blockrows([(rng.choice(['h1','h2','h3','h4','h5','h6','p','li','pre','future']),rng.randrange(0,30)) for _ in range(rng.randrange(1,80))]);a=core.summarize(iter(rows),chars);v=prior.diagnose([dict(ordinal=i,kind=k,hash=h,characters=n) for i,k,h,n,_,_ in rows]);assert a['empty_subtrees']==len(v['empty_heading_subtrees']) and a['empty_leaf_subtrees']==v['empty_leaf_heading_subtrees'] and a['nonempty_nonheading']==v['nonempty_nonheading_blocks'] and a['unknown_kinds']==len(v['unknown_kind_diagnostics'])
 tests.append('1000_full_prior_v_streaming_metadata_equal')
 rows,chars=blockrows([('h2',1),('p',2)]);
 for name,alter in [('ordinal_gap',lambda r:r.__setitem__(0,(2,*r[0][1:]))),('bad_hash',lambda r:r.__setitem__(0,(*r[0][:2],'x',*r[0][3:]))),('negative_length',lambda r:r.__setitem__(0,(*r[0][:3],-1,*r[0][4:]))),('range_gap',lambda r:r.__setitem__(1,(*r[1][:4],9,11)))]:
  r=list(rows);alter(r);no(name,lambda r=r:core.summarize(r,chars))
 no('final_char_coverage_mismatch',lambda:core.summarize(rows,chars+1));no('empty_metadata_document_hold',lambda:core.summarize([],0))
 rows,chars=blockrows([('h2',1)]*1000);f=core.summarize(iter(rows),chars);raw=core.bounded_record({'source_ordinal':1,'family':'z'*256,'text_sha256':'b'*64},f);j=json.loads(raw);assert len(raw)<=1024 and j['feature']['empty_subtrees']==1000 and j['empty_examples_omitted']>0 and j['feature']['empty_close_event_SHA256']==f['empty_close_event_SHA256'];tests.append('1000_empty_headings_bounded_output_counts_digest_retained')
 def row(i):return dict(source_ordinal=i,page_id=i+10,revision_id=i+20,family='family',text_sha256=str(i)*64,content_tokens=10,tokens_plus_one_EOS=11,language_pass=1,known_discovery_hold=0,holds='[]')
 rows=[row(i) for i in [1,2,3]];overlay=[dict(source_ordinal=3,page_id=13,revision_id=23,text_SHA256='3'*64,stored_M1_content_tokens=10)];expected={'base_documents':3,'base_tokens':30,'held_documents':1,'held_tokens':10,'candidate_documents':2,'candidate_tokens':20};a,c,h=core.select_frame(rows,overlay,expected);assert set(c)=={1,2} and h=={3};tests.append('production_frame_overlay_excluded_not_candidate')
 no('production_duplicate_frame_ID',lambda:core.select_frame(rows+[rows[0]],overlay,expected));no('production_bad_hold_revision',lambda:core.select_frame(rows,[{**overlay[0],'revision_id':99}],expected));no('production_language_hold_never_promoted',lambda:core.select_frame([{**rows[0],'language_pass':0}]+rows[1:],overlay,expected));no('production_tokens_EOS_consistency',lambda:core.select_frame([{**rows[0],'tokens_plus_one_EOS':10}]+rows[1:],overlay,expected))
 with tempfile.TemporaryDirectory() as temp:
  root=pathlib.Path(temp);db=root/'x.sqlite';d=sqlite3.connect(db);d.executescript('create table rendered(source_ordinal integer primary key,page_id integer,revision_id integer,family text,data text);create table blocks(source_ordinal integer,ordinal integer,kind text,hash text,characters integer,start integer,end integer,primary key(source_ordinal,ordinal));');d.execute('insert into rendered values(1,11,21,?,?)',('family','DO_NOT_READ_BODY'));d.execute('insert into blocks values(1,0,?,?,?,?,?)',('p','a'*64,1,0,1));d.commit();d.close();d=triage.connect(db);trace=[];d.set_trace_callback(trace.append);got=list(d.execute('select source_ordinal,page_id,revision_id,family from rendered where source_ordinal in (?) order by source_ordinal',[1]));features=core.summarize(d.execute('select ordinal,kind,hash,characters,start,end from blocks where source_ordinal=? order by ordinal',[1]),1);d.close();assert got==[(1,11,21,'family')] and features['nonempty_nonheading']==1 and not any('data' in x.lower() for x in trace);tests.append('actual_SQLite_exact_metadata_queries_never_project_body_data')
  # Existing output must remainbyte-identical on refusal.
  out=root/'old';out.mkdir();(out/'supervisor.json').write_text('old');before=(out/'supervisor.json').read_bytes()
  no('actual_existing_output_preserved',lambda:supervisor.supervise(out,lambda t:[],lambda:None));assert (out/'supervisor.json').read_bytes()==before
  # Earliest slotsetup failure still writes partial terminal; no child launched.
  out=root/'slots';oldwrite=pathlib.Path.write_bytes
  def broken(path,data):
   if path.name=='result.json':raise OSError('synthetic_first_slot_failure')
   return oldwrite(path,data)
  pathlib.Path.write_bytes=broken
  try:no('actual_first_slot_failure_partial_receipt',lambda:supervisor.supervise(out,lambda t:[],lambda:None))
  finally:pathlib.Path.write_bytes=oldwrite
  assert json.loads((out/'supervisor.json').read_text())['status']=='PARTIAL_NO_RETRY'
  # Signal and real timer are armed before preflight.
  for case in ['deadline','term','int']:
   oldarm=supervisor.arm
   def arm(seconds):oldarm(.03 if case=='deadline' else seconds)
   supervisor.arm=arm;out=root/case
   def pre():
    if case=='deadline':time.sleep(1)
    else:signal.raise_signal(signal.SIGTERM if case=='term' else signal.SIGINT)
   try:no('actual_supervisor_preflight_'+case,lambda:supervisor.supervise(out,lambda t:[],pre))
   finally:supervisor.arm=oldarm
   assert not out.exists()
  out=root/'success';code='import pathlib,json,sys; p=pathlib.Path(sys.argv[1]); f=p/"result.json"; n=f.stat().st_size; b=json.dumps({"status":"COMPLETE_SYNTHETIC"}).encode(); f.write_bytes(b+b" "*(n-len(b)))'
  supervisor.supervise(out,lambda t:[sys.executable,'-B','-c',code,str(out)],lambda:None);receipt=json.loads((out/'supervisor.json').read_text());assert receipt['status']=='COMPLETE' and receipt['child_reaped'] and receipt['returncode']==0;tests.append('actual_synthetic_worker_lifecycle_finalRSS_reaped')
 return {'status':'PASS_SYNTHETIC_ONLY_NO_RETAINED_METADATA_FEATURE_SCAN','controls':len(tests),'cases':tests}
if __name__=='__main__':print(json.dumps(run(),indent=2))
