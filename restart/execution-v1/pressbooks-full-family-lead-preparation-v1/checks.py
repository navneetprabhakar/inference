"""Synthetic-only strict native-prefix leads and all-row metadata overlay checks."""
import hashlib,json,os,sqlite3,tempfile,time,types,signal
from pathlib import Path
from unittest.mock import patch
import derive as d,overlay as e,pilot
N=[]
def test(n,f):f();N.append(n)
def must(f):
 try:f()
 except Exception:return
 raise AssertionError('must refuse')
for book,url,code,root in [
 ('https://opentextbc.ca/book/front-matter/about/','https://opentextbc.ca/book/chapter/c/',1,'https://opentextbc.ca/book/'),
 ('https://iopn.library.illinois.edu/pressbooks/book/front-matter/about/','https://iopn.library.illinois.edu/pressbooks/book/chapter/c/',1,'https://iopn.library.illinois.edu/pressbooks/book/'),
 ('https://theatreappreciation.pressbooks.sunycreate.cloud/front-matter/introduction/','https://theatreappreciation.pressbooks.sunycreate.cloud/chapter/c/',2,'https://theatreappreciation.pressbooks.sunycreate.cloud/'),
 ('https://host.example/book/','https://host.example/book/chapter/c/',1,'https://host.example/book/'),
 ('https://host.example/','https://host.example/chapter/c/',2,'https://host.example/'),
 ('https://host.example:443/book/front-matter/a/','https://host.example/book/part/p/',1,'https://host.example:443/book/'),
 ('https://host.example/book/back-matter/a/','https://host.example/book/part/p/',1,'https://host.example/book/')]:
 test('observed structural form '+book,lambda book=book,url=url,code=code,root=root:(_ for _ in ()).throw(AssertionError()) if d.derive(book,url)!=(code,root) else None)
for invalid in ['https://u:p@host.example/book/chapter/x','https://@host.example/book/chapter/x','http://127.0.0.1/book/chapter/x','http://10.0.0.1/book/chapter/x','http://localhost/book/chapter/x','https://host.example:444/book/chapter/x','https://host.example/book/%2f/chapter/x','https://host.example/book/%2e%2e/chapter/x','https://host.example/book//chapter/x','https://host.example/book/%zz/chapter/x','https://host.example/book/\u200b/chapter/x','https://host.example/book/%E2%80%8B/chapter/x']:
 test('strict public/path refusal '+invalid,lambda invalid=invalid:(_ for _ in ()).throw(AssertionError()) if d.derive(invalid,invalid)[0]!=3 else None)
test('scheme and host mismatch remain uncleared',lambda:(_ for _ in ()).throw(AssertionError()) if d.derive('https://host.example/book/','http://host.example/book/chapter/x')[0]!=4 or d.derive('https://host.example/book/','https://other.example/book/chapter/x')[0]!=4 else None)
test('query/fragment no root guessing',lambda:(_ for _ in ()).throw(AssertionError()) if d.derive('https://host.example/book/?edition=2','https://host.example/book/chapter/x')[0]!=5 or d.derive('https://host.example/book/','https://host.example/book/chapter/x#part')[0]!=5 else None)
test('different literal bookprefix no merge',lambda:(_ for _ in ()).throw(AssertionError()) if d.derive('https://host.example/book1/front-matter/a/','https://host.example/book2/chapter/x')[0]!=6 else None)

def fixture(root):
 catalog='https://x.example/catalog/chapter/c/';conflict='https://x.example/conflict/chapter/c/';alias='https://different.example/alias/chapter/c/';ordinary='https://iopn.library.illinois.edu/pressbooks/book/chapter/c/'
 contents=[[(catalog,b'catalog',64|1024),(conflict,b'versionA',0),(ordinary,b'ordinary',0)],[(alias,b'catalog',64),(conflict,b'versionB',0),(catalog,b'catalog',0)]];inputs=[];conf=[];catpairs=[];cattext=[];expected={}
 for sid,records in enumerate(contents,1):
  path=root/f'source{sid}.sqlite';db=sqlite3.connect(path);db.execute('CREATE TABLE records(ordinal INTEGER PRIMARY KEY,line_offset INTEGER,line_bytes INTEGER,ends_LF INTEGER,line_SHA256 BLOB,text_SHA256 BLOB,text_UTF8_bytes INTEGER,flags INTEGER,id TEXT,url TEXT,book_url TEXT)')
  for ordinal,(id,body,flags) in enumerate(records,1):
   rooturl=id.rsplit('/chapter/',1)[0]+'/';book=rooturl+'front-matter/introduction/';raw=hashlib.sha256(f'{sid}:{ordinal}:{id}'.encode()).digest();text=hashlib.sha256(body).digest();row=(ordinal,(ordinal-1)*100,100,1,raw,text,len(body),flags,id,id,book);db.execute('INSERT INTO records VALUES('+','.join('?'*11)+')',row);expected[sid,ordinal]=row
   evidence={'source_id':sid,'ordinal':ordinal,'id':id,'line_SHA256':raw.hex(),'text_SHA256':text.hex()}
   if id==conflict:conf.append(evidence)
   if body==b'catalog':cattext.append(evidence)
   if id==catalog:catpairs.append(evidence)
  db.commit();db.close();s=path.stat();inputs.append({'source_id':sid,'path':str(path),'stat':e.ident(s),'rows':3,'SHA256':hashlib.sha256(path.read_bytes()).hexdigest()})
 p={'inputs':inputs,'limits':{'DB_bytes':2000000},'conflicting_identity_holds':conf,'cross_source_catalog_hold':{'id':catalog,'text_SHA256':hashlib.sha256(b'catalog').hexdigest()},'expected_rows':6,'expected_original_family_unresolved':2,'expected_catalog_occurrences':2,'expected_catalog_bindings':catpairs,'expected_catalog_content_occurrences':3,'expected_catalog_content_bindings':cattext}
 return p,expected

def roundtrip():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();p,expected=fixture(root);out=root/'out';out.mkdir();r=e.run(p,out,lambda *a:None);assert r['raw_metadata_rows']==6 and r['identity_hold_counts']=={'CONFLICTING_SAME_ID_TEXT':2,'EXACT_KNOWN_CATALOG_ID_TEXT':2,'EXACT_KNOWN_CATALOG_TEXT_CONTENT':3}
  db=sqlite3.connect(out/'leads.sqlite');rows=db.execute('SELECT r.source_id,r.ordinal,r.line_offset,r.line_bytes,r.ends_LF,r.line_SHA256,r.text_SHA256,r.text_UTF8_bytes,r.existing_flags,i.value,u.value,b.value,r.url_pair_SHA256,r.identity_holds,r.ancestry_status,r.split_status,r.rights_status FROM rows r LEFT JOIN strings i ON i.string_id=r.id_id LEFT JOIN strings u ON u.string_id=r.url_id LEFT JOIN strings b ON b.string_id=r.book_url_id ORDER BY r.source_id,r.ordinal').fetchall()
  for row in rows:
   sid,ordinal=row[:2];old=expected[sid,ordinal];assert tuple(row[2:12])==tuple(old[1:]);assert row[12]==hashlib.sha256(e.transcript(list(old[-3:]))).digest();assert row[-3:]==(0,0,0)
  assert rows[0][13]==6 and rows[3][13]==4 and rows[5][13]==6 and rows[1][13]==rows[4][13]==1
  assert db.execute('PRAGMA integrity_check').fetchone()==('ok',) and db.execute('PRAGMA foreign_key_check').fetchone() is None;db.close()
  for binding in p['inputs']:assert e.ident(Path(binding['path']).stat())==binding['stat']
test('two shard all-row SQL/rawURLpair lossless/sourceflags/uncleared/conflicts/knowncatalogdifferentIDs+ordinals',roundtrip)

def fail_drift(which):
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();p,_=fixture(root);out=root/'out';out.mkdir()
  if which=='conflict':p['conflicting_identity_holds'][0]['text_SHA256']='0'*64
  elif which=='catalog':p['expected_catalog_content_occurrences']=2
  elif which=='flags':p['expected_original_family_unresolved']=0
  else:p['expected_rows']=7
  must(lambda:e.run(p,out,lambda *a:None))
  db=sqlite3.connect(out/'leads.sqlite');assert db.execute('SELECT count(*) FROM rows').fetchone()==(0,);db.close()
for which in ['conflict','catalog','flags','rows']:test('exact expected '+which+' drift refuses+rollsback uncommitted rows',lambda which=which:fail_drift(which))

def input_mutation():
 with tempfile.TemporaryDirectory() as z:
  p,_=fixture(Path(z).resolve())
  try:
   with e.frames(p,lambda:None) as (sources,custody):
    path=Path(sources[0][0]['path']);path.touch();custody()
  except ValueError:pass
  else:raise AssertionError('input changed accepted')
test('readonly source stat mutation fails closed',input_mutation)
def no_output():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();p,_=fixture(root);out=root/'out';out.mkdir()
  def refuse(*a):raise ValueError('cap')
  must(lambda:e.run(p,out,refuse));assert not list(out.iterdir())
test('aggregate prewrite refusal before DB file',no_output)
def lifecycle():
 old=pilot.ENTRY_START;pilot.ENTRY_START=pilot.clk()-54.98
 try:
  with patch.object(pilot,'verify',lambda a:time.sleep(.1)):must(lambda:pilot.supervise(types.SimpleNamespace()))
 finally:pilot.ENTRY_START=old
 with tempfile.TemporaryDirectory() as z:
  out=Path(z);(out/'old').write_bytes(b'preserve')
  with patch.object(pilot,'verify',lambda a:{'output':str(out)}):must(lambda:pilot.supervise(types.SimpleNamespace()))
  assert list(out.iterdir())==[out/'old'] and (out/'old').read_bytes()==b'preserve'
test('actual early shareddeadline and existing-output preservation',lifecycle)
def worker():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();p,_=fixture(root);out=root/'out';out.mkdir();p['output']=str(out)
  for n,size in pilot.SLOTS.items():(out/n).write_bytes(b' '*size)
  a=types.SimpleNamespace(start=pilot.clk(),supervisor_pid=os.getppid(),profile_sha256='p',code_pins_sha256='c');(out/'ownership.json').write_text(json.dumps({'worker_PID':os.getpid(),'supervisor_PID':os.getppid(),'shared_start':a.start,'profile_SHA256':'p','codepins_SHA256':'c'}))
  with patch.object(pilot,'verify',lambda a:p),patch.object(pilot,'guard',lambda *a:None):pilot.worker(a)
  r=json.loads((out/'result.json').read_text());assert r['status']=='COMPLETE_TWO_SHARD_ADDITIVE_STRUCTURAL_LEADS_NO_ADMISSION' and r['raw_metadata_rows']==6 and r['artifacts']['leads.sqlite']['SHA256']==hashlib.sha256((out/'leads.sqlite').read_bytes()).hexdigest()
test('actual worker success closes inputFDs/postflight/streamartifacthash',worker)
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':len(N),'names':N,'actual_source_frames_read':0,'source_bodies_read':0,'network_requests':0},indent=2))
