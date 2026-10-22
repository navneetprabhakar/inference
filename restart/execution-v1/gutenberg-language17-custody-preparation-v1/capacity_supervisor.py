from pathlib import Path
import sys,time,subprocess,os,signal,json,hashlib
HERE=Path(__file__).resolve().parent
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 pin=json.loads((HERE/'capacity-input-pins.json').read_text())
 for name,h in pin['files'].items():assert H(Path(name))==h
 results=[];start=time.monotonic()
 for label,extra in [('old4',['--old4']),('all17',[])]:
  child=None;peak=0;case=time.monotonic()
  try:
   with (HERE/f'capacity-{label}.json').open('xb') as log:child=subprocess.Popen([sys.executable,'-I','-B',str(HERE/'capacity.py'),'--worker']+extra,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   while child.poll() is None:
    if time.monotonic()-case>45:raise TimeoutError('capacity45seconds')
    ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],text=True,capture_output=True,check=True,timeout=1);rows={}
    for line in ps.stdout.splitlines():
     if not line.strip():continue
     f=line.split()
     if len(f)!=3 or any(not x.isdecimal() for x in f):raise ValueError('RSS_snapshot')
     pid,parent,rss=map(int,f)
     if pid in rows:raise ValueError('RSS_duplicate')
     rows[pid]=(parent,rss)
    owned={os.getpid()}
    if os.getpid() not in rows:raise ValueError('RSS_missing_supervisor')
    while True:
     n=owned|{p for p,(q,r) in rows.items() if q in owned}
     if n==owned:break
     owned=n
    peak=max(peak,sum(rows[p][1]*1024 for p in owned))
    if peak>1000000000:raise ValueError('synthetic_tree_RSS1GB')
    time.sleep(.05)
   child.wait(timeout=3);assert child.returncode==0
   payload=json.loads((HERE/f'capacity-{label}.json').read_text());assert payload['source_last_candidate_late_containment_retained'];results.append({'case':label,'observed_peak_tree_RSS_bytes':peak,'worker':payload,'elapsed_seconds':time.monotonic()-case})
  finally:
   if child is not None and child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=3)
 for name,h in pin['files'].items():assert H(Path(name))==h
 (HERE/'capacity-comparison.json').write_text(json.dumps({'status':'COMPLETE_SYNTHETIC_MEMORY_COMPARISON_NO_CORPUS_SCAN','cases':results,'elapsed_seconds':time.monotonic()-start,'inputs_unchanged':True,'actual_retained_corpus_rows_scanned':0},indent=2)+'\n');print(json.dumps(results))
if __name__=='__main__':main()
