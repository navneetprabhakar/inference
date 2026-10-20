# Creator: Navneet Prabhakar
from collections import Counter
from slm.data.curation import shingles
from slm.data.schema import digest
from slm.data.prefix_near_fast import FastPrefixStore
from slm.data.conversation_grouping import Query

def test_new_order_preserves_raw_near_threshold(tmp_path):
    a=' '.join('word'+str(i) for i in range(100))
    texts=[a,a.replace('word99','different_end'),' '.join('other'+str(i) for i in range(100))]
    order=Counter(bytes.fromhex(digest(s)) for t in texts for s in shingles(t))
    store=FastPrefixStore(tmp_path/'index',order,max_facets=10,max_features=1000,max_pairs=100,max_db_bytes=1048576)
    for i,t in enumerate(texts):store.insert_facet(i,'full',t)
    store.close();q=Query(tmp_path/'index',order)
    assert set(q.matches(a))=={1,2}
    assert set(q.matches(texts[2]))=={3}
    assert set(q.matches(texts[1]))=={1,2}
    q.close()
