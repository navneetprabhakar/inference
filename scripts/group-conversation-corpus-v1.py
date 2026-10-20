"""Finite new-candidate components and conservative old/protected-population exclusion."""
# Creator: Navneet Prabhakar
import collections,json,resource,shutil,sqlite3,struct,time
from pathlib import Path
from slm.data.stream_hash import sha
from slm.data.schema import digest
from slm.data.prose_screen import word_key
from slm.data.exact_families import ExactFamilies
from slm.data.prefix_near_fast import FastPrefixStore
from slm.data.conversation_grouping import Query,facets
ROOT=Path('data/conversation-groups-v1');SCREEN=Path('data/conversation-screen-v1');OLD=Path('data/global-prefix-grouping-v2/index')
def rows(path):
 with Path(path).open() as f:yield from map(json.loads,f)
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 ROOT.mkdir();started=time.monotonic()
 protected=Path('data/conversation-corpus-intake-v1/upstream-test.jsonl');raw=Path('data/conversation-parquet-intake-v3/train.jsonl');ordering=Path('data/prefix-near-benchmark-v1/ordering-counts.bin')
 paths=[SCREEN/'candidates.jsonl',SCREEN/'report.json',protected,raw,ordering,Path(__file__),Path('src/slm/data/conversation_grouping.py'),Path('data/evaluation-exclusions-v3/inventory.json')]
 bindings={str(p):sha(p) for p in paths};oldstats={str(p):(p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ino) for p in OLD.iterdir()}
 order={}
 for chunk in iter(lambda:None,None):pass
 with ordering.open('rb') as f:
  while b:=f.read(36):
   if len(b)!=36:raise ValueError('Incomplete fixed ordering')
   order[b[:32]]=struct.unpack('<I',b[32:])[0]
 candidates=list(rows(SCREEN/'candidates.jsonl'));ids={r['row_index'] for r in candidates};exact=ExactFamilies(ROOT/'families.sqlite',max_records=4000,max_bytes=256*1024**2)
 index=FastPrefixStore(ROOT/'index',order,max_facets=30000,max_features=12000000,max_pairs=2000000,max_db_bytes=2*1024**3,cache_kib=131072)
 def guard():
  if time.monotonic()-started>3600 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>8*1024**3 or shutil.disk_usage(ROOT).free<40*1024**3:raise ValueError('Finite local grouping resource guard')
 for sid,r in enumerate(candidates):
  guard();texts=facets(r['messages']);exact.add(dict(id=str(r['row_index']),ingredient=r['source'],candidate=True,fixed_partition=None,blocked=False,families=[],texts=texts))
  for k,t in texts.items():index.insert_facet(sid,k,t)
  if sid%500==0:print('indexed candidates',sid,flush=True)
 index.commit()
 for a,b in index.db.execute('SELECT a,b FROM near_pairs'):
  aa=[x[0] for x in index.db.execute('SELECT source_sid FROM facet_sources WHERE sid=?',(a,))];bb=[x[0] for x in index.db.execute('SELECT source_sid FROM facet_sources WHERE sid=?',(b,))]
  for x in aa:
   for y in bb:exact.union(x,y,'near','17/20-full-raw-verified')
 # Identical raw facets may be shared across several candidate records.
 for facet, in index.db.execute('SELECT sid FROM facet_sources GROUP BY sid HAVING count(DISTINCT source_sid)>1'):
  sources=[x[0] for x in index.db.execute('SELECT DISTINCT source_sid FROM facet_sources WHERE sid=?',(facet,))]
  for other in sources[1:]:exact.union(sources[0],other,'exact-facet','shared-raw-text')
 index.close();q=Query(ROOT/'index',order,10000000);old=Query(OLD,order,5000000)
 old_exact=sqlite3.connect('file:'+str(Path('data/global-exact-families-v2/families.sqlite').resolve())+'?mode=ro',uri=True)
 blocked=collections.defaultdict(set);witnesses=0
 def block(texts,reason):
  nonlocal witnesses
  for text in texts:
   guard()
   for facet in q.matches(text):
    for sid, in q.db.execute('SELECT source_sid FROM facet_sources WHERE sid=?',(facet,)):blocked[sid].add(reason);witnesses+=1
 for sid,r in enumerate(candidates):
  guard()
  for t in facets(r['messages']).values():
   if old_exact.execute("SELECT 1 FROM anchors WHERE kind='text' AND key=?",(digest(word_key(t)),)).fetchone() or old.matches(t):blocked[sid].add('prior_population_overlap')
  if sid%500==0:print('checked prior population',sid,flush=True)
 for n,r in enumerate(rows(protected)):
  block(facets(r['messages']).values(),'upstream_test_overlap')
  if n%4000==0:print('checked upstream holdouts',n,flush=True)
 for r in rows(raw):
  if r['row_index'] not in ids:block(facets(r['messages']).values(),'screen_rejected_family_overlap')
 for e in json.loads(Path('data/evaluation-exclusions-v3/inventory.json').read_text())['entries']:block([e['text']],'evaluation_overlap')
 for sid,reasons in blocked.items():exact.db.execute('UPDATE records SET blocked=1 WHERE sid=?',(sid,))
 summary=exact.finish();eligible=[];seen=set();blocked_counts=collections.Counter()
 for sid,r in enumerate(candidates):
  root=exact.find(sid);group,fixed,bad,n=exact.db.execute('SELECT group_id,heldout_priority,blocked,members FROM components WHERE root=?',(root,)).fetchone()
  if bad:continue
  if root in seen:continue
  seen.add(root);eligible.append(dict(**r,split_group=group,component_members=n))
 with (ROOT/'eligible.jsonl').open('x') as f:
  for r in eligible:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 with (ROOT/'blocked-witnesses.jsonl').open('x') as f:
  for sid,reasons in sorted(blocked.items()):f.write(json.dumps(dict(row_index=candidates[sid]['row_index'],reasons=sorted(reasons)))+'\n');blocked_counts.update(reasons)
 report=dict(creator='Navneet Prabhakar',complete=True,training_approved=False,**summary,eligible_families=len(eligible),eligible_by_source=dict(collections.Counter(r['source'] for r in eligible)),direct_block_reasons=dict(blocked_counts),query_pairs=q.pairs,old_query_pairs=old.pairs,input_bindings=bindings,eligible_sha256=sha(ROOT/'eligible.jsonl'),elapsed_seconds=time.monotonic()-started,scope='Complete normalized exact and raw-verified17/20 shingle facets; conservative removal of any prior-population overlap and new noncandidate/upstream-test/evaluation-connected components. No semantic/paraphrase/task-template isolation guarantee.')
 q.close();old.close();old_exact.close();exact.close()
 if any(sha(p)!=h for p,h in bindings.items()):raise ValueError('Input changed')
 if any((Path(p).stat().st_size,Path(p).stat().st_mtime_ns,Path(p).stat().st_ino)!=v for p,v in oldstats.items()):raise ValueError('Immutable prior near index changed')
 (ROOT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='input_bindings'},indent=2))
if __name__=='__main__':main()
