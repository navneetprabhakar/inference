# Creator: Navneet Prabhakar
import shutil,sqlite3
from slm.data.prefix_near import PrefixStore
from slm.data.prefix_near_fast import FastPrefixStore

def test_fast_lookup_recall_and_resumed_copy_match_original(tmp_path):
 texts=[' '.join('word'+str(i) for i in range(150))+suffix for suffix in ['', ' extra',' other',' completely different']]
 old=PrefixStore(tmp_path/'old',{},cache_kib=2048)
 for i,t in enumerate(texts):old.insert_facet(i,'content',t)
 gold=list(old.db.execute('SELECT a,b FROM near_pairs ORDER BY a,b'));old.close()
 fast=FastPrefixStore(tmp_path/'fast',{},cache_kib=2048)
 for i,t in enumerate(texts[:2]):fast.insert_facet(i,'content',t)
 fast.close();shutil.copytree(tmp_path/'fast',tmp_path/'copy')
 with (tmp_path/'copy/full-shingles.bin').open('ab') as f:f.write(b'preserved-only-in-original-orphan-tail')
 s=FastPrefixStore.resume_copy(tmp_path/'copy',{},max_facets=100,max_features=10000,max_pairs=10000,max_db_bytes=1048576)
 for i,t in enumerate(texts[2:],2):s.insert_facet(i,'content',t)
 assert list(s.db.execute('SELECT a,b FROM near_pairs ORDER BY a,b'))==gold
 assert s.pairs==6;s.close()

def test_candidate_lookup_plan_does_not_scan_full_record_table(tmp_path):
 s=FastPrefixStore(tmp_path/'plan',{},cache_kib=2048)
 p=list(s.db.execute('EXPLAIN QUERY PLAN SELECT r.sid,r.n,r.offset,r.data FROM candidates c CROSS JOIN records r ON r.sid=c.sid ORDER BY c.sid'))
 assert any('SCAN c' in r[3] for r in p) and not any('SCAN r' in r[3] for r in p)
 s.close()
