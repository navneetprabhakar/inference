"""Whole-source synthetic production controls; no retained corpus opens."""
import json,hashlib,zlib,sqlite3,gzip,tempfile,copy
from pathlib import Path
import bounded_policy as policy,engine,inventory,select_core
N=0
def ok(x):
 global N;assert x;N+=1
def refusal(fn):
 global N
 try:fn()
 except (ValueError,KeyError,sqlite3.DatabaseError,zlib.error):N+=1;return
 raise AssertionError('refusal expected')
def ident(t):return {'source_id':1,'ordinal':1,'text_SHA256':hashlib.sha256(t.encode()).hexdigest(),'source_JSON_SHA256':'a'*64}
for t,mask,queue in [('Clean prose explains an idea.',0,0),('Knowledge Check',4,1),('Use Figure 2 to compare ages.',0,1),('Licensed under CC BY NC SA 4.0.',0,2)]:
 r=policy.evaluate(t,ident(t));ok(bool(r['mask'])==bool(mask));ok(r['queue_mask']==queue);u=zlib.decompress(r['zlib_bytes']);ok(hashlib.sha256(u).digest()==r['JSON_SHA256']);ok(json.loads(u)['structural']['source_SHA256']==ident(t)['text_SHA256'])
refusal(lambda:policy.evaluate('text',dict(ident('text'),text_SHA256='b'*64)))
refusal(lambda:policy.evaluate('x'*2196001,ident('x'*2196001)))
# Actual whole producer with2completegzip/frames/family/M1 tables and cross-source aliases.
with tempfile.TemporaryDirectory() as z:
 d=Path(z);fam=sqlite3.connect(d/'family.sqlite');fam.execute('CREATE TABLE rows(source_id INTEGER,ordinal INTEGER,line_offset INTEGER,line_bytes INTEGER,ends_LF INTEGER,line_SHA256 BLOB,text_SHA256 BLOB,text_UTF8_bytes INTEGER,existing_flags INTEGER,identity_holds INTEGER,lead_status INTEGER,lead_root_id INTEGER)')
 tok=sqlite3.connect(d/'tokens.sqlite');tok.execute('CREATE TABLE docs(source INTEGER,source_ordinal INTEGER,text_SHA256 BLOB,line_SHA256 BLOB,UTF8_bytes INTEGER,content_tokens INTEGER,language_pass INTEGER,source_flags INTEGER,explicit_hold_flags INTEGER,normalized_SHA256 BLOB,normalized_words INTEGER)')
 texts=['Clean prose explains an idea.','This exact source has a known review hold.','Knowledge Check','Use Figure 2 to compare ages.','Licensed under CC BY NC SA 4.0.','A specific chronology concern is pending.','A previously reviewed clean sentence.','Another intact English paragraph.','Language failure fixture.'];hashes=[hashlib.sha256(t.encode()).hexdigest() for t in texts];sources=[]
 def bind(p):
  s=p.stat();return {'path':str(p.resolve()),'stat':[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]}
 for sid,indices in [(1,list(range(7))),(2,[0,1,4,7,8])]:
  f=sqlite3.connect(d/f'frame{sid}.sqlite');f.executescript(inventory.SCHEMA);parts=[];off=0;lh=hashlib.sha256()
  for ordinal,index in enumerate(indices,1):
   t=texts[index];u=f'https://example.pressbooks.pub/book/chapter/{sid}-{ordinal}/';obj={'id':u,'text':t,'source':'pressbooks','added':'2024-01-01T00:00:00','created':'01-01-2024','metadata':{'license':'CC BY https://creativecommons.org/licenses/by/4.0/','url':u,'book_url':'https://example.pressbooks.pub/book/front-matter/introduction/','title':'Book','author':'Author','institution':'Example','subject':'Instruction'}}
   raw=(json.dumps(obj)+'\n').encode();h=hashlib.sha256(raw).digest();rec,_=inventory.row(ordinal,off,len(raw),True,h,raw);assert rec[5]==0
   f.execute('INSERT INTO records VALUES('+','.join(['?']*21)+')',rec);fam.execute('INSERT INTO rows VALUES('+','.join(['?']*12)+')',(sid,ordinal,off,len(raw),1,h,rec[17],rec[18],0,0,1,None));tok.execute('INSERT INTO docs VALUES('+','.join(['?']*11)+')',(sid,ordinal,rec[17],h,rec[18],20+index,int(index!=8),0,0,rec[17],len(t.split())));lh.update(select_core.transcript([ordinal,off,len(raw),1,h.hex()]));parts.append(raw);off+=len(raw)
  f.commit();f.close();source=d/f'source{sid}.gz';source.write_bytes(gzip.compress(b''.join(parts)));sb=bind(source);sb.update(bytes=source.stat().st_size,SHA256=hashlib.sha256(source.read_bytes()).hexdigest());fb=bind(d/f'frame{sid}.sqlite');fb.update(rows=len(indices),ordered_line_locator_SHA256=lh.hexdigest());sources.append({'source_id':sid,'raw':sb,'frame':fb,'known_holds':[]})
 for x in [fam,tok]:x.commit();x.close()
 targets=[{'text_SHA256':hashes[1],'hold_roles':['KNOWN_QUALITY'],'pending_roles':[],'evidence':[]},{'text_SHA256':hashes[5],'hold_roles':[],'pending_roles':['SOURCE_SPECIFIC_SUSPECTED_CHRONOLOGY'],'evidence':[]}]
 p={'sources':sources,'family_frame':bind(d/'family.sqlite'),'token_frame':bind(d/'tokens.sqlite'),'known_hold_SHA256':[hashes[1]],'fresh_exclusion_SHA256':[hashes[6]],'overlay_targets':targets,'expected':{'raw_rows':12,'distinct_textSHA':9},'limits':{'DB_bytes':600000000,'journal_bytes':64000000,'all_events':5000000}}
 out=d/'success';out.mkdir();r=engine.run(p,out,lambda extra=0:None);ok(r['raw_rows']==12);ok(r['distinct_raw_SHA']==9);ok(r['new_admitted_documents']==0);ok(not any('selection' in f.name for f in out.iterdir()));db=sqlite3.connect(out/'candidate.sqlite');ok(db.execute('PRAGMA integrity_check').fetchone()==('ok',));ok(db.execute('PRAGMA foreign_key_check').fetchone() is None)
 axis=r['populations_overlapping_axes'];ok(axis['known_exact_holds']['raw_occurrences']==2);ok(axis['component_queue']['raw_occurrences']==2);ok(axis['clear_diagnostic_candidate']['distinct_raw_textSHA']==3);ok(axis['clear_unreviewed_frame']['distinct_raw_textSHA']==2);ok(axis['clear_seen_not_fresh']['distinct_raw_textSHA']==1);ok(r['disjoint_buckets']['SPECIFIC_FACTUAL_PENDING_QUEUE']['distinct_raw_textSHA']==1);ok(sum(v['raw_occurrences'] for v in r['disjoint_buckets'].values())==12)
 ok(db.execute('SELECT count(*) FROM known_roles').fetchone()==(2,));ok(db.execute('SELECT M1_content_tokens,occurrences FROM texts WHERE text_SHA256=?',(bytes.fromhex(hashes[1]),)).fetchone()==(21,2));ok(db.execute('SELECT count(*) FROM receipts').fetchone()==(9,));db.close()
 # All-copy overlay must cover actual source, not fabricate a target.
 bad=copy.deepcopy(p);bad['overlay_targets'].append({'text_SHA256':'f'*64,'hold_roles':[],'pending_roles':['PENDING'],'evidence':[]});oo=d/'extraoverlay';oo.mkdir();refusal(lambda:engine.run(bad,oo,lambda extra=0:None))
 # Required M1 join cannot silently skip a mismatched row.
 tdb=sqlite3.connect(d/'tokens.sqlite');tdb.execute('UPDATE docs SET text_SHA256=? WHERE source=1 AND source_ordinal=1',(bytes(32),));tdb.commit();tdb.close();oo=d/'tokenbad';oo.mkdir();refusal(lambda:engine.run(p,oo,lambda extra=0:None));tdb=sqlite3.connect(d/'tokens.sqlite');tdb.execute('UPDATE docs SET text_SHA256=? WHERE source=1 AND source_ordinal=1',(bytes.fromhex(hashes[0]),));tdb.commit();tdb.close()
 # Resource fail is partial rather than quality rejection or complete candidate frame.
 bad=copy.deepcopy(p);bad['limits']['all_events']=0;oo=d/'eventcap';oo.mkdir();refusal(lambda:engine.run(bad,oo,lambda extra=0:None))
 oo=d/'prewrite';oo.mkdir()
 def stop(extra=0):
  if extra:raise ValueError('synthetic_prewrite_reserve_stop')
 refusal(lambda:engine.run(p,oo,stop))
 # Exact compressed integrity/CRC: a valid prefix is never silently complete.
 src=Path(sources[0]['raw']['path']);raw=bytearray(src.read_bytes());raw[-8]^=1;src.write_bytes(raw);bad=copy.deepcopy(p);bad['sources'][0]['raw']={**bind(src),'bytes':len(raw),'SHA256':hashlib.sha256(raw).hexdigest()};oo=d/'crc';oo.mkdir();refusal(lambda:engine.run(bad,oo,lambda extra=0:None));ok(not (oo/'fresh-review-selection.json').exists())
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':N,'source_body_runs':0,'sampling_invocations':0},indent=2))
