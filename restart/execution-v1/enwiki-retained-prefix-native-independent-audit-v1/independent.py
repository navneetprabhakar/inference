"""Independent synthetic native/index round-trip and boundary audit; no source."""
import base64,bz2,hashlib,json,os,random,sqlite3,sys,tempfile
from pathlib import Path
from unittest.mock import patch
B=Path(__file__).resolve().parent.parent;P=B/'enwiki-retained-prefix-frame-preparation-v1';sys.path.insert(0,str(P));import engine,index_reader,pilot,source_guard
N=[]
def test(name,f):f();N.append(name)
def must(f):
 try:f()
 except Exception:return
 raise AssertionError('must refuse')
def sha(b):return hashlib.sha256(b).digest()
H=b'<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/"><siteinfo><base>https://en.wikipedia.org/wiki/Main_Page</base></siteinfo>'
def native(i,title,text=b'plain'):
 return b'<page><title>'+title+b'</title><ns>0</ns><id>'+str(i).encode()+b'</id><revision><id>'+str(1000+i).encode()+b'</id><model>wikitext</model><format>text/x-wiki</format><text>'+text+b'</text></revision></page>'
def fixture(root,large=False):
 titles={1:b'British &amp; Irish Lions',2:b'&amp;amp;',3:'e\u0301 😀'.encode()};rnd=random.Random(2300);big=base64.b64encode(rnd.randbytes(2400000)) if large else b'plain';pages=[native(i,titles.get(i,('T'+str(i)).encode()),big if i==1 else b'plain') for i in range(1,101)];header=bz2.compress(H);body=b''.join(pages);comp=bz2.compress(body);data=header+comp;path=root/'index.sqlite';db=sqlite3.connect(path)
 db.executescript('CREATE TABLE groups(group_ordinal INTEGER PRIMARY KEY,block_start INTEGER,block_end_exclusive INTEGER,first_row INTEGER,last_row INTEGER,row_count INTEGER);CREATE TABLE rows(row_ordinal INTEGER PRIMARY KEY,page_id INTEGER UNIQUE,group_ordinal INTEGER,title TEXT,raw_line_sha256 BLOB,raw_line_bytes INTEGER,line_ends_LF INTEGER,noncanonical_offset_ascii TEXT,noncanonical_page_ascii TEXT);')
 db.execute('INSERT INTO groups VALUES(1,?,?,1,100,100)',(len(header),len(data)))
 original=[]
 for i in range(1,101):
  title=titles.get(i,('T'+str(i)).encode()).decode();off=('000' if i==2 else '')+str(len(header));pid=('000' if i==2 else '')+str(i);line=(off+':'+pid+':'+title+'\n').encode();original.append(line);db.execute('INSERT INTO rows VALUES(?,?,?,?,?,?,?,?,?)',(i,i,1,title,sha(line),len(line),1,off if i==2 else None,pid if i==2 else None))
 db.commit();db.close();p={'index':{'path':str(path),'stat':index_reader.identity(path.stat())},'source':{'bytes':len(data)},'selection':{'groups':1,'rows':100,'header_bytes':len(header),'compressed_prefix_end_exclusive':len(data),'require_next_group_outside_prefix':False},'semantic_module':str(B/'enwiki-semantic-SAX-metadata-preparation-v3/semantic.py'),'sink_module':str(B/'enwiki-compact-SQLite-sink-preparation-v2/sink.py'),'title_decoder':str(B/'enwiki-index-XML-title-proposal-v1/title_decode.py'),'limits':{'DB_bytes':2000000,'metadata_bytes':2000000,'revision_occurrences':1000,'decoded_bytes':10000000,'max_group_compressed_bytes':4078038,'compressed_bytes':len(data)}}
 return p,data,pages,body,original,len(comp)
def large_roundtrip():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();p,data,pages,body,lines,n=fixture(root,True);assert 1802826<n<=4078038
  out=root/'out';out.mkdir();calls=[]
  def read(off,n):calls.append((off,n));return data[off:off+n]
  with index_reader.opened(p,lambda *a,**k:None) as groups:r=engine.run(p,groups,read,out,lambda *a,**k:None)
  db=sqlite3.connect(out/'frame.sqlite');stored=db.execute('SELECT row_ordinal,page_id,first_revision_id,revision_count,group_decoded_start,raw_XML_bytes,raw_SHA256 FROM pages ORDER BY row_ordinal').fetchall();assert len(stored)==100;offset=0
  for i,(row,pageid,rev,nrev,start,nbytes,rawhash) in enumerate(stored,1):
   assert (row,pageid,rev,nrev,start,nbytes,rawhash)==(i,i,1000+i,1,offset,len(pages[i-1]),sha(pages[i-1]));offset+=nbytes
  assert db.execute('SELECT count(*) FROM revisions').fetchone()==(100,) and db.execute('PRAGMA foreign_key_check').fetchone() is None
  group=db.execute('SELECT decoded_bytes,raw_SHA256 FROM groups').fetchone();assert group==(len(body),sha(body));db.close();receipt=json.loads((out/'group-receipts.jsonl').read_text());assert receipt['raw_index_lines_SHA256']==hashlib.sha256(b''.join(lines)).hexdigest() and receipt['actual_native_identity_SHA256']==receipt['frozen_index_identity_SHA256'] and receipt['references_decoded_once']==2
  assert r['counts']['pages']==100 and r['counts']['revision_occurrences']==100 and len(calls)==2 and sum(x[1] for x in calls)==len(data)
test('100row streamed SQL/native roundtrip, >old1.8MB compressedgroup, XMLonce/noncanonical/rawspan/allrevision/CRC proof',large_roundtrip)
def source_bound():
 with tempfile.TemporaryDirectory() as z:
  f=Path(z).resolve()/'synthetic';f.write_bytes(b'x'*4078038);binding={'path':str(f),'stat':source_guard.ident(f.stat())};real=os.pread;calls=[]
  def read(fd,n,off):calls.append((n,off));return real(fd,n,off)
  try:
   with patch.object(source_guard.os,'pread',read),source_guard.opened(binding,lambda:None) as rd:
    must(lambda:rd(0,4078039));assert calls==[];assert len(rd(0,4078038))==4078038;rd.assert_custody();assert calls==[(4078038,0)];raise RuntimeError('synthetic prefix intentionally shorter')
  except RuntimeError:pass
 testdata=True
test('actual source max4078038 accepted and4078039 refused before IO',source_bound)
for label,sql in [('rowcount101','UPDATE groups SET row_count=101,last_row=101'),('UTF8rawhash','UPDATE rows SET raw_line_sha256=zeroblob(32) WHERE row_ordinal=3'),('wrong numeric lexeme','UPDATE rows SET noncanonical_page_ascii="+2" WHERE row_ordinal=2'),('crossgroup row','UPDATE rows SET group_ordinal=2 WHERE row_ordinal=4')]:
 def bad(sql=sql):
  with tempfile.TemporaryDirectory() as z:
   root=Path(z).resolve();p,*_=fixture(root);path=Path(p['index']['path']);db=sqlite3.connect(path);db.execute(sql);db.commit();db.close();p['index']['stat']=index_reader.identity(path.stat())
   def consume():
    with index_reader.opened(p,lambda:None) as groups:list(groups())
   must(consume)
 test('index '+label+' failclosed',bad)
def cutoff():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();p,*_=fixture(root);p['selection']['require_next_group_outside_prefix']=True;path=Path(p['index']['path']);db=sqlite3.connect(path);end=p['selection']['compressed_prefix_end_exclusive'];db.execute('INSERT INTO groups VALUES(2,?,?,101,101,1)',(end,end+10));db.commit();db.close();p['index']['stat']=index_reader.identity(path.stat())
  with index_reader.opened(p,lambda:None) as g:assert len(list(g()))==1
  p['source']['bytes']=end+10
  def bad():
   with index_reader.opened(p,lambda:None) as g:list(g())
  must(bad)
test('exact nextgroup completeness cutoff proof, equalend refused',cutoff)
def lifecycle():
 import time,types
 from unittest.mock import patch
 old=pilot.ENTRY_START;pilot.ENTRY_START=pilot.clk()-21894.98
 try:
  with patch.object(pilot,'verify',lambda a:time.sleep(.1)):must(lambda:pilot.supervise(types.SimpleNamespace()))
 finally:pilot.ENTRY_START=old
 with tempfile.TemporaryDirectory() as z:
  p=Path(z);(p/'original').write_bytes(b'kept')
  with patch.object(pilot,'verify',lambda a:({'output':str(p)},{})):must(lambda:pilot.supervise(types.SimpleNamespace()))
  assert (p/'original').read_bytes()==b'kept' and list(p.iterdir())==[p/'original']
test('actual early blocked-preflight alarm and existing-output preservation',lifecycle)
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','independent_controls':len(N),'names':N,'retained_source_or_index_body_reads':0,'actual_GETs':0,'global_ledger_writes':False},indent=2))
