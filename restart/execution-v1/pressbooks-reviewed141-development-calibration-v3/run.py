"""Exact frozen141 development-only detector calibration. No full-source pass."""
import signal,time
START=time.clock_gettime(time.CLOCK_MONOTONIC)
signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('30second_calibration')))
signal.setitimer(signal.ITIMER_REAL,30)
import hashlib,json,os,stat,sys,subprocess,collections
from pathlib import Path
HERE=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def load_module(name,path):
 import importlib.util
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def read_exact(p,expected,cap):
 p=Path(p);s=p.stat(follow_symlinks=False)
 assert stat.S_ISREG(s.st_mode) and not p.is_symlink() and s.st_size<=cap
 sig=lambda z:(z.st_dev,z.st_ino,z.st_size,z.st_mtime_ns,z.st_ctime_ns)
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  assert sig(os.fstat(fd))==sig(s)
  with os.fdopen(fd,'rb',closefd=False) as f:r=f.read(cap+1)
  assert len(r)<=cap and sha(r)==expected
  assert sig(os.fstat(fd))==sig(s)==sig(p.stat(follow_symlinks=False))
 finally:os.close(fd)
 return r

def main():
 profile=Path(sys.argv[1]);assert sha(profile.read_bytes())==sys.argv[2]
 p=json.loads(profile.read_text());assert len(p['records'])==141 and p['text_bytes']<=2000000
 for path,h in p['pins'].items():assert sha(Path(path).read_bytes())==h,path
 structural=load_module('structural',p['structural']);component=load_module('component',p['component'])
 rows=[];total=0
 for x in p['records']:
  assert time.clock_gettime(time.CLOCK_MONOTONIC)-START<28
  raw=read_exact(x['text_path'],x['text_SHA256'],2000000);total+=len(raw);assert total<=2000000
  source=read_exact(x['JSON_path'],x['source_JSON_SHA256'],2500000)
  text=raw.decode('utf8','strict');assert json.loads(source)['text']==text
  s=structural.assess(text);c=component.detect_components(text,{k:x[k] for k in ['source_id','ordinal','text_SHA256','source_JSON_SHA256']})
  rows.append({'identity':{k:x[k] for k in ['source_id','ordinal','text_SHA256','source_JSON_SHA256']},'original_review':x['review'],'structural':s,'components':c})
 out=HERE/'results.json';assert not out.exists()
 result={'status':'COMPLETE_DEVELOPMENT_CALIBRATION_ONLY','count':len(rows),'text_bytes':total,'rows':rows,'source_body_transformations':0,'new_admissions':0,'whole_source_pass':False,'elapsed_seconds':time.clock_gettime(time.CLOCK_MONOTONIC)-START}
 b=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode();assert len(b)<=7500000
 with out.open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
 print(json.dumps({'status':result['status'],'count':len(rows),'text_bytes':total,'results_SHA256':sha(b),'output_bytes':len(b),'elapsed_seconds':result['elapsed_seconds']}))
if __name__=='__main__':main()
