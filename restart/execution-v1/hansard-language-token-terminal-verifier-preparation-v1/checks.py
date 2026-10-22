"""Tiny stored-SQL fixtures, never PB source bodies or inference."""
from pathlib import Path
import sys,tempfile,json,sqlite3,hashlib,copy,types,time,signal
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import runner,core
import engine,rules
cases=[]
def must(fn):
 try:fn()
 except Exception:return
 raise AssertionError('expected refusal')
def fixture(path):
 p=json.loads((runner.PRODUCER/'profile.json').read_text());p['sources']=[{'source_id':1,'rows':2}];p['known_targets']={'semantic_text_SHA256':'0'*64,'expected_bindings':[]};db=sqlite3.connect(':memory:');db.execute('create table records(source_id integer,ordinal integer,line_offset integer,line_bytes integer,ends_LF integer,line_SHA256 blob,flags integer,id text,source text,added text,year text,language text,license text,text_SHA256 blob,text_UTF8_bytes integer,text_chars integer)');store=engine.Store(path,p['limits'],lambda *a:None);batch=[];stats={'documents':2,'UTF8_bytes':0,'characters':0,'all_windows':0}
 for n in [1,2]:
  text='English prose '*80+'x'*39;raw=text.encode();identity='ID'+str(n);w,size=engine.prepared(text);m=[1,n,(n-1)*len(raw),len(raw),0,hashlib.sha256(raw).digest(),64,identity,'uk-hansard-northern-ireland-assembly' if n==1 else 'uk-hansard-london-mayors-questions','2020-01-01','2020','en','unverified',hashlib.sha256(raw).digest(),len(raw),len(text)];db.execute('insert into records values('+','.join('?'*16)+')',m);batch.append({'doc':n,'identity':{'source':1,'ordinal':n,'id':identity,'text_SHA256':m[13].hex(),'line_SHA256':m[5].hex(),'characters':m[15],'UTF8_bytes':m[14],'source_flags':64,'rights_unclear_flags':n},'tokens':10,'windows':w,'explicit_flags':0,'normalized_SHA256':hashlib.sha256(b'english prose').digest(),'normalized_words':160});stats['UTF8_bytes']+=len(raw);stats['characters']+=len(text);stats['all_windows']+=len(w)
 store.batch(p,batch,30,lambda p,data,*a:['__label__en 0.9']*data.count(b'\n'));r={'stats':store.stats.copy(),'summary':store.summary(),'known_hold_bindings':[],'rights_diagnostic_counts':[[1,1],[2,1]],'all_record_rights_status':'UNCLEARED_REGARDLESS_FLAGS'};p['rights_expected_counts']=[[1,1],[2,1]];store.close();p['limits'].update(stats);return p,r,db
with tempfile.TemporaryDirectory()as z:
 p,r,source=fixture(z);output=sqlite3.connect(Path(z)/'screening.sqlite');good=core.verify(output,{1:source},r,p,lambda:None);assert good['totals']['documents']==2 and good['distinct_raw_text_hashes']==1;cases.append('actual_tiny_SQL_allrow_windows_raw_distinct_EOS_summary_join')
 mutations=[('rawline','update docs set line_SHA256=zeroblob(32) where doc=1'),('ID','update docs set id_SHA256=zeroblob(32) where doc=1'),('ordinal','update docs set source_ordinal=3 where doc=2'),('text','update docs set text_SHA256=zeroblob(32) where doc=1'),('sourceflags','update docs set source_flags=0 where doc=1'),('rights_flag','update docs set rights_unclear_flags=0 where doc=1'),('rights_distinct_union','update texts set rights_unclear_flags=1'),('windowspan','update windows set end=end-1 where doc=1 and ordinal=1'),('alphascore','update windows set alphabetics=0 where doc=1 and ordinal=1'),('missingwindow','delete from windows where doc=1 and ordinal=1'),('extrawindow','insert into windows select doc,100,kind,start,end,alphabetics,raw_SHA256,projection_SHA256,scored,skip_reason,label,raw_probability,top_probability,english_probability,policy_pass from windows where doc=1 and ordinal=0'),('rawprob','update windows set raw_probability="nan" where doc=1 and ordinal=0'),('minprob','update docs set min_english=0.89 where doc=1'),('holdbit','update docs set explicit_hold_flags=4 where doc=1'),('EOS','update docs set EOS_count=0 where doc=1'),('distinctoccurrence','update texts set occurrences=1'),('distincttokens','update texts set content_tokens=9'),('distinctnorm','update texts set normalized_words=159'),('duplicatehashnorm','update docs set normalized_words=159 where doc=1')]
 for name,sql in mutations:
  output.execute('savepoint x');output.execute(sql);must(lambda:core.verify(output,{1:source},r,p,lambda:None));output.execute('rollback to x');output.execute('release x');cases.append('refuse_'+name)
 bad=copy.deepcopy(r);bad['summary']['all_raw']['EOS_separate']=0;must(lambda:core.verify(output,{1:source},bad,p,lambda:None));cases.append('producer_summary_not_self_certifying');source.close();output.close()
with tempfile.TemporaryDirectory() as z:
 p,r,source=fixture(z);output=sqlite3.connect(Path(z)/'screening.sqlite');textSHA=output.execute('select text_SHA256 from docs where doc=1').fetchone()[0];p['known_targets']['semantic_text_SHA256']=textSHA.hex();output.execute('update docs set explicit_hold_flags=1');output.execute('update texts set explicit_hold_flags=1');p['known_targets']['expected_bindings']=[[1,n,hashlib.sha256(('ID'+str(n)).encode()).hexdigest(),textSHA.hex(),1]for n in [1,2]];r['known_hold_bindings']=p['known_targets']['expected_bindings']
 for k in ['raw_language_pass_after_explicit_known_holds','distinct_text_language_pass_without_any_explicit_hold_occurrence']:
  r['summary'][k]={a:(False if a=='usable_or_admitted' else 0) for a in r['summary'][k]}
 assert core.verify(output,{1:source},r,p,lambda:None)['known_bindings']==p['known_targets']['expected_bindings'];cases.append('exact_semantic_textSHA_hold_propagates_to_all_different_IDcopies')
 bad=copy.deepcopy(r);bad['all_record_rights_status']='CLEARED';must(lambda:core.verify(output,{1:source},bad,p,lambda:None));cases.append('zero_region_flag_never_becomes_blanket_rights_clearance');source.close();output.close()
for label in ['__label__fr','__label__en']:
 row=[1,0,0,0,3,3,b'x'*32,b'y'*32,1,None,label,'0.8',.8,.8 if label.endswith('en') else 0.,1 if label.endswith('en') else 0]
 assert core.window(row,1,0,3)==(.8 if label.endswith('en') else 0.)
cases.append('independent_top1_nonEnglish_zero_threshold')
old=runner.START;runner.START=time.monotonic()-1194.98
try:
 with patch.object(runner,'verify',lambda a:time.sleep(.1)):must(lambda:runner.supervise(types.SimpleNamespace()))
finally:runner.START=old;signal.setitimer(signal.ITIMER_REAL,0)
cases.append('actual_supervisor_deadline_before_preflight')
with tempfile.TemporaryDirectory()as z:
 marker=Path(z)/'original';marker.write_bytes(b'unchanged')
 with patch.object(runner,'verify',lambda a:{'output':z}),patch.object(runner,'bound',lambda *a:None),patch.object(runner.subprocess,'Popen',lambda *a,**k:(_ for _ in ()).throw(AssertionError('nochild'))):must(lambda:runner.supervise(types.SimpleNamespace()))
 assert marker.read_bytes()==b'unchanged' and len(list(Path(z).iterdir()))==1
cases.append('existing_verifier_OUT_not_overwritten_or_child_launched')
def fresh_supervisor():
 import subprocess,os
 real=subprocess.Popen
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();out=root/'fresh';q={'output':str(out)}
  def launch(argv,**kwargs):
   if argv[0]=='/bin/ps':return real(argv,**kwargs)
   script="import pathlib,json; p=pathlib.Path("+repr(str(out))+" )/'result.json'; p.write_text(json.dumps({'status':'COMPLETE_INDEPENDENT_STORED_HANSARD_DIAGNOSTIC_VERIFICATION_NO_ADMISSION'}))"
   return real([sys.executable,'-c',script],**kwargs)
  with patch.object(runner,'verify',lambda a:q),patch.object(runner,'bound',lambda *a:None),patch.object(runner.producer,'ROOT',root),patch.object(runner.producer,'FREE',0),patch.object(runner.subprocess,'Popen',launch):
   code=runner.supervise(types.SimpleNamespace(profile_sha256='p',code_pins_sha256='c',binding='b',binding_sha256='d'))
  assert code==0;sup=json.loads((out/'supervisor.json').read_text());assert sup['worker_reaped'] and sup['worker_exit_code']==0 and sup['status']=='COMPLETE_STORED_METADATA_VERIFICATION'
fresh_supervisor();cases.append('actual_fresh_output_supervisor_child_complete_and_reaped')
print(json.dumps({'status':'PASS_SYNTHETIC_STORED_METADATA_ONLY','controls':len(cases),'cases':cases,'Hansard_source_body_reads':0,'classifier_tokenizer_operations':0},indent=2))
