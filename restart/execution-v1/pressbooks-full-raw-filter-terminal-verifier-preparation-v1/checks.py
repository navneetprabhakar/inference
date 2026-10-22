"""Independent temporary synthetic sources/SQLite; no retained body run."""
import sys,json,sqlite3,tempfile,gzip,hashlib,zlib,copy,types,time,signal
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import runner,core
P=HERE.parent/'pressbooks-full-raw-filter-preparation-v1';sys.path.insert(0,str(P))
import engine,inventory,select_core,bounded_policy
N=[]
def must(fn):
 try:fn()
 except Exception:return
 raise AssertionError('expected refusal')
with tempfile.TemporaryDirectory() as z:
 d=Path(z).resolve();out=d/'out';out.mkdir();f=sqlite3.connect(d/'frame');f.executescript(inventory.SCHEMA)
 family=sqlite3.connect(d/'family');family.execute('CREATE TABLE rows(source_id INTEGER,ordinal INTEGER,line_offset INTEGER,line_bytes INTEGER,ends_LF INTEGER,line_SHA256 BLOB,text_SHA256 BLOB,text_UTF8_bytes INTEGER,existing_flags INTEGER,identity_holds INTEGER,lead_status INTEGER,lead_root_id INTEGER,id_id INTEGER,url_id INTEGER,book_url_id INTEGER)');family.execute('CREATE TABLE strings(string_id INTEGER PRIMARY KEY,value TEXT)');family.execute('INSERT INTO strings VALUES(1,"SAME_BOOK_LEAD_NOT_CLEARED")')
 tok=sqlite3.connect(d/'tokens');tok.execute('CREATE TABLE docs(source INTEGER,source_ordinal INTEGER,ID_SHA256 BLOB,characters INTEGER,text_SHA256 BLOB,line_SHA256 BLOB,UTF8_bytes INTEGER,content_tokens INTEGER,language_pass INTEGER,source_flags INTEGER,explicit_hold_flags INTEGER,normalized_SHA256 BLOB,normalized_words INTEGER)')
 parts=[];offset=0;lh=hashlib.sha256();hashes=[]
 # 200 fresh + held + reviewed survivor + language failure, followed by two aliases.
 texts=[f'A complete synthetic explanatory unit number {i}.' for i in range(203)];texts += [texts[200],texts[0]]
 for i,text in enumerate(texts,1):
  url=f'https://example.pressbooks.pub/book/chapter/u{i}/';obj={'id':url,'text':text,'source':'pressbooks','added':'2024-01-01T00:00:00','created':'01-01-2024','metadata':{'license':'CC BY https://creativecommons.org/licenses/by/4.0/','url':url,'book_url':'https://example.pressbooks.pub/book/','title':'Book','author':'Author','institution':'Example','subject':'Instruction'}};raw=(json.dumps(obj)+'\n').encode();hh=hashlib.sha256(raw).digest();r,_=inventory.row(i,offset,len(raw),True,hh,raw);assert r[5]==0;f.execute('INSERT INTO records VALUES('+','.join('?'*21)+')',r);h=r[17];hashes.append(h)
  family.execute('INSERT INTO rows VALUES('+','.join('?'*15)+')',(1,i,offset,len(raw),1,hh,h,len(text.encode()),0,0,2 if i==205 else 1,1,None,None,None))
  token=0 if i in [1,205] else min(25,7+texts.index(text));lang=int(i!=203);tok.execute('INSERT INTO docs VALUES('+','.join('?'*13)+')',(1,i,hashlib.sha256(url.encode()).digest(),len(text),h,hh,len(text.encode()),token,lang,0,0,h,8));parts.append(raw);lh.update(select_core.transcript([i,offset,len(raw),1,hh.hex()]));offset+=len(raw)
 for db in [f,family,tok]:db.commit();db.close()
 source=d/'s.gz';source.write_bytes(gzip.compress(b''.join(parts)))
 def binding(p):
  s=p.stat();return {'path':str(p),'stat':[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]}
 b=binding(source)|{'bytes':source.stat().st_size,'SHA256':hashlib.sha256(source.read_bytes()).hexdigest()};frame=binding(d/'frame')|{'rows':205,'ordered_line_locator_SHA256':lh.hexdigest()}
 p={'sources':[{'source_id':1,'raw':b,'frame':frame,'known_holds':[]}],'family_frame':binding(d/'family'),'token_frame':binding(d/'tokens'),'known_hold_SHA256':[hashes[200].hex()],'fresh_exclusion_SHA256':[hashes[200].hex(),hashes[201].hex()],'expected':{'raw_rows':205,'distinct_textSHA':203},'limits':{'DB_bytes':600000000,'journal_bytes':64000000,'all_events':5000000,'selection_bytes':8000000},'sampling_seed':'independent-rawSHA-test'}
 calls=[];original=bounded_policy.evaluate
 def once(text):calls.append(hashlib.sha256(text.encode()).digest());return original(text)
 with patch.object(bounded_policy,'evaluate',once):result=engine.run(p,out,lambda *a:None)
 assert len(calls)==203 and len(set(calls))==203;N.append('205 raw rows/203 distinct: policy executes exactly once per rawSHA; all occurrences reconciled')
 db=sqlite3.connect(out/'candidate.sqlite');known=db.execute('SELECT occurrences,explicit_known_hold,candidate,fresh_population FROM texts WHERE text_SHA256=?',(hashes[200],)).fetchone();assert known==(2,1,0,0);N.append('known exact-content hold covers different-ID duplicate and both occurrences')
 prior=db.execute('SELECT candidate,fresh_population FROM texts WHERE text_SHA256=?',(hashes[201],)).fetchone();assert prior==(1,0);N.append('reviewed readable survivor stays candidate but is excluded from fresh population')
 alias=db.execute('SELECT occurrences,family_uncertainty,candidate FROM texts WHERE text_SHA256=?',(hashes[0],)).fetchone();assert alias==(2,1,1);N.append('duplicate family uncertainty OR retained without silent book-family exclusion')
 assert result['populations']['full_filtered_candidate']['distinct_raw_textSHA']==201 and result['populations']['fresh_review_population']['distinct_raw_textSHA']==200
 sel=json.loads((out/'fresh-review-selection.json').read_text());draws=sel['draws'];assert len(draws)==400
 assert all(x['text_SHA256'] not in {hashes[200].hex(),hashes[201].hex(),hashes[202].hex()} for x in draws)
 uni=[x for x in draws if x['mode'].startswith('UNIFORM')];wei=[x for x in draws if x['mode'].startswith('TOKEN')];assert len({x['text_SHA256'] for x in uni})==200 and hashes[0].hex() in {x['text_SHA256'] for x in uni} and all(x['M1_content_tokens']>0 for x in wei)
 assert len(wei)==200 and sel['weighted_repeat_draws']==200-len({x['text_SHA256'] for x in wei});N.append('exact400 draws preserve uniform zero-token eligibility, positive weighted eligibility, repetitions and exclusions')
 for h,jsha,packed,psha,codec in db.execute('SELECT * FROM receipts'):
  raw=zlib.decompress(packed);assert hashlib.sha256(raw).digest()==jsha and hashlib.sha256(packed).digest()==psha;record=json.loads(raw);assert record['source_SHA256']==h.hex() and 'text' not in record
 db.close();N.append('all203 compressed finding receipts hash/codec source-bind without text payload copies')
 candidate=sqlite3.connect(out/'candidate.sqlite');frames={1:core.dbopen(d/'frame')};fd=core.dbopen(d/'family');td=core.dbopen(d/'tokens');good=core.verify(candidate,frames,fd,td,result,p,sel,lambda:None);assert good['raw_rows']==205 and good['sampling']['draws']==400;N.append('independent full stored-output verifier reconciles205 aliases/203receipts/exact400draws')
 for name,sql in [('candidate','update texts set candidate=0 where candidate=1'),('fresh','update texts set fresh_population=1 where prior_reviewed_or_held=1'),('mask','update texts set generic_mask=1 where generic_mask=0'),('occurrences','update texts set occurrences=occurrences+1'),('locator','update occurrences set line_offset=line_offset+1 where ordinal=205'),('knownhold','update texts set explicit_known_hold=0 where explicit_known_hold=1')]:
  candidate.execute('savepoint x');candidate.execute(sql)
  try:core.verify(candidate,frames,fd,td,result,p,sel,lambda:None)
  except ValueError:pass
  else:raise AssertionError('mutation not refused:'+name)
  candidate.execute('rollback to x');candidate.execute('release x');N.append('stored verifier refuses '+name)
 for typ in ['draw_duplicate','token_position','count_summary']:
  badsel=copy.deepcopy(sel);badresult=copy.deepcopy(result)
  if typ=='draw_duplicate':badsel['draws'][0]=copy.deepcopy(badsel['draws'][1])
  elif typ=='token_position':next(x for x in badsel['draws'] if x['mode'].startswith('TOKEN'))['token_position_zero_based']+=1
  else:badresult['populations']['full_filtered_candidate']['M1_content_tokens']+=1
  try:core.verify(candidate,frames,fd,td,badresult,p,badsel,lambda:None)
  except ValueError:pass
  else:raise AssertionError('summary/draw mutation not refused:'+typ)
  N.append('stored verifier refuses '+typ)
 row=candidate.execute('select * from receipts limit1'.replace('limit1','limit 1')).fetchone();stored=candidate.execute('select UTF8_bytes,receipt_JSON_bytes,events,event_upper_bound,generic_mask from texts where text_SHA256=?',(row[0],)).fetchone();chars=td.execute('select characters from docs where text_SHA256=?',(row[0],)).fetchone()[0]
 for label,packed in [('trailing',row[2]+b'x'),('concatenated',row[2]+zlib.compress(b'{}')),('decompressioncap',zlib.compress(b'x'*2000001))]:
  rr=(row[0],row[1],packed,hashlib.sha256(packed).digest(),row[4])
  try:core.receipt(rr,row[0],stored[0],chars,(stored[4],stored[2],stored[3],stored[1]))
  except ValueError:pass
  else:raise AssertionError('bad receipt accepted:'+label)
  N.append('bounded receipt rejects '+label)
 candidate.close();fd.close();td.close();frames[1].close()
 bad=sqlite3.connect(d/'tokens');bad.execute('UPDATE docs SET line_SHA256=? WHERE source_ordinal=205',(b'x'*32,));bad.commit();bad.close();failed=d/'failed';failed.mkdir()
 try:engine.run(p,failed,lambda *a:None)
 except ValueError as e:assert str(e)=='verified_M1_language_doc_join'
 else:raise AssertionError('late duplicate token-line drift not refused')
 assert not(failed/'fresh-review-selection.json').exists();N.append('late alias metadata drift refuses complete selection after prior committed batches')
old=runner.START;runner.START=time.monotonic()-1194.98
try:
 with patch.object(runner,'verify',lambda a:time.sleep(.1)):must(lambda:runner.supervise(types.SimpleNamespace()))
finally:runner.START=old;signal.setitimer(signal.ITIMER_REAL,0)
N.append('actual_supervisor_deadline_before_preflight')
with tempfile.TemporaryDirectory()as z:
 marker=Path(z)/'original';marker.write_bytes(b'unchanged')
 with patch.object(runner,'verify',lambda a:{'output':z}),patch.object(runner,'bound',lambda *a:None),patch.object(runner.subprocess,'Popen',lambda *a,**k:(_ for _ in ()).throw(AssertionError('nochild'))):must(lambda:runner.supervise(types.SimpleNamespace()))
 assert marker.read_bytes()==b'unchanged' and len(list(Path(z).iterdir()))==1
N.append('existing_verifier_OUT_not_overwritten_or_child_launched')
def fresh_supervisor():
 import subprocess,os
 real=subprocess.Popen
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();out=root/'fresh';q={'output':str(out)}
  def launch(argv,**kwargs):
   if argv[0]=='/bin/ps':return real(argv,**kwargs)
   script="import pathlib,json; p=pathlib.Path("+repr(str(out))+" )/'result.json'; p.write_text(json.dumps({'status':'COMPLETE_INDEPENDENT_STORED_PB_FILTER_AND_FRESH400_VERIFICATION_NO_ADMISSION'}))"
   return real([sys.executable,'-c',script],**kwargs)
  with patch.object(runner,'verify',lambda a:q),patch.object(runner,'bound',lambda *a:None),patch.object(runner.producer,'ROOT',root),patch.object(runner.producer,'FREE',0),patch.object(runner.subprocess,'Popen',launch):
   code=runner.supervise(types.SimpleNamespace(profile_sha256='p',code_pins_sha256='c',binding='b',binding_sha256='d'))
  assert code==0;sup=json.loads((out/'supervisor.json').read_text());assert sup['worker_reaped'] and sup['worker_exit_code']==0 and sup['status']=='COMPLETE_STORED_METADATA_VERIFICATION'
fresh_supervisor();N.append('actual_fresh_output_supervisor_child_complete_and_reaped')
print(json.dumps({'status':'PASS_SYNTHETIC_STORED_METADATA_ONLY','controls':len(N),'cases':N,'PB_source_body_reads':0,'classifier_tokenizer_operations':0},indent=2))
