# Creator: Navneet Prabhakar
from slm.data.prefix_near_fast import FastPrefixStore
from slm.data.conversation_grouping import Query,facets
from slm.data.curation import shingles

def test_readonly_complete_matches(tmp_path):
    texts=['A quiet orange cat sits beside the window and watches birds fly past the old garden wall.', 'A quiet orange cat sits beside the window and watches birds fly past the old garden fence.', 'A completely unrelated topic about baking bread with warm water and fresh yeast.']
    index=FastPrefixStore(tmp_path/'index',{},max_facets=10,max_features=1000,max_pairs=100,max_db_bytes=1048576)
    for i,t in enumerate(texts):index.insert_facet(i,'text',t)
    index.close();before=(tmp_path/'index/near.sqlite').read_bytes()
    q=Query(tmp_path/'index',{})
    for text in texts:
        expected={i+1 for i,t in enumerate(texts) if 20*len(shingles(text)&shingles(t))>=17*len(shingles(text)|shingles(t))}
        assert set(q.matches(text))==expected
    q.close();assert before==(tmp_path/'index/near.sqlite').read_bytes()

def test_facets_protect_whole_and_individual_messages():
    m=[dict(role='user',content='Please explain how birds build nests.'),dict(role='assistant',content='Birds gather twigs and weave them together.')]
    assert set(facets(m))=={'0','1','dialogue'}
