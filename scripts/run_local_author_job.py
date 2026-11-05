"""Resumable public model download followed by local-only dialogue generation.

No remote inference, training, content review or evaluation. Downloads use public
HTTP byte ranges and a pinned publisher SHA-256. Does not modify student weights.
"""
import concurrent.futures,hashlib,json,os,subprocess,sys,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/local-author-v1';REPORT=ROOT/'reports/local-author-v1'
def write(p,o):
 p=Path(p);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(o,indent=2)+'\n');os.replace(tmp,p)
def main():
 import fcntl
 lock=(RUN/'supervisor.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 cfg=json.loads((ROOT/'configs/local_author_v1.json').read_text());meta=json.loads((REPORT/'teacher-files.json').read_text());modeldir=ROOT/cfg['teacher_local_path']
 assert meta['revision']==cfg['teacher_revision'];state={'pid':os.getpid(),'status':'downloading_model','started_at':time.time(),'target':10000,'training_started':False,'evaluation_started':False,'quality_review_started':False,'paid_api_calls':0}
 def status(**kw):state.update(updated_at=time.time(),**kw);write(RUN/'job.json',state)
 for weight in meta['weights']:
  destination=modeldir/weight['name']
  if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest()==weight['sha256']:continue
  size=weight['size'];chunk=8*2**20;parts=RUN/'download-parts';parts.mkdir(exist_ok=True)
  total=(size+chunk-1)//chunk
  def fetch(i):
   start=i*chunk;end=min(size,start+chunk)-1;n=end-start+1;p=parts/f'{i:05d}.part'
   if p.exists() and p.stat().st_size==n:return n
   for retry in range(5):
    if (RUN/'STOP').exists():raise RuntimeError('Stop requested')
    try:
     url=f'https://huggingface.co/{cfg["teacher_repo"]}/resolve/{cfg["teacher_revision"]}/{weight["name"]}?download=true&part={i}'
     req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}','Accept-Encoding':'identity'})
     with urllib.request.urlopen(req,timeout=90) as response:
      if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{size}':raise RuntimeError('Server did not honor byte range')
      temp=p.with_suffix('.tmp');count=0
      with temp.open('wb') as f:
       while True:
        b=response.read(min(1024*1024,n-count+1))
        if not b:break
        count+=len(b)
        if count>n:raise RuntimeError('Oversized range response')
        f.write(b)
       f.flush();os.fsync(f.fileno())
      if count!=n:raise RuntimeError('Incomplete range response')
     os.replace(temp,p);return n
    except Exception as e:
     if retry==4:raise RuntimeError(f'Chunk {i}: {type(e).__name__}') from None
     time.sleep(min(2**retry,16))
  done=sum(p.stat().st_size for p in parts.glob('*.part'));status(download_bytes=done,download_total_bytes=size)
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
   jobs={pool.submit(fetch,i):i for i in range(total)}
   for future in concurrent.futures.as_completed(jobs):
    future.result();done=sum(p.stat().st_size for p in parts.glob('*.part'));status(download_bytes=done,download_total_bytes=size)
    print(f'download {done}/{size}',flush=True)
  temp=destination.with_suffix('.tmp');h=hashlib.sha256()
  with temp.open('wb') as out:
   for i in range(total):
    with (parts/f'{i:05d}.part').open('rb') as f:
     while b:=f.read(2**20):h.update(b);out.write(b)
   out.flush();os.fsync(out.fileno())
  assert temp.stat().st_size==size and h.hexdigest()==weight['sha256'],'Publisher SHA mismatch'
  os.replace(temp,destination)
  # Remove only assembled temporary chunks; final model and receipts remain.
  for p in parts.glob('*.part'):p.unlink()
 write(RUN/'download.json',{'model':cfg['teacher_repo'],'revision':cfg['teacher_revision'],'path':str(modeldir),'status':'downloaded','transport':'verified_public_http_ranges'})
 env=dict(os.environ,HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
 cmd=[str(RUN/'env/bin/python'),str(ROOT/'scripts/author_conversations_local.py')]
 if (RUN/'status.json').exists():cmd.append('--resume')
 if (RUN/'STOP').exists():status(status='stopped');return
 child=subprocess.Popen(cmd,cwd=ROOT,env=env);status(status='generating',child_pid=child.pid)
 rc=child.wait();status(status='generation_complete_awaiting_review' if rc==0 else 'generation_stopped_or_failed',child_exit_code=rc)
 if rc:raise SystemExit(rc)
if __name__=='__main__':
 try:main()
 except Exception as e:
  p=RUN/'job.json';state=json.loads(p.read_text()) if p.exists() else {};state.update(status='failed',error=type(e).__name__+': '+str(e),updated_at=time.time());write(p,state);raise
