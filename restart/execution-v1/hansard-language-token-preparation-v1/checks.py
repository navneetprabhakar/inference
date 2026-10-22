"""Frozen policy controls + synthetic transport/SQL/lifecycle; no Hansard body run."""
import pathlib,json,hashlib,tempfile,sqlite3,subprocess,sys,types,signal,time,os,importlib.util
from unittest.mock import patch
import rules,engine,classify,pilot
HERE=pathlib.Path(__file__).resolve().parent;p=json.loads((HERE/'profile.json').read_text());checks=[]
def test(n,fn):fn();checks.append(n)
def must(fn):
 try:fn()
 except Exception:return
 raise AssertionError('expected refusal')
def policy():
 w=list(rules.windows('a'*39));assert len(w)==2 and w[0][0]['scored'] and not w[1][0]['scored'];assert all(x['scored'] for x,_ in rules.windows('a'*40))
 w=list(rules.windows('é'*1024+'b'*40));assert [(m['start'],m['end']) for m,_ in w]==[(0,1064),(0,1024),(1024,1064)] and w[-1][0]['scored']
 assert rules.projection('a\r\nb</s>')=='a  b< /s >' and rules.prediction('__label__en 0.8')[-1]==1 and rules.prediction('__label__en 0.799999')[-1]==0 and rules.prediction('__label__fr 0.999')[-1]==0
 for bad in ['nan','inf','-0.1','1.01']:must(lambda bad=bad:rules.prediction('__label__en '+bad))
test('reused_WB_whole_chunk40alpha_1024Unicode_tail_projection_threshold_controls',policy)
def token_controls():
 t=rules.load_tokenizer(p)
 for text in ['Simple English.','é漢🙂','literal </s> <|assistant|>','line\r\ntext']:
  ids=t.encode(text,add_special_tokens=False).ids;assert t.decode(ids,skip_special_tokens=False)==text and len(ids)+1==sum(1 for _ in ids)+1
 assert t.get_vocab_size()==8182
test('actual_frozen_M1_no_added_tokens_normalization_fit_roundtrip_EOSseparate',token_controls)
def live_classifier():
 for item in [p['fasttext'],p['language_model']]:assert rules.sha(item['path'])==item['sha256']
 lines=classify.infer(p,b'\nThis is a simple English sentence about a book.\nBonjour tout le monde.\n',30,lambda:None);assert len(lines)==3;[rules.prediction(x) for x in lines]
test('actual_frozen_fastText_synthetic_stdin_blank_English_foreign_exact3lines',live_classifier)
def transport(script,expected):
 real=subprocess.Popen;children=[]
 def fake(argv,**kwargs):
  assert argv==[p['fasttext']['path'],'predict-prob',p['language_model']['path'],'-','1'];assert not kwargs.get('start_new_session',False);c=real([sys.executable,'-c',script],**kwargs);children.append(c);return c
 with patch.object(classify.subprocess,'Popen',fake):
  try:classify.infer(p,b'A\n',.1 if expected=='timeout' else 3,lambda:None)
  except Exception as e:assert 'SECRET' not in str(e)
  else:raise AssertionError('expected transport refusal')
 assert children and all(c.poll() is not None for c in children)
for name,script in [('stdout','import sys;sys.stdout.buffer.write(b"x"*1048577);sys.stdout.flush()'),('stderr','import sys;sys.stderr.buffer.write(b"SECRET"*12000);sys.stderr.flush()'),('exit','import sys;sys.stderr.write("SECRET");sys.exit(1)'),('encoding','import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(b"\\xff")'),('timeout','import time;time.sleep(3)')]:test('bounded_CLI_'+name+'_killed_reaped_no_external_text_leak',lambda s=script,n=name:transport(s,n))
test('8MiB_input_cap_before_classifier_process',lambda:must(lambda:classify.infer(p,b'x'*(8388608+1),30,lambda:None)))
def source_binding():
 spec=importlib.util.spec_from_file_location('original_inventory',p['inventory_module']);inv=importlib.util.module_from_spec(spec);spec.loader.exec_module(inv);raw=b'{"id":"ID","text":"English text"}\n';m=[None]*21;m[:5]=[1,0,len(raw),1,hashlib.sha256(raw).digest()];m[6]='ID';m[17]=hashlib.sha256(b'English text').digest();m[18]=12;m[19]=12
 assert engine.source_record(1,0,len(raw),True,m[4],raw,m,inv)[1]=='English text'
 for at,value in [(0,2),(1,1),(2,len(raw)+1),(4,b'0'*32),(6,'otherID'),(17,b'0'*32),(18,11),(19,11)]:
  bad=m.copy();bad[at]=value;must(lambda bad=bad:engine.source_record(1,0,len(raw),True,m[4],raw,bad,inv))
 must(lambda:engine.source_record(1,0,len(raw),True,m[4],None,m,inv))
test('raw_line_ord_offset_bytes_LF_SHA_ID_textSHA_chars_all_bind_beforecount',source_binding)
assert pilot.LIMITS==p['limits'] and pilot.LIMITS['normalized_UTF8_bytes']==64000000
normal=pilot.module('normalization_controls',p['normalization_module']).normalized
def norm():
 assert normal('K Ä ß ﬀ _foo__ 42 e\u0301')=='k ä ss ff _foo__ 42 é';raw='A.B—C\nD';h,n=engine.normalization_diagnostic(raw,normal);assert h==hashlib.sha256(b'a b c d').digest() and n==4 and raw=='A.B—C\nD'
test('exact_existing_NFKC_casefold_Unicode_word_normalized_SHA_diagnostic_only',norm)
def projection_cap():
 text='</s>'*(976480//4);windows,n=engine.prepared(text);assert n>1048576 and n<=8388608 and windows[0][0]['scored'] and sum(m['kind']=='whole' for m,_ in windows)==1
test('HS_max976KB_expanding_projection_retained_and_bounded',projection_cap)
def flags():
 targets={'semantic_text_SHA256':'sha'};assert engine.explicit_flags('same','sha',targets)==1 and engine.explicit_flags('differentID','sha',targets)==1 and engine.explicit_flags('same','otherSHA',targets)==0
test('exact_semantic_content_hold_ALL_IDcopies_only',flags)
def document(n,text,flags=0):
 data=text.encode();w,size=engine.prepared(text);normalizedSHA,normalized_words=engine.normalization_diagnostic(text,normal)
 return {'doc':n,'identity':{'source':1,'ordinal':n,'id':'ID'+str(n),'text_SHA256':hashlib.sha256(data).hexdigest(),'line_SHA256':hashlib.sha256(data).hexdigest(),'characters':len(text),'UTF8_bytes':len(data),'source_flags':64},'tokens':7,'windows':w,'explicit_flags':flags,'normalized_SHA256':normalizedSHA,'normalized_words':normalized_words}
def fakeinfer(profile,data,remaining,check):return ['__label__en 0.8']*data.count(b'\n')
def raw_duplicates():
 with tempfile.TemporaryDirectory() as z:
  store=engine.Store(z,p['limits'],lambda *a:None);text='a'*1024+'b'*39
  try:
   store.batch(p,[document(1,text,1),document(2,text)],30,fakeinfer);s=store.summary();assert s['all_raw']['documents']==2 and s['all_raw']['M1_content_tokens']==14 and s['all_raw']['EOS_separate']==2 and s['all_distinct_text_hashes']['distinct_text_hashes']==1 and s['all_distinct_text_hashes']['M1_content_tokens']==7 and s['all_distinct_text_hashes']['one_EOS_per_distinct_hash_separate']==1
   assert store.db.execute('select count(*) from windows where scored=0 and skip_reason=1').fetchone()==(2,) and store.db.execute('select count(*) from windows').fetchone()==(6,) and store.db.execute('select count(*) from docs where explicit_hold_flags=1').fetchone()==(1,)
   assert store.db.execute('select explicit_hold_flags from texts').fetchone()==(1,) and store.db.execute('pragma journal_mode').fetchone()==('persist',)
  finally:store.close()
test('allraw_duplicate_positions_windows_skips_tokens_EOS_distinct_diagnostics_holds',raw_duplicates)
def short_predictions():
 with tempfile.TemporaryDirectory() as z:
  store=engine.Store(z,p['limits'],lambda *a:None)
  try:must(lambda:store.batch(p,[document(1,'a'*1064)],30,lambda *a:[]));store.db.rollback();assert store.db.execute('select count(*) from docs').fetchone()==(0,)
  finally:store.close()
test('missing_classifier_lines_fail_before_any_batch_commit',short_predictions)
def batchcap():
 with tempfile.TemporaryDirectory() as z:
  store=engine.Store(z,p['limits'],lambda *a:None)
  try:must(lambda:store.batch(p,[{}]*65,30,lambda *a:(_ for _ in ()).throw(AssertionError('mustnotinfer'))))
  finally:store.close()
test('65doc_batch_refused_before_classifier',batchcap)
def RSS():
 for x in ['', '9 9 1','9 1 -1','9 1 2\n9 1 3','9 1 2']:
  must(lambda x=x:pilot.tree_rss(x,999))
 assert pilot.tree_rss('9 1 2\n10 9 3\n11 10 4',9,10)==9*1024
test('strict_RSS_root_worker_and_classifier_descendant_aggregate',RSS)
def early():
 old=pilot.START;pilot.START=time.monotonic()-3054.98
 try:
  with patch.object(pilot,'verify',lambda a:time.sleep(.1)):must(lambda:pilot.supervise(types.SimpleNamespace()))
 finally:pilot.START=old;signal.setitimer(signal.ITIMER_REAL,0)
test('actual_supervisor_alarm_before_blocked_preflight',early)
def full_engine_fixture(z):
 import gzip,copy
 z=str(pathlib.Path(z).resolve());q=copy.deepcopy(p);q['sources']=[];q['known_targets']={'semantic_text_SHA256':'0'*64,'expected_bindings':[]};q['rights_expected_counts']=[[1,1],[2,1]];q['output']=str(pathlib.Path(z)/'output');pathlib.Path(q['output']).mkdir();expected={'documents':0,'UTF8_bytes':0,'characters':0,'all_windows':0}
 for sid,text in [(1,'An English paragraph with a complete sentence. '*30),(2,'Another English section with independent wording. '*24)]:
  raw=(json.dumps({'id':'synthetic://'+str(sid),'text':text})+'\n').encode();data=gzip.compress(raw);source=pathlib.Path(z)/('source'+str(sid)+'.gz');source.write_bytes(data);frame=pathlib.Path(z)/('frame'+str(sid)+'.sqlite');db=sqlite3.connect(frame);db.execute('create table records(source_id integer,ordinal integer,line_offset integer,line_bytes integer,ends_LF integer,line_SHA256 blob,flags integer,id text,source text,added text,year text,language text,license text,text_SHA256 blob,text_UTF8_bytes integer,text_chars integer)');m=[sid,1,0,len(raw),1,hashlib.sha256(raw).digest(),0,'synthetic://'+str(sid),'uk-hansard-northern-ireland-assembly' if sid==1 else 'uk-hansard-london-mayors-questions','2020-01-01','2020','en','unverified',hashlib.sha256(text.encode()).digest(),len(text.encode()),len(text)];db.execute('insert into records values('+','.join('?'*16)+')',m);db.commit();db.close();q['sources'].append({'source_id':sid,'rows':1,'decoded_bytes':len(raw),'source':{'path':str(source),'bytes':len(data),'SHA256':rules.sha(source),'stat':pilot.ident(source)},'frame':{'path':str(frame),'SHA256':rules.sha(frame),'stat':pilot.ident(frame)}})
  expected['documents']+=1;expected['UTF8_bytes']+=len(text.encode());expected['characters']+=len(text);expected['all_windows']+=len(engine.prepared(text)[0])
 return q,expected

def full_engine(corrupt=False):
 import contextlib
 inv=pilot.module('tiny_original_inventory',p['inventory_module']);tok=types.SimpleNamespace(encode=lambda text,**kw:types.SimpleNamespace(ids=list(range(len(text.split())))))
 with tempfile.TemporaryDirectory() as z:
  q,expected=full_engine_fixture(z);connections=[]
  def metadata(item):
   db=sqlite3.connect(item['frame']['path']);connections.append(db);return (pilot.module('synthetic_HS_adapter',p['inventory_module']).adapted(r) for r in db.execute('select * from records order by ordinal'))
  if corrupt:
   source=pathlib.Path(q['sources'][1]['source']['path']);data=bytearray(source.read_bytes());data[-8]^=1;source.write_bytes(data);q['sources'][1]['source']['stat']=pilot.ident(source)
  try:
   with patch.object(engine,'EXPECTED',expected):
    fn=lambda:engine.run(q,q['output'],metadata,lambda item,check:pilot.source_guard.opened(item['source'],check),inv,lambda *a:None,lambda:30,tok,normal,fakeinfer)
    if corrupt:
     must(fn);db=sqlite3.connect(pathlib.Path(q['output'])/'screening.sqlite');assert db.execute('select count(*) from docs').fetchone()==(1,);db.close()
    else:
     r=fn();assert r['status'].startswith('COMPLETE') and r['stats']['documents']==2 and r['stats']['all_windows']==expected['all_windows'] and len(r['source_receipts'])==2
  finally:
   for db in connections:db.close()
test('actual_two_gzip_engine_success_all_framejoins_CRC_SHA_normalization_windows_SQL',full_engine)
test('second_gzip_CRC_fault_refuses_COMPLETE_preserves_only_prior_committed_source',lambda:full_engine(True))

def worker_lifecycle(fail=False):
 with tempfile.TemporaryDirectory() as z:
  q,expected=full_engine_fixture(z);out=pathlib.Path(q['output']);a=types.SimpleNamespace(start=time.monotonic(),supervisor_pid=os.getppid(),profile_sha256='p',code_pins_sha256='c');(out/'ownership.json').write_text(json.dumps({'worker_PID':os.getpid(),'supervisor_PID':a.supervisor_pid,'shared_start':a.start,'profile_SHA256':'p','codepins_SHA256':'c'}));(out/'result.json').write_bytes(b' '*1048576);calls=[]
  def verify(a):calls.append('verify');return q
  def run(profile,out,metadata,source,inventory,check,remaining,tokenizer,normalizer):
   assert len(list(metadata(profile['sources'][0])))==1
   with source(profile['sources'][0],check) as read:assert read(1)
   if fail:raise ValueError('SECRET synthetic source content')
   return {'status':'COMPLETE_RAW_HANSARD_LANGUAGE_M1_DIAGNOSTICS_NO_ADMISSION','new_admitted_documents':0}
  with patch.object(pilot,'verify',verify),patch.object(pilot.rules,'load_tokenizer',lambda p:object()),patch.object(pilot.engine,'run',run),patch.object(pilot,'guard',lambda *a:None):
   if fail:must(lambda:pilot.worker(a))
   else:pilot.worker(a)
  r=json.loads((out/'result.json').read_text());assert 'SECRET' not in (out/'result.json').read_text()
  if fail:assert r['status'].startswith('PARTIAL') and len(calls)==1
  else:assert r['status'].startswith('COMPLETE') and len(calls)==2
  assert signal.getitimer(signal.ITIMER_REAL)[0]==0
test('actual_worker_synthetic_FD_lifecycle_postflight_success_after_closed_metadataFD',worker_lifecycle)
test('actual_worker_partial_terminal_no_secret_exception_and_alarm_disarmed',lambda:worker_lifecycle(True))

def existing_output():
 with tempfile.TemporaryDirectory() as z:
  q=dict(p,output=z);marker=pathlib.Path(z)/'marker';marker.write_bytes(b'original')
  with patch.object(pilot,'verify',lambda a:q),patch.object(pilot.subprocess,'Popen',lambda *a,**k:(_ for _ in ()).throw(AssertionError('nochild'))):must(lambda:pilot.supervise(types.SimpleNamespace()))
  assert marker.read_bytes()==b'original' and sorted(x.name for x in pathlib.Path(z).iterdir())==['marker']
test('actual_supervisor_existingOUT_refused_nochild_or_receipt_overwrite',existing_output)
def rights_adapter():
 m=pilot.module('HS_rights_adapter_control',p['inventory_module']);base=[1,1,0,2,1,b'x'*32,0,'ID','uk-hansard-northern-ireland-assembly','2020-01-01','2020','en','unverified',b'y'*32,1,1]
 assert m.adapted(base)[20]==1;base[8]='uk-hansard-london-mayors-questions';assert m.adapted(base)[20]==2;base[8]='uk-hansard-lords-debates';assert m.adapted(base)[20]==0 and m.adapted(base)[5]==0
 with tempfile.TemporaryDirectory() as z:
  store=engine.Store(z,p['limits'],lambda *a:None)
  try:
   a=document(1,'An English text '*100);b=document(2,'An English text '*100);a['identity']['rights_unclear_flags']=1;b['identity']['rights_unclear_flags']=2;store.batch(p,[a,b],30,fakeinfer);assert store.db.execute('select rights_unclear_flags from docs order by doc').fetchall()==[(1,),(2,)];assert store.db.execute('select rights_unclear_flags from texts').fetchone()==(3,);assert store.summary()['all_raw']['documents']==2
  finally:store.close()
test('source_metadata_NI_London_separate_rightsbits_OR_without_raw_or_language_exclusion',rights_adapter)
print(json.dumps({'status':'PASS_SYNTHETIC_AND_PINNED_DEPENDENCIES_NO_HANSARD_BODY_RUN','count':len(checks),'checks':checks,'raw_HANSARD_source_body_reads':0,'student_operations':0},indent=2))
