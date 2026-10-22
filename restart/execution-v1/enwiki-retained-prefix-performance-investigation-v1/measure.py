"""Synthetic exact sink comparisons; no retained source or live-output reads."""
from pathlib import Path
import importlib.util,sqlite3,tempfile,time,json,hashlib,os
BASE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('original_sink',BASE/'enwiki-compact-SQLite-sink-preparation-v2/sink.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Buffered(m.Sink):
 def begin_group(self,*args):
  super().begin_group(*args);self.pending=[]
 def revision(self,rid,pid,ordinal):
  g=self.group
  if pid!=g['expected'][g['seen']][0] or ordinal!=len(self.pending)+1 or len(self.pending)>=10000:raise ValueError('synthetic_pending_bound')
  self.pending.append((rid,pid,ordinal))
 def page(self,record,title):
  # Reuse production page validation, but no deferred child exists at its INSERT.
  g=self.group;g['page_revs']=len(self.pending);g['first_rev']=self.pending[0][0] if self.pending else None;g['revs']+=len(self.pending)
  super().page(record,title)
  for values in self.pending:self.db.execute('INSERT INTO revisions VALUES(?,?,?)',values)
  self.pending=[]
def run(kind,n):
 with tempfile.TemporaryDirectory() as t:
  path=Path(t)/'db.sqlite';sink=(Buffered if kind=='PAGE_FIRST_CURRENT_PAGE_BUFFER' else m.Sink)(path)
  if kind=='CHILD_PAGE_INDEX_COMPARISON_ONLY':sink.db.execute('CREATE INDEX revisions_by_page ON revisions(page_ordinal)');sink.db.commit()
  started=time.monotonic();last=started
  for g in range(n//100):
   expected=[(g*100+i+1,g*100+i+100,'Synthetic') for i in range(100)];sink.begin_group(g+1,g*100,g*100+100,expected)
   for i,(ordinal,pid,title) in enumerate(expected):
    rid=ordinal+1000000;sink.revision(rid,ordinal,1)
    record=dict(zip(m.FIELDS,(ordinal,pid,rid,0,0,0,1,0,i*2,1,b'x'*32)));sink.page(record,title)
   sink.end_group(200,b'y'*32)
   if g==n//100-11:last=time.monotonic()
  elapsed=time.monotonic()-started;last10=time.monotonic()-last
  assert sink.db.execute('PRAGMA integrity_check').fetchone()==('ok',) and sink.db.execute('PRAGMA foreign_key_check').fetchone() is None
  assert sink.db.execute('SELECT count(*) FROM pages').fetchone()[0]==n and sink.db.execute('SELECT count(*) FROM revisions').fetchone()[0]==n
  size=path.stat().st_size;sink.close();return {'kind':kind,'pages':n,'groups':n//100,'seconds':elapsed,'last10groups_seconds':last10,'DB_bytes':size,'integrity_FK_counts_PASS':True}
results=[run(kind,n) for n in [5000,10000,20000] for kind in ['UNCHANGED_PRODUCTION_DEFERRED_CHILD_FIRST','CHILD_PAGE_INDEX_COMPARISON_ONLY','PAGE_FIRST_CURRENT_PAGE_BUFFER']]
print(json.dumps({'status':'SYNTHETIC_ONLY_PRODUCTION_VS_TWO_DIAGNOSTIC_VARIANTS','results':results,'notes':['Buffered is an isolated benchmark prototype, not a full validated production replacement.','No retained native/source/index/live output read; temporary databases removed.','All variants same atomic100pagegroups; integrity/FK/counts checked.']},indent=2))
