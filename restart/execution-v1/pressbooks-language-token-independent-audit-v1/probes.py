"""Synthetic independent probes; no actual PB source/classifier/tokenizer pass."""
import hashlib,json,sys,tempfile,sqlite3,os,time,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent.parent/'pressbooks-language-token-preparation-v1';sys.path.insert(0,str(P));import engine,rules,classify
names=[]
def t(n,f):f();names.append(n)
def must(f):
 try:f()
 except Exception:return
 raise AssertionError('accepted')
class Inventory:
 @staticmethod
 def unique(pairs):
  d={}
  for k,v in pairs:
   if k in d:raise ValueError('duplicate')
   d[k]=v
  return d
 nofloat=staticmethod(lambda x:(_ for _ in ()).throw(ValueError('nonfinite')))
def binding():
 text='Exact Café 😀\r\nEnglish </s>.';raw=(json.dumps({'id':'exact','text':text})+'\n').encode();sha=hashlib.sha256(raw).digest();m=[1,0,len(raw),1,sha,0,'exact']+[None]*10+[hashlib.sha256(text.encode()).digest(),len(text.encode()),len(text)]
 assert engine.source_record(1,0,len(raw),True,sha,raw,m,Inventory)==('exact',text,text.encode())
 for k,value in [(0,2),(1,1),(2,len(raw)-1),(3,0),(4,b'x'*32),(6,'wrong'),(17,b'x'*32),(18,1),(19,1)]:
  bad=list(m);bad[k]=value;must(lambda:engine.source_record(1,0,len(raw),True,sha,raw,bad,Inventory))
 must(lambda:engine.source_record(1,0,len(raw),True,sha,raw,None,Inventory))
t('actual source_record exact whole inverse and ten frame drift refusals',binding)
def windows():
 text='A'*1024+'B'*40;w,n=engine.prepared(text);assert len(w)==3 and w[2][0]['scored'] and w[2][0]['start']==1024 and w[2][0]['end']==1064
 assert n==sum(len(p)+1 for m,p in w if m['scored'])
 text='A'*1024+'B'*39;w,n=engine.prepared(text);assert len(w)==3 and not w[2][0]['scored'] and w[2][0]['alphabetics']==39
 assert rules.projection('a\r\nb</s>')=='a  b< /s >'
 assert rules.prediction('__label__en 0.8')[-1]==1 and rules.prediction('__label__en 0.799999')[-1]==0 and rules.prediction('__label__fr 0.99')[3]==0
 for x in ['__label__en nan','__label__en -1','__label__en 5','__label__en .9 extra']:must(lambda:rules.prediction(x))
t('1024 boundary40/39alphabets, exactprojection and threshold/nonEnglish/top1 refusals',windows)
def batch():
 with tempfile.TemporaryDirectory() as z:
  store=engine.Store(z,{'DB_bytes':4000000},lambda *a:None);text='A'*1024+'B'*40;w,_=engine.prepared(text);norm=hashlib.sha256(text.encode()).digest();sha=norm.hex()
  def doc(i,flags):return {'doc':i,'identity':{'id':'x'+str(i),'source':1,'ordinal':i,'text_SHA256':sha,'line_SHA256':str(i)*64,'characters':len(text),'UTF8_bytes':len(text),'source_flags':64},'explicit_flags':flags,'tokens':123,'windows':w,'normalized_SHA256':norm,'normalized_words':1}
  inputs=[doc(1,0),doc(2,4)]
  def predictions(p,data,remaining,check):
   assert len(data.splitlines())==6;return ['__label__en .99','__label__en .99','__label__en .7']*2
  store.batch({},inputs,10,predictions);assert store.docs==2 and store.windows==6
  assert store.db.execute('select count(*) from docs where language_pass=0').fetchone()==(2,)
  assert store.db.execute('select occurrences,explicit_hold_flags,source_flags from texts').fetchone()==(2,4,64)
  assert store.db.execute('select sum(content_tokens),sum(EOS_count) from docs').fetchone()==(246,2)
  must(lambda:store.batch({},[doc(3,0)],10,lambda *a:['__label__en .99']*2));store.db.rollback()
  store.close()
t('actual batch shorttailfailure, duplicatehash unionhold, EOSseparate, missingprediction refuses',batch)
def flags():
 target={'conflicting_IDs':{'conflict'},'catalog':{'id':'catalog','text_SHA256':'hash'}}
 assert engine.explicit_flags('different','hash',target)==4 and engine.explicit_flags('catalog','hash',target)==6 and engine.explicit_flags('conflict','other',target)==1 and engine.explicit_flags('normal','other',target)==0
 must(lambda:engine.normalization_diagnostic('x',lambda x:'x'*64000001))
t('independent bit1/2/4 contentancestry and normalized cap',flags)
def transport():
 with tempfile.TemporaryDirectory() as z:
  p=Path(z)/'fake';p.write_text('#!/bin/sh\nwhile IFS= read -r line; do echo "__label__en 0.99"; done\n');p.chmod(0o700);profile={'fasttext':{'path':str(p)},'language_model':{'path':'synthetic'}}
  assert classify.infer(profile,b'one\ntwo\n',2,lambda *a:None)==['__label__en 0.99']*2
  p.write_text('#!/bin/sh\nexec sleep 60\n');start=time.monotonic();must(lambda:classify.infer(profile,b'one\n',.05,lambda *a:None));assert time.monotonic()-start<2
  p.write_text('#!/bin/sh\nexit 1\n');must(lambda:classify.infer(profile,b'one\n',1,lambda *a:None))
t('actual classifier child stdin/stdout plus timeoutkill/reap and nonzeroexit',transport)
def clocks():
 for i in range(3):
  a=time.monotonic();child=float(subprocess.check_output([sys.executable,'-B','-c','import time;print(time.monotonic())']));b=time.monotonic();assert a<=child<=b
t('actual pinnedRuntime crossprocess sharedclock threechild containment',clocks)
print(json.dumps({'status':'PASS_SYNTHETIC_INDEPENDENT','checks':len(names),'names':names,'source_bodies_read':0,'actual_tokenizer_or_language_model_pass':False},indent=2))
