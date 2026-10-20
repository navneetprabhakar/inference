"""Explicit indexed-lookup correction on a recovered copy, original deadline retained."""
# Creator: Navneet Prabhakar
import importlib.util,json,os,signal,sqlite3,struct,subprocess,sys,time,shutil
from pathlib import Path
from slm.data.prefix_near_fast import FastPrefixStore,prefix_length
from slm.data.curation import shingles
from slm.data.schema import digest
from slm.data.stream_hash import sha

def save(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True)+'\n')
def base_module():
 spec=importlib.util.spec_from_file_location('immutable_prefix_base','scripts/run-prefix-grouping.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def worker(path):
 p=json.loads(Path(path).read_text());root=Path(p['output']);base=base_module();base.check(p)
 evidence={}
 def factory(index,counts,**limits):
  s=FastPrefixStore.resume_copy(index,counts,max_facets=p['max_facets'],max_features=p['max_features'],max_pairs=p['max_pairs'],max_db_bytes=p['max_database_bytes'])
  # Upper-bound all comparisons from at most256 uncommitted/new-in-progress facets.
  # Replayed committed facets do no work. Unknown prior CPU remains charged by original wall deadline.
  source=sqlite3.connect('file:'+str(Path(p['source']).resolve())+'?mode=ro',uri=True)
  last=s.db.execute('SELECT coalesce(max(source_sid),0) FROM facet_sources').fetchone()[0];lookahead=0;upper=0;seen=set()
  for source_sid,data in source.execute('SELECT sid,data FROM records WHERE sid>=? ORDER BY sid',(last,)):
   for name,text in base.fields(data).items():
    raw=digest(text)
    if raw in seen or s.db.execute('SELECT 1 FROM records WHERE exact=?',(raw,)).fetchone():continue
    hashes={bytes.fromhex(digest(v)) for v in shingles(text)};n=len(hashes);prefix=sorted(hashes,key=lambda h:(counts.get(h,0),h))[:prefix_length(n)]
    s.db.execute('DELETE FROM incoming');s.db.executemany('INSERT INTO incoming VALUES(?)',((h,) for h in prefix))
    count=s.db.execute('SELECT count(DISTINCT r.sid) FROM incoming i CROSS JOIN prefixes x ON x.feat=i.feat CROSS JOIN records r ON r.sid=x.sid WHERE 20*r.n>=17*? AND 17*r.n<=20*?',(n,n)).fetchone()[0]
    upper+=count+lookahead;seen.add(raw);lookahead+=1
    if lookahead==256:break
   if lookahead==256:break
  source.close();s.max_pairs=p['max_pairs']-upper
  if s.pairs>s.max_pairs:raise ValueError('Rollback conservative reservation exhausts original comparison cap')
  evidence.update(committed_facets=s.facets,committed_features=s.features,committed_prefixes=s.postings,committed_candidate_pairs=s.pairs,unknown_rollback_comparison_upper_reservation=upper,lookahead_new_facets=lookahead,last_committed_mapped_source=last,remaining_complete_join_candidate_cap=s.max_pairs,cache_kib=2097152)
  save(root/'resume-accounting.json',evidence);return s
 base.PrefixStore=factory
 base.worker(path)
 r=json.loads((root/'report.json').read_text());save(root/'base-audit-report.json',r)
 r.update(kind='indexed-exact-prefix-copy-resume-v2',resume_accounting=evidence,original_attempt_retained=p['original'],original_deadline_unix=p['deadline_unix'],original_elapsed_seconds=time.time()-p['original_started_unix'],unknown_rollback_cpu_work='Unknown; original absolute wall deadline retained, no refund/reset',query_correction='Candidate-first CROSS JOIN and c.sid order; same identities, order, prefix completeness and raw17/20verification')
 save(root/'report.json',r);print(json.dumps(r),flush=True)

def main():
 path=sys.argv[1]
 if '--worker' in sys.argv:worker(path);return
 p=json.loads(Path(path).read_text());base_module().check(p);root=Path(p['output']);old=Path(p['original'])
 if root.exists():raise FileExistsError('Retain previous copy attempt')
 terminal=json.loads((old/'supervisor-terminal.json').read_text())
 if terminal!=dict(complete=False,error='KeyboardInterrupt',returncode=-9):raise ValueError('Owned original must be authoritatively stopped/reaped')
 if time.time()>=p['deadline_unix']:raise TimeoutError('Original deadline exhausted')
 root.mkdir();(root/'index').mkdir();shutil.copyfile(path,root/'plan.json');shutil.copyfile(__file__,root/'executed-resumer.py');shutil.copyfile('src/slm/data/prefix_near_fast.py',root/'executed-fast-prefix.py')
 for name in ['near.sqlite','near.sqlite-journal','full-shingles.bin']:
  f=old/'index'/name
  if f.exists():subprocess.run(['cp','-c',str(f),str(root/'index'/name)],check=True)
 child=subprocess.Popen([sys.executable,__file__,path,'--worker'],start_new_session=True)
 save(root/'process.json',dict(parent=os.getpid(),child=child.pid,original_deadline_unix=p['deadline_unix']))
 try:
  while child.poll() is None:
   if time.time()>=p['deadline_unix']:raise TimeoutError('Original unchanged full-join deadline')
   if shutil.disk_usage(root).free<p['minimum_free_bytes']:raise ValueError('Free disk reserve')
   size=0
   for d in [old,root]:
    for f in d.rglob('*'):
     try:
      if f.is_file():size+=f.stat().st_size
     except FileNotFoundError:pass
   if size>p['max_work_bytes']:raise ValueError('Combined original/copy work cap')
   sample=subprocess.run(['ps','-p',str(child.pid),'-o','rss='],capture_output=True,text=True)
   rss=sample.stdout.strip()
   if rss and int(rss)*1024>8*1024**3:raise ValueError('New explicit8GiBworkerRSSstop')
   time.sleep(2)
  if child.returncode:raise RuntimeError('Versioned copy worker failed')
  save(root/'supervisor-terminal.json',dict(complete=True,returncode=0))
 except BaseException as e:
  if child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait()
  save(root/'supervisor-terminal.json',dict(complete=False,error=type(e).__name__,returncode=child.returncode));raise
if __name__=='__main__':main()
