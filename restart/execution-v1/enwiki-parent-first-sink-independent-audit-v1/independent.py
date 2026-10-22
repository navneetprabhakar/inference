"""Synthetic-only independent table equivalence, FK scan/counter and bound probes."""
import importlib.util,sqlite3,tempfile,json,time,hashlib,sys
from pathlib import Path
B=Path(__file__).resolve().parent.parent
def load(path,name):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
old=load(B/'enwiki-compact-SQLite-sink-preparation-v2/sink.py','old_sink')
new=load(B/'enwiki-compact-SQLite-sink-preparation-v3/sink.py','new_sink')
checks=[]
def ok(v,n):assert v,n;checks.append(n)
def no(fn,n):
 try:fn()
 except (ValueError,sqlite3.Error):checks.append(n);return
 raise AssertionError('expected refusal '+n)
assert old.SCHEMA==new.SCHEMA and old.FIELDS==new.FIELDS
checks.append('exact_schema_and_fields_unchanged')
def rec(mod,o,pid,rev,ns,flags,model,rc,text,a):return dict(zip(mod.FIELDS,(o,pid,rev,ns,flags,model,rc,text,a,1,hashlib.sha256(str(o).encode()).digest())))
def fill(mod,path,n=600,varied=True):
 s=mod.Sink(path);seq=[];started=time.monotonic();ticks=[0]
 s.db.set_progress_handler(lambda:(ticks.__setitem__(0,ticks[0]+1) or 0),1000)
 for g in range(n//100):
  rows=[(g*100+i+1,100000+g*100+i,'Title café & exact') for i in range(100)];s.begin_group(g+1,g*100,(g+1)*100,rows)
  for i,(o,pid,title) in enumerate(rows):
   # Some zero revisions, repeated IDs within and across pages, nonzero/deleted flags.
   ids=[] if varied and o%13==0 else [19,19,o*1234567] if varied and o%7==0 else [2**62+o if varied and o%19==0 else (n-o+1)]
   for j,rid in enumerate(ids,1):s.revision(rid,o,j)
   s.page(rec(mod,o,pid,ids[0] if ids else None,-2 if varied and o%17==0 else 0,2**32-1 if varied and o%23==0 else 0,9 if varied and o%29==0 else 1,len(ids),-1 if varied and o%23==0 else 10,i*2),title)
  s.end_group(200,b'z'*32)
 elapsed=time.monotonic()-started;count=ticks[0]*1000;s.db.set_progress_handler(None,0)
 ok(s.db.execute('PRAGMA integrity_check').fetchone()==('ok',),mod.__name__+'_integrity')
 ok(not s.db.execute('PRAGMA foreign_key_check').fetchall(),mod.__name__+'_FK')
 result={t:s.db.execute(f'SELECT * FROM {t} ORDER BY '+{'pages':'row_ordinal','groups':'group_ordinal','revisions':'revision_id,page_ordinal,revision_ordinal'}[t]).fetchall() for t in ['pages','groups','revisions']}
 schema=s.db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall();size=path.stat().st_size
 s.close();return result,schema,{'pages':n,'seconds':elapsed,'approx_VM_steps_1000granularity':count,'DB_bytes':size}
with tempfile.TemporaryDirectory() as d:
 p=Path(d);a,sa,pa=fill(old,p/'old');b,sb,pb=fill(new,p/'new');ok(a==b,'all_exact_page_group_revision_values_same');ok(sa==sb,'SQL_schema_indexes_FK_identical')
 # Parent buffer is per current page only; valid commit and atomic invalid group.
 s=new.Sink(p/'atomic');s.begin_group(1,0,10,[(1,101,'one')]);s.revision(7,1,1);ok(s.db.execute('SELECT count(*) FROM revisions').fetchone()[0]==0,'unvalidated_revision_only_buffered');s.page(rec(new,1,101,7,0,0,1,1,0,0),'one');ok(s.db.execute('SELECT count(*) FROM revisions').fetchone()[0]==1,'validated_parent_flushes_revision');ok(not s.group['pending_revisions'],'per_page_buffer_freed');s.end_group(1,b'x'*32)
 s.begin_group(2,10,20,[(2,102,'two'),(3,103,'three')]);s.revision(7,2,1);s.page(rec(new,2,102,7,0,0,1,1,0,0),'two');s.revision(8,3,1);no(lambda:s.page(rec(new,3,103,8,0,0,1,1,0,1),'WRONG'),'bad_title_aborts_entire_group');ok(s.db.execute('SELECT count(*) FROM pages').fetchone()[0]==1 and s.db.execute('SELECT count(*) FROM revisions').fetchone()[0]==1,'previous_commit_only_survives');ok(not s.group['pending_revisions'],'abort_frees_page_buffer');no(lambda:s.revision(9,3,2),'failed_sink_terminal');s.close()
 s=new.Sink(p/'cap');s.begin_group(1,0,1,[(1,101,'one')]);
 for j in range(1,10001):s.revision(j,1,j)
 ok(len(s.group['pending_revisions'])==10000,'exact_10000_currentpage_bound');no(lambda:s.revision(10001,1,10001),'revision10001_refused');ok(not s.group['pending_revisions'],'oversize_abort_frees_buffer');ok(s.db.execute('SELECT count(*) FROM revisions').fetchone()[0]==0,'oversize_leaves_no_persisted_children');s.close()
 # Opcode existence unchanged; zero deferred-counter branch is the mechanism.
 s=new.Sink(p/'explain');s.begin_group(1,0,1,[(1,101,'x')]);vm=s.db.execute('EXPLAIN INSERT INTO pages VALUES (?,?,?,?,?,?,?,?,?,?,?)',tuple(rec(new,1,101,7,0,0,1,1,0,0).values())).fetchall();s.close()
 plans=[{'addr':r[0],'opcode':r[1],'p1':r[2],'p2':r[3],'p3':r[4],'p4':r[5]} for r in vm if r[1] in ['FkIfZero','FkCounter','Rewind','Next','OpenRead']]
 metrics=[]
 for n in [2000,4000]:
  for m in [old,new]:
   _,_,x=fill(m,p/(m.__name__+str(n)),n,False);x['variant']=m.__name__;metrics.append(x)
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','independent_controls':checks,'equivalence_600_pages':{'old':pa,'new':pb},'parent_insert_FK_opcodes':plans,'scaling':metrics,'interpretation':'Schema/EXPLAIN can retain FK-child-scan opcode. Parent-first means zero outstanding deferred FK violations so SQLite can bypass that scan; actual VM-step scaling, not opcode disappearance, is measured. Synthetic throughput is not a guarantee for retained bz2/SAX/filesystem work.','retained_source_or_live_output_reads':0},indent=2))
