"""Synthetic complete repaired producer→independent verifier, no retained data."""
import sys,json,sqlite3,tempfile,gzip,hashlib,zlib,copy,types,time,signal,os
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import runner,core
P=HERE.parent/'pressbooks-full-repaired-filter-preparation-v1';sys.path.insert(0,str(P));import engine,inventory,select_core,bounded_policy
N=[]
def must(fn):
 try:fn()
 except Exception:return
 raise AssertionError('expected refusal')
with tempfile.TemporaryDirectory() as z:
 d=Path(z).resolve();out=d/'out';out.mkdir();frame=sqlite3.connect(d/'frame');frame.executescript(inventory.SCHEMA)
 family=sqlite3.connect(d/'family');family.execute('CREATE TABLE rows(source_id INTEGER,ordinal INTEGER,line_offset INTEGER,line_bytes INTEGER,ends_LF INTEGER,line_SHA256 BLOB,text_SHA256 BLOB,text_UTF8_bytes INTEGER,existing_flags INTEGER,identity_holds INTEGER,lead_status INTEGER,lead_root_id INTEGER,PRIMARY KEY(source_id,ordinal))')
 tokens=sqlite3.connect(d/'tokens');tokens.execute('CREATE TABLE docs(source INTEGER,source_ordinal INTEGER,ID_SHA256 BLOB,characters INTEGER,text_SHA256 BLOB,line_SHA256 BLOB,UTF8_bytes INTEGER,content_tokens INTEGER,language_pass INTEGER,source_flags INTEGER,explicit_hold_flags INTEGER,normalized_SHA256 BLOB,normalized_words INTEGER,PRIMARY KEY(source,source_ordinal))')
 texts=['Clean explanatory prose.','Known source-specific hold.','Knowledge Check','Use Figure 2 to compare ages.','Licensed under CC BY NC SA 4.0.','A chronology concern pending.','A prior component lead pending.','Previously reviewed clean prose.','Language failure.','[latex]P(0']
 parts=[];offset=0;linehash=hashlib.sha256();hashes=[]
 for o,index in enumerate([*range(10),0,1],1):
  text=texts[index];url=f'https://example.pressbooks.pub/book/chapter/u{o}/';obj={'id':url,'text':text,'source':'pressbooks','added':'2024-01-01T00:00:00','created':'01-01-2024','metadata':{'license':'CC BY https://creativecommons.org/licenses/by/4.0/','url':url,'book_url':'https://example.pressbooks.pub/book/','title':'Book','author':'Author','institution':'Example','subject':'Instruction'}};raw=(json.dumps(obj)+'\n').encode();line=hashlib.sha256(raw).digest();r,_=inventory.row(o,offset,len(raw),True,line,raw);assert r[5]==0;frame.execute('INSERT INTO records VALUES('+','.join('?'*21)+')',r);h=r[17];hashes.append(h)
  family.execute('INSERT INTO rows VALUES('+','.join('?'*12)+')',(1,o,offset,len(raw),1,line,h,r[18],0,0,2 if o==11 else 1,None));tokens.execute('INSERT INTO docs VALUES('+','.join('?'*13)+')',(1,o,hashlib.sha256(url.encode()).digest(),len(text),h,line,r[18],min(20+index,r[18]),int(index!=8),0,0,h,len(text.split())));parts.append(raw);linehash.update(core.transcript([o,offset,len(raw),1,line.hex()]));offset+=len(raw)
 for db in [frame,family,tokens]:db.commit();db.close()
 rawpath=d/'source.gz';rawpath.write_bytes(gzip.compress(b''.join(parts)))
 def binding(path):s=path.stat();return {'path':str(path),'stat':[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]}
 sb=binding(rawpath)|{'bytes':rawpath.stat().st_size,'SHA256':hashlib.sha256(rawpath.read_bytes()).hexdigest()};fb=binding(d/'frame')|{'rows':12,'ordered_line_locator_SHA256':linehash.hexdigest()}
 targets=[{'text_SHA256':hashes[1].hex(),'hold_roles':['KNOWN_QUALITY'],'pending_roles':[],'evidence':[{'review':'synthetic'}]},{'text_SHA256':hashes[5].hex(),'hold_roles':[],'pending_roles':['SOURCE_SPECIFIC_SUSPECTED_CHRONOLOGY'],'evidence':[]},{'text_SHA256':hashes[6].hex(),'hold_roles':[],'pending_roles':['COMPONENT_LEAD'],'evidence':[]}]
 p={'sources':[{'source_id':1,'raw':sb,'frame':fb,'known_holds':[]}],'family_frame':binding(d/'family'),'token_frame':binding(d/'tokens'),'known_hold_SHA256':[hashes[1].hex()],'fresh_exclusion_SHA256':[hashes[1].hex(),hashes[7].hex()],'overlay_targets':targets,'expected':{'raw_rows':12,'distinct_textSHA':10},'limits':{'DB_bytes':600000000,'journal_bytes':64000000,'all_events':5000000}}
 r=engine.run(p,out,lambda *a:None);candidate=sqlite3.connect(out/'candidate.sqlite');frames={1:core.dbopen(d/'frame')};fam=core.dbopen(d/'family');tok=core.dbopen(d/'tokens');v=core.verify(candidate,frames,fam,tok,r,p,lambda:None);assert v['raw_rows']==12 and v['distinct_textSHA']==10 and v['sampling_performed']is False;N.append('full repaired producer and independent verifier actual12rows10receipts allbuckets')
 assert v['disjoint_buckets']['COMPONENT_QUEUE']['distinct_raw_textSHA']==2 and v['disjoint_buckets']['SPECIFIC_FACTUAL_PENDING_QUEUE']['distinct_raw_textSHA']==1;N.append('component notice queue and priorcomponentbit8 are separate from factualbit4')
 for name,sql in [('source_provenance',"update sources set path='wrong'"),('knownrole',"update known_roles set role='wrong'"),('candidate','update texts set candidate=1 where generic_mask!=0'),('queue','update texts set queue_mask=0 where queue_mask!=0'),('fresh','update texts set fresh_population=1 where prior_reviewed_or_held=1'),('flags','update texts set source_flags=64'),('firstidentity','update texts set first_ordinal=99'),('occurrences','update texts set occurrences=occurrences+1'),('mask','update texts set generic_mask=7'),('knownhold','update texts set explicit_known_hold=0 where explicit_known_hold=1'),('locator','update occurrences set line_offset=line_offset+1 where ordinal=12')]:
  candidate.execute('savepoint x');candidate.execute(sql);must(lambda:core.verify(candidate,frames,fam,tok,r,p,lambda:None));candidate.execute('rollback to x');candidate.execute('release x');N.append('refuses_'+name)
 for key in ['all_policy_events','max_events_per_text','max_lossless_policy_JSON_bytes','overlay_target_SHA','freshness_exclusion_SHA']:
  bad=copy.deepcopy(r);bad[key]+=1;must(lambda:core.verify(candidate,frames,fam,tok,bad,p,lambda:None));N.append('refuses_summary_'+key)
 for collection in ['disjoint_buckets','populations_overlapping_axes']:
  bad=copy.deepcopy(r);next(iter(bad[collection].values()))['M1_content_tokens']+=1;must(lambda:core.verify(candidate,frames,fam,tok,bad,p,lambda:None));N.append('refuses_'+collection)
 row=candidate.execute('select * from receipts order by text_SHA256 limit 1').fetchone();st=candidate.execute('select UTF8_bytes,events,event_upper_bound,receipt_JSON_bytes,generic_mask,first_source,first_ordinal from texts where text_SHA256=?',(row[0],)).fetchone();tr=tok.execute('select characters,line_SHA256 from docs where source=? and source_ordinal=?',(st[5],st[6])).fetchone()
 def unpack(rr):return core.receipt(rr,row[0],st[0],tr[0],st[5],st[6],tr[1],(st[4],st[1],st[2],st[3]))
 for name,blob in [('trailing',row[2]+b'x'),('concat',row[2]+zlib.compress(b'{}')),('cap',zlib.compress(b'x'*3000001))]:must(lambda blob=blob:unpack((row[0],row[1],blob,hashlib.sha256(blob).digest(),row[4])));N.append('bounded_receipt_'+name)
 for path in [d/'frame',d/'family',d/'tokens']:
  key='frame' if path.name=='frame' else 'family_frame' if path.name=='family' else 'token_frame'
  item=p['sources'][0]['frame'] if key=='frame' else p[key];item['inherited_SHA256']=hashlib.sha256(path.read_bytes()).hexdigest()
 # Actual successful worker+actualcore through all postflight; gates alone mocked.
 (out/'ownership.json').write_text('{}');(out/'supervisor.json').write_text('{}');rr=copy.deepcopy(r);rr['artifacts']={x.name:{'bytes':x.stat().st_size,'SHA256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in out.iterdir() if x.name not in ['result.json','supervisor.json']};(out/'result.json').write_text(json.dumps(rr));bb={'files':{x.name:{'stat':runner.ident(x),'SHA256':hashlib.sha256(x.read_bytes()).hexdigest()} for x in out.iterdir()}};ss={'all_output_bytes':sum(x['stat'][2] for x in bb['files'].values())};dest=d/'verified';dest.mkdir()
 for name,size in runner.SLOTS.items():(dest/name).write_bytes(b' '*size)
 start=time.monotonic();a=types.SimpleNamespace(start=start,supervisor_pid=os.getppid(),profile_sha256='p',code_pins_sha256='c',binding_sha256='b');(dest/'ownership.json').write_text(json.dumps({'supervisor_PID':a.supervisor_pid,'worker_PID':os.getpid(),'shared_start':start,'profile_SHA256':'p','codepins_SHA256':'c'}));vp={'output':str(dest),'producer_output':str(out),'producer_profile_SHA256':'pp','producer_codepins_SHA256':'cc'}
 with patch.object(runner,'verify',lambda a:vp),patch.object(runner,'bound',lambda *a:(bb,rr,ss)),patch.object(runner.producer,'verify',lambda a:p),patch.object(runner.producer,'ROOT',d),patch.object(runner.producer,'FREE',0):runner.worker(a)
 verified=json.loads((dest/'result.json').read_text());assert verified['status']=='COMPLETE_INDEPENDENT_STORED_PB_REPAIRED_BUCKET_VERIFICATION_NO_ADMISSION' and verified['raw_rows']==12 and verified['sampling_performed']is False;N.append('actual_worker_actualcore_FDpostflight_terminal_success_no_core_mock')
 candidate.close();fam.close();tok.close();frames[1].close()
# Parent incomplete/reaped gate refuses before candidateSQL inventory.
with tempfile.TemporaryDirectory() as t:
 pth=Path(t)/'binding';pth.write_text('{"status":"PENDING"}');must(lambda:runner.bound(types.SimpleNamespace(binding=str(pth),binding_sha256=runner.sha(pth)),{}));N.append('pending_terminal_binding_refused')
old=runner.START;runner.START=time.monotonic()-1194.98
try:
 with patch.object(runner,'verify',lambda a:time.sleep(.1)):must(lambda:runner.supervise(types.SimpleNamespace()))
 N.append('actual_early_preflight_deadline')
finally:runner.START=old;signal.setitimer(signal.ITIMER_REAL,0)
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY_REPAIRED_ALL_METADATA_NO_DRAW','controls':len(N),'checks':N,'retained_source_or_liveSQL_reads':0},indent=2))
