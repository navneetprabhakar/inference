"""Article-isolated grounded-QA components; retain unique paragraphs, not question variants."""
# Creator: Navneet Prabhakar
import collections,json,resource,shutil,sqlite3,struct,time
from pathlib import Path
from slm.data.conversation_grouping import Query
from slm.data.curation import shingles
from slm.data.prefix_near_fast import FastPrefixStore
from slm.data.exact_families import ExactFamilies
from slm.data.prose_screen import word_key
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/grounded-qa-groups-v2');CAND=Path('data/grounded-qa-candidates-v1');SOURCE=Path('data/grounded-qa-intake-v1');OLD=Path('data/global-prefix-grouping-v2/index')
def fs(row):return dict(context=row['context'],full_user=row['messages'][0]['content'])
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 ROOT.mkdir();started=time.monotonic();rows=[json.loads(l) for l in (CAND/'candidates.jsonl').open()];order={}
 with Path('data/prefix-near-benchmark-v1/ordering-counts.bin').open('rb') as f:
  while b:=f.read(36):order[b[:32]]=struct.unpack('<I',b[32:])[0]
 new_order=collections.Counter();ordering_features=0
 for r in rows:
  for text in fs(r).values():
   values=shingles(text);ordering_features+=len(values)
   if ordering_features>16000000:raise ValueError('Finite complete ordering feature cap')
   new_order.update(bytes.fromhex(digest(v)) for v in values)
 with (ROOT/'ordering-counts.bin').open('xb') as out:
  for h,n in sorted(new_order.items()):out.write(h+struct.pack('<I',n))
 print('new complete ordering features',ordering_features,'distinct',len(new_order),flush=True)
 bindings={str(p):sha(p) for p in [Path('data/grounded-qa-groups-v1/failure-receipt-v1.json'),ROOT/'ordering-counts.bin',CAND/'candidates.jsonl',CAND/'report.json',SOURCE/'train-v1.1.json',SOURCE/'dev-v1.1.json',Path(__file__),Path('src/slm/data/conversation_grouping.py')]};old_stats={str(p):(p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ino) for p in OLD.iterdir()}
 exact=ExactFamilies(ROOT/'families.sqlite',max_records=22000,max_bytes=512*1024**2);index=FastPrefixStore(ROOT/'index',new_order,max_facets=50000,max_features=16000000,max_pairs=2000000,max_db_bytes=3*1024**3,cache_kib=131072)
 def guard():
  if time.monotonic()-started>3600 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>8*1024**3 or shutil.disk_usage(ROOT).free<40*1024**3:raise ValueError('Finite grounded-grouping resource cap')
 for sid,r in enumerate(rows):
  guard();exact.add(dict(id=r['id'],ingredient=r['source'],candidate=r['official_split']=='train',fixed_partition=None if r['official_split']=='train' else 'test',blocked=False,families=[r['article_family']],texts=fs(r)))
  for k,t in fs(r).items():index.insert_facet(sid,k,t)
  if sid%2000==0:print('indexed grounded rows',sid,flush=True)
 index.commit();paragraph_parent=list(range(len(rows)))
 def find(i):
  while paragraph_parent[i]!=i:paragraph_parent[i]=paragraph_parent[paragraph_parent[i]];i=paragraph_parent[i]
  return i
 def union(a,b):
  a,b=find(a),find(b)
  if a!=b:paragraph_parent[max(a,b)]=min(a,b)
 def link(aa,bb,kind):
  for a in aa:
   for b in bb:exact.union(a,b,kind,'complete-context-or-full-user');union(a,b)
 for a,b in index.db.execute('SELECT a,b FROM near_pairs'):
  aa=[r[0] for r in index.db.execute('SELECT source_sid FROM facet_sources WHERE sid=?',(a,))];bb=[r[0] for r in index.db.execute('SELECT source_sid FROM facet_sources WHERE sid=?',(b,))];link(aa,bb,'near')
 for sid, in index.db.execute('SELECT sid FROM facet_sources GROUP BY sid HAVING count(DISTINCT source_sid)>1'):
  values=[r[0] for r in index.db.execute('SELECT DISTINCT source_sid FROM facet_sources WHERE sid=?',(sid,))];link(values[:1],values[1:],'exact-facet')
 index.close();q=Query(ROOT/'index',new_order,1000000);old=Query(OLD,order,2000000);blocked=collections.defaultdict(set)
 for sid,r in enumerate(rows):
  if r['official_split']=='train':
   for t in fs(r).values():
    guard()
    if old.matches(t):blocked[sid].add('prior_population_overlap')
  if sid%2000==0:print('checked prior grounded rows',sid,flush=True)
 # All official dev paragraphs are protected, including those rejected by the candidate screen.
 dev=json.loads((SOURCE/'dev-v1.1.json').read_text())
 for a in dev['data']:
  for p in a['paragraphs']:
   guard()
   for facet in q.matches(p['context']):
    for sid, in q.db.execute('SELECT source_sid FROM facet_sources WHERE sid=?',(facet,)):blocked[sid].add('full_official_dev_context_overlap')
 for sid in blocked:exact.db.execute('UPDATE records SET blocked=1 WHERE sid=?',(sid,))
 summary=exact.finish();eligible=[];seen=set();members=collections.defaultdict(list)
 for i,r in enumerate(rows):members[find(i)].append(r['id'])
 paragraph_hashes={k:digest(sorted(v)) for k,v in members.items()}
 for sid,r in enumerate(rows):
  group,fixed,bad=exact.db.execute('SELECT group_id,heldout_priority,blocked FROM components WHERE root=?',(exact.find(sid),)).fetchone();paragraph=find(sid)
  if r['official_split']!='train' or fixed or bad or paragraph in seen:continue
  seen.add(paragraph);eligible.append(dict(**r,split_group=group,paragraph_component=paragraph_hashes[paragraph]))
 with (ROOT/'eligible.jsonl').open('x') as f:
  for r in eligible:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 report=dict(creator='Navneet Prabhakar',complete=True,training_approved=False,**summary,eligible_paragraphs=len(eligible),eligible_article_components=len({r['split_group'] for r in eligible}),eligible_articles=len({r['article'] for r in eligible}),blocked_direct_reasons=dict(collections.Counter(reason for rr in blocked.values() for reason in rr)),query_pairs=q.pairs,old_query_pairs=old.pairs,self_join_pairs=index.pairs,prior_failed_pair_reservation=5000000,maximum_cumulative_reserved_pairs=10000000,complete_new_ordering_feature_occurrences=ordering_features,ordering_sha256=sha(ROOT/'ordering-counts.bin'),inputs=bindings,eligible_sha256=sha(ROOT/'eligible.jsonl'),elapsed_seconds=time.monotonic()-started,scope='Original failed fixed-prose ordering retained. New complete candidate-derived rarity order changes retrieval efficiency only; same full text/shingles/exact17-of20 threshold. New total caps self2M+dev1M+prior-query2M plus retained failed5M=10M. Old-index queries keep old order. Whole-context and complete serialized user-prompt exact/17-of20 near families; all paragraphs of article-linked components share partition/nonapproval flags. One representative per near paragraph component, multiple distinct nonoverlapping source paragraphs allowed within an article. Answer-only generic short spans are not independent tasks/facets. Official dev articles/contexts never train; no semantic/paraphrase-family guarantee. Evaluation-exclusion extension and direct review remain required.')
 q.close();old.close();exact.close()
 if any(sha(p)!=h for p,h in bindings.items()) or any((Path(p).stat().st_size,Path(p).stat().st_mtime_ns,Path(p).stat().st_ino)!=v for p,v in old_stats.items()):raise ValueError('Inputs changed')
 (ROOT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='inputs'},indent=2))
if __name__=='__main__':main()
