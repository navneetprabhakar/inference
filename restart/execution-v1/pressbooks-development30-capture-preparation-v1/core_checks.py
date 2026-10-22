"""Synthetic gzip/JSONL+SQLite full frame/capture controls only."""
from pathlib import Path
import tempfile,json,gzip,hashlib,sqlite3,io
import capture,inventory,select_core
checks=[]
def reject(fn):
 try:fn()
 except Exception:return
 raise AssertionError('expected refusal')
def fixture(z,kind=None):
 z=Path(z);out=z/'out';out.mkdir();raw=[]
 for i,t in enumerate(['A complete paragraph.','Unicode café\nSecond paragraph.']):
  obj={'id':f'https://books.pressbooks.pub/book/chapter/{i}/','text':t,'source':'pressbooks','added':'2025-01-01','created':'2020-01-01','metadata':{'license':'https://creativecommons.org/licenses/by/4.0/','url':f'https://books.pressbooks.pub/book/chapter/{i}/','book_url':'https://books.pressbooks.pub/book/','title':'Example','author':'Author','institution':'University','subject':'Subject'}}
  raw.append((json.dumps(obj,ensure_ascii=False)+'\n').encode())
 frame=z/'frame.sqlite';d=sqlite3.connect(frame);d.executescript(inventory.SCHEMA);off=0;lh=hashlib.sha256();selected={}
 for ordinal,line in enumerate(raw,1):
  h=hashlib.sha256(line).digest();r,_=inventory.row(ordinal,off,len(line),True,h,line);d.execute('INSERT INTO records VALUES('+','.join('?' for _ in r)+')',r);lh.update(json.dumps([ordinal,off,len(line),1,h.hex()],separators=(',',':')).encode()+b'\n')
  selected[ordinal]={'line_SHA256':h.hex(),'line_offset':off,'line_bytes':len(line),'ends_LF':1,'text_SHA256':r[17].hex(),'text_UTF8_bytes':r[18]};off+=len(line)
 if kind=='frame':d.execute('UPDATE records SET text_UTF8_bytes=999 WHERE ordinal=1')
 d.commit();d.close();body=gzip.compress(b''.join(raw));expectedbody=body
 if kind=='CRC':body=body[:-5]+bytes([body[-5]^1])+body[-4:]
 if kind=='truncated':body=body[:-2]
 if kind=='trailing':body+=b'junk'
 if kind=='selected':selected[1]['text_SHA256']='0'*64
 if kind=='missing':selected[3]=selected[1]
 f={'path':str(frame),'rows':2,'ordered_line_locator_SHA256':lh.hexdigest()};binding={'source_id':1,'bytes':len(expectedbody),'SHA256':hashlib.sha256(expectedbody).hexdigest()}
 if kind=='frameDigest':f['ordered_line_locator_SHA256']='0'*64
 if kind=='sourceSHA':binding['SHA256']='0'*64
 stream=io.BytesIO(body)
 r=capture.one(binding,f,selected,out,stream.read,lambda *a:None,[])
 for item in r['captures']:
  line=(out/item['raw_line_file']).read_bytes();text=(out/item['text_file']).read_bytes();assert line==raw[item['ordinal']-1] and json.loads(line)['text'].encode()==text and hashlib.sha256(text).hexdigest()==item['text_SHA256']
 return r
with tempfile.TemporaryDirectory() as z:assert len(fixture(z)['captures'])==2
checks.append('actual_gzip_fullCRC_SQLite_everyrow_exact_rawJSON_text_inverse')
for kind in ['CRC','truncated','trailing','selected','missing','frame','frameDigest','sourceSHA']:
 with tempfile.TemporaryDirectory() as z:reject(lambda:fixture(z,kind))
 checks.append('refuse_'+kind)
pop=[{'text_SHA256':hashlib.sha256(str(i).encode()).hexdigest(),'text_UTF8_bytes':i} for i in range(30)];d=select_core.draws(pop)
assert d==select_core.draws(list(reversed(pop))) and len(d['draws'])==30 and len({x['text_SHA256'] for x in d['draws'][:20]})==20
checks.append('uniform_draw_order_independent_exact20distinct_and_byte10_multiplicity')
assert all(0<=select_core.byte_draw(n,17)<17 for n in range(1,1001));checks.append('1000_byte_rejection_sampler_bounds')
reject(lambda:select_core.draws(pop+pop[:1]));reject(lambda:select_core.draws(pop[:19]));checks.append('duplicate_or_insufficient_population_refused')
with tempfile.TemporaryDirectory() as z:
 p=Path(z);seen=[]
 def stop(n=0):seen.append(n);raise ValueError('prewrite_outputcap')
 reject(lambda:capture.write(p,'blocked',b'body',stop));assert not list(p.iterdir()) and seen==[4]
checks.append('prewrite_cap_before_file_creation')
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','checks':len(checks),'cases':checks,'retained_source_reads':0},indent=2))
