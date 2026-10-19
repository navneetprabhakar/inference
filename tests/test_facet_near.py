# Creator: Navneet Prabhakar
from itertools import combinations
import pytest
from slm.data.curation import shingles
from slm.data.facet_near import FacetStore


def store(tmp_path,**changes):
    args=dict(max_bytes=16*1024**2,max_facets=100,max_features=10000,max_shingles=1000);args.update(changes)
    return FacetStore(tmp_path/'db',**args)


def test_complete_prefix_pairs_equal_brute_force_full_shingles(tmp_path):
    s=store(tmp_path);base=' '.join('word'+str(i) for i in range(160))
    texts=[base,base.replace('word80','changed'),base+' extra',base.replace('word80','changed').replace('word5','new'), ' '.join('other'+str(i) for i in range(160))]
    ids=[s.insert_facet(i,'content',text) for i,text in enumerate(texts)]
    expected=set()
    for a,b in combinations(range(len(texts)),2):
        x,y=shingles(texts[a]),shingles(texts[b])
        if 20*len(x&y)>=17*len(x|y):expected.add(tuple(sorted((ids[a],ids[b]))))
    s.group(10000)
    assert set(s.db.execute('SELECT a,b FROM near_pairs'))==expected
    assert len(expected)>=3
    s.db.close()


def test_identical_raw_facet_maps_to_all_sources_without_rewriting(tmp_path):
    s=store(tmp_path);text='  A complete source passage.\n'
    a=s.insert_facet(0,'content',text);b=s.insert_facet(1,'seed',text)
    assert a==b and s.facets==1
    assert s.db.execute('SELECT data FROM records').fetchone()[0]==text
    assert s.db.execute('SELECT count(*) FROM facet_sources').fetchone()[0]==2
    s.db.close()


def test_caps_refuse_without_truncation_or_reusing_database(tmp_path):
    s=store(tmp_path,max_shingles=1)
    with pytest.raises(ValueError):s.insert_facet(0,'content','one two three four five six seven')
    assert s.db.execute('SELECT count(*) FROM records').fetchone()[0]==0
    s.db.close()
    with pytest.raises(FileExistsError):store(tmp_path)


def test_frequency_prefix_join_recall_across_many_mutation_levels(tmp_path):
    import random
    rng=random.Random(19);s=store(tmp_path,max_facets=100,max_features=50000)
    texts=[]
    for family in range(3):
        words=['group'+str(family)+'word'+str(i) for i in range(90)]
        for changes in (0,1,2,4,8,16):
            copy=list(words)
            for position in rng.sample(range(90),changes):copy[position]='replacement'+str(position)
            texts.append(' '.join(copy))
    ids=[s.insert_facet(i,'field',text) for i,text in enumerate(texts)]
    values=[shingles(t) for t in texts];expected=set()
    for i,j in combinations(range(len(texts)),2):
        if 20*len(values[i]&values[j])>=17*len(values[i]|values[j]):expected.add(tuple(sorted((ids[i],ids[j]))))
    s.group(100000)
    assert set(s.db.execute('SELECT a,b FROM near_pairs'))==expected
    assert expected and len(expected)<len(texts)*(len(texts)-1)//2
    s.db.close()
