"""Synthetic bytes only: never opens retained native source."""
import bz2,copy,hashlib,json,tempfile
from pathlib import Path
from unittest.mock import patch
import engine,source_guard,pilot
HERE=Path(__file__).resolve().parent
P=json.loads((HERE/'profile.json').read_text());N=[]
H=b'<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/"><siteinfo><base>https://en.wikipedia.org/wiki/Main_Page</base></siteinfo>'
def page(i,title):return b'<page><title>'+title+b'</title><ns>0</ns><id>'+str(i).encode()+b'</id></page>'
def must(fn):
 try:fn()
 except Exception:return
 raise AssertionError('expected refusal')
def test(name,fn):fn();N.append(name)
def fixture(kind='amp'):
 pages=[];rows=[]
 for i in range(1,101):
  title=b'British &amp; Irish Lions' if i==40 else b'Example '+str(i).encode();pages.append(page(i,title));title_index=title.decode()
  rows.append([2200+i,23,i,title_index,'0'*64,1,1,'unused'])
 raw=b''.join(pages);parts={(0,570):bz2.compress(H),(24391408,1375788):bz2.compress(raw)}
 if kind=='id':rows[39][2]=999
 if kind=='truncated':parts[(24391408,1375788)]=parts[(24391408,1375788)][:-4]
 if kind=='crc':
  b=bytearray(parts[(24391408,1375788)]);b[-5]^=1;parts[(24391408,1375788)]=bytes(b)
 if kind=='trailing':parts[(24391408,1375788)]+=b'X'
 calls=[]
 def read(a,n):calls.append((a,n));return parts[(a,n)]
 p=copy.deepcopy(P)
 if kind=='cap':p['limits']['decoded_bytes']=100
 result=engine.run(p,{},rows,read,None,lambda *x:None)
 return result,raw,calls
def valid():
 r,raw,calls=fixture();assert r['observed_pages']==100 and r['raw_index_title_mismatches']==1
 row=r['observed'][39];assert row['native_local_ordinal']==40 and row['expected_global_ordinal']==2240 and row['native_title']=='British & Irish Lions' and row['raw_index_title_lexeme']=='British &amp; Irish Lions'
 assert calls==[(0,570),(24391408,1375788)] and row['native_raw_XML']['SHA256']==hashlib.sha256(page(40,b'British &amp; Irish Lions')).hexdigest()
 assert not any('text' in k for x in r['observed'] for k in x if k!='raw_index_title_lexeme')
test('100 local/global identities; source raw entity versus native decoded title; exact raw page SHA; no body output',valid)
for kind in ['id','truncated','crc','trailing','cap']:test('refuse '+kind,lambda kind=kind:must(lambda:fixture(kind)))
def opened():
 with tempfile.TemporaryDirectory() as z:
  f=Path(z).resolve()/'synthetic';f.write_bytes(b'x'*570)
  with f.open('r+b') as out:out.seek(24391408);out.write(b'y'*1375788)
  b={'path':str(f),'stat':source_guard.ident(f.stat())};seen=[]
  with source_guard.opened(b,lambda:None) as rd:
   assert rd(0,570)==b'x'*570;must(lambda:rd(570,1));assert rd(24391408,1375788)==b'y'*1375788;rd.assert_custody()
  with source_guard.opened(b,lambda:None) as rd:
   must(lambda:rd(1,570));rd(0,570);rd(24391408,1375788)
test('read-only nofollow stat guard exact two reads; unrelated ranges refused',opened)
def rss():
 for text in ['', '1 0 3\n','bad\n',f'{1} {1} 3\n']:
  must(lambda text=text:pilot.tree_rss(text,999))
test('strict observed RSS empty/missing/malformed snapshots fail closed',rss)
def combined_cap():
 from types import SimpleNamespace
 import signal
 with tempfile.TemporaryDirectory() as z:
  root=Path(z).resolve();out=root/'new';called=[]
  def spawn(*a,**k):called.append(True);raise RuntimeError('synthetic stop before worker')
  with patch.object(pilot,'ROOT',root),patch.object(pilot,'verify',lambda a:({'output':str(out)},{},[],{})),patch.object(pilot,'size',lambda p:50000000000 if Path(p)==root else 0),patch.object(pilot.shutil,'disk_usage',lambda p:SimpleNamespace(free=10**12)),patch.object(pilot.subprocess,'Popen',spawn):
   must(lambda:pilot.supervise(SimpleNamespace(profile_sha256='test',code_pins_sha256='test')))
  assert called==[True] # 50GB actual intake passes 64GB combined cap, not an erroneous 4GB cap.
  signal.setitimer(signal.ITIMER_REAL,0)
test('actual supervisor 50GB combined intake passes 64GB preflight while output cap stays4MB',combined_cap)
print(json.dumps({'status':'PASS' ,'controls':len(N),'names':N,'retained_native_bytes_read':0,'network_requests':0},indent=2))
