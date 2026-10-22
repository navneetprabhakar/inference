"""Synthetic exact-span/window/SQL and bounded reused transport controls."""
from pathlib import Path
import tempfile,json,hashlib,os,sqlite3,copy,subprocess,sys,time
from unittest.mock import patch
from types import SimpleNamespace
import engine,rules,classify,custody
N=0
def ok(v):
 global N;assert v;N+=1
def no(f):
 global N
 try:f()
 except (ValueError,UnicodeError,sqlite3.Error,FileExistsError):N+=1;return
 raise AssertionError('expected refusal')
class Tok:
 def encode(self,s,add_special_tokens=False):assert add_special_tokens is False;return SimpleNamespace(ids=[1]*len(s))
def infer(p,data,remaining,check):return ['__label__en 0.8']*data.count(b'\n')
s='A'*1024+'tail';z=engine.diagnostics(s,Tok(),{},1,lambda *a:None,infer);ok(z['tokens']==1028);ok(z['scored']==2 and z['skipped']==1);ok(z['rows'][-1][3]==1028);ok(z['passed']==1);ok(z['rows'][-1][-1] is None)
def foreign(p,data,remaining,check):return ['__label__en 0.9','__label__en 0.9','__label__fr 0.99']
z=engine.diagnostics('A'*2048,Tok(),{},1,lambda *a:None,foreign);ok(z['passed']==0 and z['minimum']==0)
no(lambda:engine.diagnostics('A'*100,Tok(),{},1,lambda *a:None,lambda *a:[]))
for pred in ['__label__en nan','__label__en -1','__label__en 1.1','wrong 0.9','__label__en 0.9 unexpected']:no(lambda:rules.prediction(pred))
ok(rules.prediction('__label__en 0.8')[-1]==1);ok(rules.prediction('__label__en 0.79999')[-1]==0);ok(rules.prediction('__label__fr 0.99')[-1]==0)
ok(rules.projection('x\ny\r</s>')=='x y < /s >')
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp)/'raw';root.mkdir();out=Path(tmp)/'out';out.mkdir();texts=['Coherent synthetic English prose. '*3,'Coherent synthetic English prose. '*3,'Distinct source-bound exposition. '*4];rows=[];sources=[];env=[]
 for i,text in enumerate(texts):
  folder=root/f'attempt-{i:03}'/'raw';folder.mkdir(parents=True);raw=b'header\n'+text.encode()+b'\nfooter';q=folder/f'pg{i+1}.txt';q.write_bytes(raw);rows.append({'ordinal':i,'ebook_ID':i+1});sources.append({'path':str(q.relative_to(root)),'bytes':len(raw),'SHA256':hashlib.sha256(raw).hexdigest(),'dev_ino_size_mtime_ns_ctime_ns':custody.identity(q.stat())});env.append({'start_byte':7,'end_byte':7+len(text.encode()),'bytes':len(text.encode()),'characters':len(text),'SHA256':hashlib.sha256(text.encode()).hexdigest()})
 expected={'documents':3,'raw_source_bytes_read':sum(x['bytes'] for x in sources),'UTF8_bytes':sum(x['bytes'] for x in env),'characters':sum(x['characters'] for x in env),'all_windows':6};p={'records':rows,'source_files':sources,'envelopes':env,'source_output':str(root),'expected':expected,'boundary_records_path':'synthetic metadata only'}
 result=engine.run(p,out,lambda *a:None,Tok(),infer,lambda:10);ok(result['stats']['documents']==3);ok(result['distinct_envelope_SHA_diagnostic']['count']==2);ok(result['stats']['M1_content_tokens']==expected['characters']);ok(result['raw_content_plus_EOS']==expected['characters']+3);ok(result['full_text_copies_written']==0)
 db=sqlite3.connect(out/'screening.sqlite');ok(db.execute('SELECT count(*) FROM windows').fetchone()==(6,));ok(not db.execute('PRAGMA foreign_key_check').fetchall());ok(db.execute('SELECT count(*) FROM windows WHERE prediction_logical_line IS NOT NULL').fetchone()==(6,));db.close();ok(set(q.name for q in out.iterdir())<={'screening.sqlite','screening.sqlite-journal'})
 no(lambda:engine.run(p,out,lambda *a:None,Tok(),infer,lambda:10))
 out2=Path(tmp)/'out2';out2.mkdir();bad=copy.deepcopy(p);bad['envelopes'][1]['SHA256']='0'*64
 no(lambda:engine.run(bad,out2,lambda *a:None,Tok(),infer,lambda:10));db=sqlite3.connect(out2/'screening.sqlite');ok(db.execute('SELECT count(*) FROM docs').fetchone()==(1,));db.close()
# Actual subprocess fault transport, isolated scripts; all children reaped.
real=classify.subprocess.Popen
for label,script in [('stdout','import sys;sys.stdout.buffer.write(b"x"*1048577);sys.stdout.flush()'),('stderr','import sys;sys.stderr.buffer.write(b"x"*65537);sys.stderr.flush()'),('exit','raise SystemExit(1)'),('encoding','import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(b"\\xff")'),('timeout','import time;time.sleep(2)')]:
 children=[]
 def launch(argv,**kw):
  child=real([sys.executable,'-B','-c',script],**kw);children.append(child);return child
 with patch.object(classify.subprocess,'Popen',launch):
  try:classify.infer({'fasttext':{'path':'mock'},'language_model':{'path':'mock'}},b'A\n',.1 if label=='timeout' else 3,lambda:None)
  except (ValueError,TimeoutError):pass
  else:raise AssertionError('expected transport failure '+label)
 ok(len(children)==1 and children[0].poll() is not None)
no(lambda:classify.infer({},b'x'*8388609,1,lambda:None))
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':N,'retained_PG_body_reads':0,'tokenizer_fit_or_student_model_operations':0}))
