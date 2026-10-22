"""Read terminal saved policy metadata only. Does not select records or read raw bodies."""
import sqlite3,json,zlib,hashlib,time,signal,collections
from pathlib import Path
D=Path(__file__).resolve().parent;R=D.parent;DB=R/'m2-intake/pressbooks-full-repaired-filter-impact-v1/candidate.sqlite';B=R/'pressbooks-full-repaired-filter-terminal-parent-binding-v1/binding.json'
clock=lambda:time.clock_gettime(time.CLOCK_MONOTONIC)
start=clock()
def stop(*a):raise TimeoutError('60sec_metadata_reason_inventory')
signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,60)
def ident(p):
 s=p.stat(follow_symlinks=False);return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
assert ident(DB)==json.loads(B.read_text())['files']['candidate.sqlite']['stat'];before=ident(DB)
c=sqlite3.connect(DB.as_uri()+'?mode=ro&immutable=1',uri=True);c.execute('PRAGMA query_only=ON');c.execute('PRAGMA cache_size=-4096');c.execute('PRAGMA mmap_size=0')
sets=collections.Counter();n=0
for h,rawsha,packed,packsha,nb in c.execute('SELECT t.text_SHA256,r.receipt_JSON_SHA256,r.receipt_zlib,r.receipt_zlib_SHA256,t.receipt_JSON_bytes FROM texts t JOIN receipts r USING(text_SHA256) WHERE language_pass=1 AND explicit_known_hold=0 AND generic_mask=0 AND queue_mask=1'):
 assert hashlib.sha256(packed).digest()==packsha
 dec=zlib.decompressobj();raw=dec.decompress(packed,3000001);assert dec.eof and not dec.unused_data and not dec.unconsumed_tail and len(raw)==nb<=3000000 and hashlib.sha256(raw).digest()==rawsha
 o=json.loads(raw);s=o['structural'];v2=s['prior_v2'];v1=v2['prior_v1'];assert not o['component_ancestry_review']['flags'];reasons=tuple(sorted({x['reason'] for g in [v1['context_only_diagnostics'],v2['delta_review_only_signals'],s['pending_dependency_queue']] for x in g}));sets[reasons]+=1;n+=1
assert ident(DB)==before;c.close();signal.setitimer(signal.ITIMER_REAL,0)
x={'status':'METADATA_REASON_INVENTORY_NO_DRAW_NO_BODY_READ','rows':n,'reason_sets':[{'reasons':list(k),'distinct_textSHA':v} for k,v in sorted(sets.items(),key=lambda x:(-x[1],x[0]))],'source_stat':before,'source_SHA256_inherited':json.loads(B.read_text())['files']['candidate.sqlite']['SHA256'],'binding_SHA256':hashlib.sha256(B.read_bytes()).hexdigest(),'elapsed':clock()-start,'source_body_reads':0,'selection_performed':False};(D/'reason-set-inventory.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(x,indent=2))
