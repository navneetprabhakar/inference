"""Old/new storage equivalence and actual parent-first rollback/performance controls."""
import importlib.util,time,json,tempfile,sqlite3,sys,hashlib
from pathlib import Path
import sink
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('old',BASE/'enwiki-compact-SQLite-sink-preparation-v2/sink.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
N=0
def rec(n,pid,rids,start=0):return dict(zip(sink.FIELDS,(n,pid,rids[0] if rids else None,0,0,1,len(rids),3,start,20,hashlib.sha256(str(n).encode()).digest())))
def run(cls,path,n):
 s=cls(path);t=time.monotonic()
 for group in range(n//100):
  s.begin_group(group+1,group*10,group*10+10,[(group*100+i+1,group*100+i+1,'Same title') for i in range(100)])
  for i in range(100):
   ordinal=group*100+i+1;rids=[] if ordinal%11==0 else [777,777] if ordinal%7==0 else [ordinal+1000000]
   for j,rid in enumerate(rids,1):s.revision(rid,ordinal,j)
   s.page(rec(ordinal,ordinal,rids,i*20),'Same title')
  s.end_group(2000,b'x'*32)
 elapsed=time.monotonic()-t
 rows={t:s.db.execute('SELECT * FROM '+t+' ORDER BY '+('revision_id,page_ordinal,revision_ordinal' if t=='revisions' else 'row_ordinal' if t=='pages' else 'group_ordinal')).fetchall() for t in ['pages','revisions','groups']}
 assert s.db.execute('PRAGMA foreign_keys').fetchone()==(1,);assert s.db.execute('PRAGMA integrity_check').fetchall()==[('ok',)];assert not s.db.execute('PRAGMA foreign_key_check').fetchall();s.close();return elapsed,rows
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp);a,ar=run(old.Sink,root/'old.sqlite',5000);b,br=run(sink.Sink,root/'new.sqlite',5000);assert ar==br;N+=4
 s=sink.Sink(root/'order.sqlite');s.begin_group(1,0,10,[(1,1,'A')]);s.revision(99,1,1);assert s.db.execute('SELECT count(*) FROM revisions').fetchone()==(0,);N+=1
 trace=[];s.db.set_trace_callback(trace.append);s.page(rec(1,1,[99]),'A');assert next(i for i,q in enumerate(trace) if q.startswith('INSERT INTO pages'))<next(i for i,q in enumerate(trace) if q.startswith('INSERT INTO revisions'));N+=1
 s.end_group(20,b'x'*32);s.begin_group(2,10,20,[(2,2,'B')]);s.revision(100,2,1)
 s.db.set_authorizer(lambda action,name,*args:sqlite3.SQLITE_DENY if action==sqlite3.SQLITE_INSERT and name=='revisions' else sqlite3.SQLITE_OK)
 try:s.page(rec(2,2,[100]),'B')
 except sqlite3.DatabaseError:pass
 else:raise AssertionError('child_write_fault_expected')
 s.db.set_authorizer(None);assert s.failed and s.db.execute('SELECT row_ordinal FROM pages').fetchall()==[(1,)] and s.db.execute('SELECT revision_id FROM revisions').fetchall()==[(99,)];assert not s.group['pending_revisions'];N+=1;s.close()
 s=sink.Sink(root/'bound.sqlite');s.begin_group(1,0,10,[(1,1,'A')])
 for i in range(10000):s.revision(88,1,i+1)
 pending=s.group['pending_revisions'];peakbuffer=sys.getsizeof(pending)+sum(sys.getsizeof(v)+sum(sys.getsizeof(z) for z in v) for v in pending);assert len(pending)==10000 and s.db.execute('SELECT count(*) FROM revisions').fetchone()==(0,);N+=1
 s.page(rec(1,1,[88]*10000),'A');assert len(pending)==0;s.end_group(20,b'x'*32);assert s.db.execute('SELECT count(*) FROM revisions').fetchone()==(10000,);N+=1;s.close()
 s=sink.Sink(root/'overflow.sqlite');s.begin_group(1,0,10,[(1,1,'A')])
 for i in range(10000):s.revision(88,1,i+1)
 try:s.revision(88,1,10001)
 except ValueError:pass
 else:raise AssertionError('per_page_bound_expected')
 assert s.failed and not s.group['pending_revisions'] and s.db.execute('SELECT count(*) FROM pages').fetchone()==(0,);N+=1;s.close()
 s=sink.Sink(root/'full.sqlite',DB_cap=65536);s.begin_group(1,0,10,[(1,1,'A')])
 for i in range(10000):s.revision(i+1,1,i+1)
 try:s.page(rec(1,1,list(range(1,10001))),'A')
 except sqlite3.DatabaseError:pass
 else:raise AssertionError('SQLite_FULL_expected')
 assert s.failed and s.db.execute('SELECT count(*) FROM pages').fetchone()==(0,) and s.db.execute('SELECT count(*) FROM revisions').fetchone()==(0,);N+=1;s.close()
 assert sink.SCHEMA==old.SCHEMA;N+=1
 print(json.dumps({'status':'PASS_SYNTHETIC_ONLY_OLD_NEW_METADATA_EQUIVALENT','controls':N,'comparison_pages':5000,'old_seconds':a,'new_seconds':b,'schema_PK_FK_unchanged':True,'current_page_max_revisions':10000,'measured_max_current_page_buffer_bytes':peakbuffer,'source_or_live_output_reads':0},indent=2))
