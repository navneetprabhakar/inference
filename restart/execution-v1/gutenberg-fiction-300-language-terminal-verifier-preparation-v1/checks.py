"""Complete synthetic stored-output checks; no original source or detector/tokenizer."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import importlib.util,sys,tempfile,sqlite3,json,hashlib,copy,os,signal
import core
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;sys.path.insert(0,str(BASE/'gutenberg-fiction-300-language-M1-preparation-v1'))
spec=importlib.util.spec_from_file_location('producer_engine',BASE/'gutenberg-fiction-300-language-M1-preparation-v1/engine.py');engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
N=0
sha=lambda b:hashlib.sha256(b).digest()
def must(fn):
 global N
 try:fn()
 except Exception:N+=1;return
 raise AssertionError('expected refusal')
def fixture(root,mutation=None):
 path=root/'screening.sqlite';db=sqlite3.connect(path);db.executescript(engine.SCHEMA);texts=['A'*1030,'8'*1024+'é'*39,'A'*39];recs=[];srcs=[];envs=[]
 for i,t in enumerate(texts):
  raw=b'head'+t.encode()+b'foot';body=t.encode();rec={'ordinal':i,'ebook_ID':i+10};src={'SHA256':sha(raw).hex(),'bytes':len(raw)};e={'start_byte':4,'end_byte':4+len(body),'SHA256':sha(body).hex(),'bytes':len(body),'characters':len(t)};recs.append(rec);srcs.append(src);envs.append(e)
  def infer(p,data,remaining,check):return ['__label__fr 0.9' if i==2 else '__label__en 0.9']*(len(data.splitlines()))
  d=engine.diagnostics(t,SimpleNamespace(encode=lambda text,**k:SimpleNamespace(ids=list(range(len(text))))),{},100,lambda *a:None,infer)
  db.execute('INSERT INTO docs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(i,i+10,sha(raw),4,4+len(body),sha(body),len(t),len(body),d['tokens'],1,d['scored'],d['skipped'],d['passed'],d['minimum'],d['input_SHA256'],d['prediction_lines_SHA256']))
  db.executemany('INSERT INTO windows VALUES('+','.join('?' for _ in range(16))+')',[(i,*w) for w in d['rows']])
 if mutation:mutation(db)
 db.commit();db.close();p={'records':recs,'source_files':srcs,'envelopes':envs,'expected':{'documents':3,'raw_source_bytes_read':sum(x['bytes'] for x in srcs),'UTF8_bytes':sum(x['bytes'] for x in envs),'characters':sum(x['characters'] for x in envs),'all_windows':sum(1+(len(t)+1023)//1024 for t in texts)}};return path,p
with tempfile.TemporaryDirectory() as z:
 root=Path(z);path,p=fixture(root);v=core.verify_sql(path,p,lambda:None);assert v['stats']['documents']==3 and v['stats']['skipped']==4 and v['stats']['language_pass']==2 and v['one_EOS_per_raw_envelope_separate']==3;N+=1
 mutations=[lambda d:d.execute('DELETE FROM docs WHERE ordinal=1'),lambda d:d.execute('DELETE FROM windows WHERE doc=0 AND ordinal=1'),lambda d:d.execute('UPDATE docs SET ebook_ID=999 WHERE ordinal=1'),lambda d:d.execute('UPDATE docs SET text_SHA256=zeroblob(32) WHERE ordinal=1'),lambda d:d.execute('UPDATE windows SET start=1 WHERE doc=0 AND ordinal=1'),lambda d:d.execute('UPDATE windows SET kind=0 WHERE doc=0 AND ordinal=1'),lambda d:d.execute('UPDATE windows SET scored=1 WHERE doc=1 AND ordinal=1'),lambda d:d.execute("UPDATE windows SET raw_probability='0.1' WHERE doc=0 AND ordinal=0"),lambda d:d.execute('UPDATE windows SET policy_pass=0 WHERE doc=0 AND ordinal=0'),lambda d:d.execute('UPDATE docs SET min_english=0.1 WHERE ordinal=0'),lambda d:d.execute('UPDATE docs SET EOS_separate=0 WHERE ordinal=0'),lambda d:d.execute('UPDATE docs SET prediction_logical_lines_SHA256=zeroblob(32) WHERE ordinal=0'),lambda d:d.execute("UPDATE windows SET skip_reason='wrong' WHERE scored=0"),lambda d:d.execute('UPDATE windows SET alphabetics=1025 WHERE doc=0 AND ordinal=1')]
 for j,mut in enumerate(mutations):
  folder=root/str(j);folder.mkdir();path,p=fixture(folder,mut);must(lambda:core.verify_sql(path,p,lambda:None))
 for line in ['__label__en nan','__label__en inf','__label__en -0.1','__label__en 1.01','english 0.8','__label__en 0.9\n'] :must(lambda line=line:core.prediction(line))
 assert core.prediction('__label__en 0.8')[-1]==1 and core.prediction('__label__en 0.7999')[-1]==0 and core.prediction('__label__fr 1.0')[-2:]==(0.,0);N+=1
 # External actual shape bound, still synthetic files and fixed fake PID absence.
 folder=root/'whole';folder.mkdir();path,producer=fixture(folder);summary=core.verify_sql(path,producer,lambda:None);(folder/'screening.sqlite-journal').write_bytes(b'journal')
 result={'status':'COMPLETE_PG300_ENVELOPE_M1_LANGUAGE_PROVISIONAL_NO_ADMISSION','profile_SHA256':core.P,'codepins_SHA256':core.C,**{k:summary[k] for k in ['stats','one_EOS_per_raw_envelope_separate','raw_content_plus_EOS','distinct_envelope_SHA_diagnostic']},'artifacts':{}}
 own={'profile_SHA256':core.P,'codepins_SHA256':core.C,'supervisor_PID':42966,'worker_PID':42967};(folder/'ownership.json').write_text(json.dumps(own));result['artifacts']={n:{'bytes':(folder/n).stat().st_size,'SHA256':hashlib.sha256((folder/n).read_bytes()).hexdigest()} for n in ['ownership.json','screening.sqlite','screening.sqlite-journal']};(folder/'result.json').write_text(json.dumps(result))
 sup={'status':'COMPLETE_PG300_ENVELOPE_DIAGNOSTICS_NO_ADMISSION','worker_exit_code':0,'result_SHA256':hashlib.sha256((folder/'result.json').read_bytes()).hexdigest(),'elapsed_seconds':1,'peak_observed_RSS_bytes':1,'all_output_bytes':0};(folder/'supervisor.json').write_text(json.dumps(sup))
 # all_output_bytes contains supervisor itself: converge its short JSON length.
 for _ in range(4):sup['all_output_bytes']=sum(f.stat().st_size for f in folder.iterdir());(folder/'supervisor.json').write_text(json.dumps(sup))
 pp=root/'producer.json';pp.write_text(json.dumps(producer));profile={'source_output':str(folder),'producer_profile':str(pp),'producer_profile_SHA256':core.P,'producer_codepins_SHA256':core.C,'expected_supervisor_PID':42966,'expected_worker_PID':42967};bp=root/'binding.json';binding={'producer_reaped':True,'exec_exit_code':0,'exec_session':22400,'owned_PIDs_absent':True,'supervisor_PID':42966,'worker_PID':42967,'profile_SHA256':core.P,'codepins_SHA256':core.C,'artifacts':{f.name:{'path':str(f),'bytes':f.stat().st_size,'SHA256':hashlib.sha256(f.read_bytes()).hexdigest(),'dev_ino_size_mtime_ns_ctime_ns':core.ident(f)} for f in folder.iterdir()}}
 def bind(b):bp.write_text(json.dumps(b));profile['terminal_binding_path']=str(bp);profile['terminal_binding_SHA256']=hashlib.sha256(bp.read_bytes()).hexdigest()
 def absent(*a):raise ProcessLookupError
 bind(binding)
 with patch.object(core.os,'kill',absent):
  assert core.run(profile,root,lambda:None)['stats']['documents']==3;N+=1
  for field,value in [('producer_reaped',False),('exec_exit_code',1),('owned_PIDs_absent',False),('profile_SHA256','x'*64),('worker_PID',42)]:
   bad=copy.deepcopy(binding);bad[field]=value;bind(bad);must(lambda:core.gate(profile,str(bp),profile['terminal_binding_SHA256']))
 bind(binding)
 with patch.object(core.os,'kill',lambda *a:None):must(lambda:core.gate(profile,str(bp),profile['terminal_binding_SHA256']))
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY_STORED_SQL_AND_COMPLETE_RUN','controls':N,'source_or_actual_producer_SQL_reads':0,'detector_tokenizer_inference':0}))
