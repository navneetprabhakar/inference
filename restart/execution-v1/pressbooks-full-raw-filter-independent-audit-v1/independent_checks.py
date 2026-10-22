"""Independent temporary synthetic sources/SQLite; no retained body run."""
import sys,json,sqlite3,tempfile,gzip,hashlib,zlib
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parents[1]/'pressbooks-full-raw-filter-preparation-v1';sys.path.insert(0,str(P))
import engine,inventory,select_core,bounded_policy
N=[]
with tempfile.TemporaryDirectory() as z:
 d=Path(z).resolve();out=d/'out';out.mkdir();f=sqlite3.connect(d/'frame');f.executescript(inventory.SCHEMA)
 family=sqlite3.connect(d/'family');family.execute('CREATE TABLE rows(source_id INTEGER,ordinal INTEGER,line_offset INTEGER,line_bytes INTEGER,ends_LF INTEGER,line_SHA256 BLOB,text_SHA256 BLOB,text_UTF8_bytes INTEGER,existing_flags INTEGER,identity_holds INTEGER,lead_status INTEGER,lead_root_id INTEGER,id_id INTEGER,url_id INTEGER,book_url_id INTEGER)');family.execute('CREATE TABLE strings(string_id INTEGER PRIMARY KEY,value TEXT)');family.execute('INSERT INTO strings VALUES(1,"SAME_BOOK_LEAD_NOT_CLEARED")')
 tok=sqlite3.connect(d/'tokens');tok.execute('CREATE TABLE docs(source INTEGER,source_ordinal INTEGER,text_SHA256 BLOB,line_SHA256 BLOB,UTF8_bytes INTEGER,content_tokens INTEGER,language_pass INTEGER,source_flags INTEGER,explicit_hold_flags INTEGER,normalized_SHA256 BLOB,normalized_words INTEGER)')
 parts=[];offset=0;lh=hashlib.sha256();hashes=[]
 # 200 fresh + held + reviewed survivor + language failure, followed by two aliases.
 texts=[f'A complete synthetic explanatory unit number {i}.' for i in range(203)];texts += [texts[200],texts[0]]
 for i,text in enumerate(texts,1):
  url=f'https://example.pressbooks.pub/book/chapter/u{i}/';obj={'id':url,'text':text,'source':'pressbooks','added':'2024-01-01T00:00:00','created':'01-01-2024','metadata':{'license':'CC BY https://creativecommons.org/licenses/by/4.0/','url':url,'book_url':'https://example.pressbooks.pub/book/','title':'Book','author':'Author','institution':'Example','subject':'Instruction'}};raw=(json.dumps(obj)+'\n').encode();hh=hashlib.sha256(raw).digest();r,_=inventory.row(i,offset,len(raw),True,hh,raw);assert r[5]==0;f.execute('INSERT INTO records VALUES('+','.join('?'*21)+')',r);h=r[17];hashes.append(h)
  family.execute('INSERT INTO rows VALUES('+','.join('?'*15)+')',(1,i,offset,len(raw),1,hh,h,len(text.encode()),0,0,2 if i==205 else 1,1,None,None,None))
  token=0 if i in [1,205] else 7+texts.index(text);lang=int(i!=203);tok.execute('INSERT INTO docs VALUES('+','.join('?'*11)+')',(1,i,h,hh,len(text.encode()),token,lang,0,0,h,8));parts.append(raw);lh.update(select_core.transcript([i,offset,len(raw),1,hh.hex()]));offset+=len(raw)
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
 bad=sqlite3.connect(d/'tokens');bad.execute('UPDATE docs SET line_SHA256=? WHERE source_ordinal=205',(b'x'*32,));bad.commit();bad.close();failed=d/'failed';failed.mkdir()
 try:engine.run(p,failed,lambda *a:None)
 except ValueError as e:assert str(e)=='verified_M1_language_doc_join'
 else:raise AssertionError('late duplicate token-line drift not refused')
 assert not(failed/'fresh-review-selection.json').exists();N.append('late alias metadata drift refuses complete selection after prior committed batches')
print(json.dumps({'status':'PASS_INDEPENDENT_SYNTHETIC_ONLY','controls':len(N),'names':N,'retained_source_runs':0,'network_requests':0,'global_ledger_writes':0},indent=2))
