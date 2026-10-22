"""Finite synthetic controls only; no retained source access."""
import hashlib,json,sqlite3,tempfile,gzip,os,zlib,copy
from pathlib import Path
import bounded_policy,policy,schema,select_core,engine,inventory
N=0
def ok(v):
 global N;assert v;N+=1
def refuse(f):
 global N
 try:f()
 except (ValueError,KeyError,sqlite3.IntegrityError,zlib.error):N+=1;return
 raise AssertionError('expected refusal')
for text in ['A short definition.','Code calls f() and prints.','See Figure 2 for illustration.','As of2004, this source said so.','A procedure\n1. Open valve.\n2. Read gauge.',"This explains '( and )' as a literal token."]:
 r=bounded_policy.evaluate(text);ok(r['mask']==0);decoded=zlib.decompress(r['zlib_bytes']);ok(hashlib.sha256(decoded).digest()==r['JSON_SHA256'])
for text in ['Both surfaces ( and ) are shown.','For the relation\nⓐ Find the domain.','It is estimated to be about\nHowever, nothing follows.']:
 ok(bounded_policy.evaluate(text)['mask']!=0)
refuse(lambda:bounded_policy.evaluate('Figure 1. '*5001))
refuse(lambda:bounded_policy.evaluate('x'*(policy.MAX_BYTES+1)))
# Exact deterministic selections, token weighting not byte weighting, preserved repeats/overlap.
def sample_db():
 db=sqlite3.connect(':memory:');db.execute('CREATE TABLE texts(text_SHA256 BLOB PRIMARY KEY,M1_content_tokens INTEGER,UTF8_bytes INTEGER,first_source INTEGER,first_ordinal INTEGER,fresh_population INTEGER)')
 for i,t,b in [(1,1,90000),(2,999,1),(3,0,20000),(4,55,20)]:db.execute('INSERT INTO texts VALUES(?,?,?,?,?,?)',(hashlib.sha256(str(i).encode()).digest(),t,b,1,i,1))
 return db
sdb=sample_db();a=select_core.select(sdb,'frozen-seed',3,lambda:None,lambda s,o:{'book':o});b=select_core.select(sdb,'frozen-seed',3,lambda:None,lambda s,o:{'book':o});ok(a==b);ok(len([d for d in a['draws'] if d['mode'].startswith('UNIFORM')])==3);ok(len(a['draws'])==6);ok(all(d['M1_content_tokens']>0 for d in a['draws'] if d['mode'].startswith('TOKEN')));ok(a['tokenweighted_with_replacement']==3);refuse(lambda:select_core.select(sdb,'seed',5,lambda:None,lambda s,o:{}));sdb.close()
# Actual production full-gzip/row/frame/token/family+candidate DB pass on200tiny synthetic records.
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp).resolve();out=d/'out';out.mkdir();rawparts=[];frame=sqlite3.connect(d/'frame.sqlite');frame.executescript(inventory.SCHEMA);fam=sqlite3.connect(d/'family.sqlite');fam.execute('CREATE TABLE rows(source_id INTEGER,ordinal INTEGER,line_offset INTEGER,line_bytes INTEGER,ends_LF INTEGER,line_SHA256 BLOB,text_SHA256 BLOB,text_UTF8_bytes INTEGER,existing_flags INTEGER,identity_holds INTEGER,lead_status INTEGER,lead_root_id INTEGER,id_id INTEGER,url_id INTEGER,book_url_id INTEGER)');fam.execute('CREATE TABLE strings(string_id INTEGER PRIMARY KEY,value TEXT)');tok=sqlite3.connect(d/'tokens.sqlite');tok.execute('CREATE TABLE docs(source INTEGER,source_ordinal INTEGER,text_SHA256 BLOB,line_SHA256 BLOB,UTF8_bytes INTEGER,content_tokens INTEGER,language_pass INTEGER,source_flags INTEGER,explicit_hold_flags INTEGER,normalized_SHA256 BLOB,normalized_words INTEGER)');off=0;lh=hashlib.sha256();allh=[]
 for i in range(1,204):
  text=f'This complete synthetic explanation number {i} remains intact.';u=f'https://example.pressbooks.pub/book/chapter/u{i}/';obj={'id':u,'text':text,'source':'pressbooks','added':'2024-01-01T00:00:00','created':'01-01-2024','metadata':{'license':'CC BY https://creativecommons.org/licenses/by/4.0/','url':u,'book_url':'https://example.pressbooks.pub/book/front-matter/introduction/','title':'Book','author':'Author','institution':'Example','subject':'Instruction'}};raw=(json.dumps(obj)+'\n').encode();hh=hashlib.sha256(raw).digest();rec,_=inventory.row(i,off,len(raw),True,hh,raw);assert rec[5]==0;frame.execute('INSERT INTO records VALUES('+','.join(['?']*21)+')',rec);h=rec[17];allh.append(h.hex());fam.execute('INSERT INTO rows VALUES('+','.join(['?']*15)+')',(1,i,off,len(raw),1,hh,h,len(text.encode()),0,0,1,None,None,None,None));tok.execute('INSERT INTO docs VALUES('+','.join(['?']*11)+')',(1,i,h,hh,len(text.encode()),20+i,1,0,0,h,9));rawparts.append(raw);lh.update(select_core.transcript([i,off,len(raw),1,hh.hex()]));off+=len(raw)
 for db in [frame,fam,tok]:db.commit();db.close()
 source=d/'source.gz';source.write_bytes(gzip.compress(b''.join(rawparts)))
 def binding(p):
  st=p.stat();return {'path':str(p),'stat':[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]}
 sb=binding(source);sb.update({'bytes':source.stat().st_size,'SHA256':hashlib.sha256(source.read_bytes()).hexdigest()});fb=binding(d/'frame.sqlite');fb.update({'rows':203,'ordered_line_locator_SHA256':lh.hexdigest()})
 p={'sources':[{'source_id':1,'raw':sb,'frame':fb,'known_holds':[]}],'family_frame':binding(d/'family.sqlite'),'token_frame':binding(d/'tokens.sqlite'),'known_hold_SHA256':[allh[0]],'fresh_exclusion_SHA256':allh[:3],'expected':{'raw_rows':203,'distinct_textSHA':203},'limits':{'DB_bytes':600000000,'journal_bytes':64000000,'all_events':5000000,'selection_bytes':8000000},'sampling_seed':'synthetic'}
 result=engine.run(p,out,lambda extra=0:None);ok(result['raw_rows']==203);ok(result['populations']['full_filtered_candidate']['distinct_raw_textSHA']==202);ok(result['populations']['fresh_review_population']['distinct_raw_textSHA']==200);ok(result['populations']['previously_reviewed_surviving_candidate']['distinct_raw_textSHA']==2);sel=json.loads((out/'fresh-review-selection.json').read_text());ok(sel['uniform_without_replacement']==200 and sel['tokenweighted_with_replacement']==200);ok(not(set(allh[:3])&{v['text_SHA256'] for v in sel['draws']}));db=sqlite3.connect(out/'candidate.sqlite');ok(db.execute('PRAGMA integrity_check').fetchone()==('ok',));ok(db.execute('SELECT count(*) FROM texts').fetchone()==(203,));db.close()
 # Corrupt CRC cannot publish a complete source; no retry or silently retained prefix.
 bad=bytearray(source.read_bytes());bad[-8]^=1;source.write_bytes(bad);p['sources'][0]['raw']={**binding(source),'bytes':len(bad),'SHA256':hashlib.sha256(bad).hexdigest()};second=d/'failed';second.mkdir();refuse(lambda:engine.run(p,second,lambda extra=0:None));ok(not(second/'fresh-review-selection.json').exists())
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':N,'retained_source_or_candidate_policy_runs':0}))
# Resource adapter is lossless and mask-identical to the unchanged policy, not a new semantic policy.
for i in range(40):
 t=('An intact instructional paragraph explains context.\n'*(i%4))+(['Figure 1 is referenced.','Both surfaces ( and ) are shown.','For the relation\nⓐ Find the range.','This refers to (and) as a token.'][i%4])
 b=bounded_policy.evaluate(t);raw=zlib.decompress(b['zlib_bytes']);expected=(json.dumps(policy.filter_raw(t),ensure_ascii=False,separators=(',',':'))+'\n').encode();ok(raw==expected)
print(json.dumps({'status':'PASS_TOTAL_SYNTHETIC_CONTROLS','controls':N,'retained_source_runs':0}))
