# Creator: Navneet Prabhakar
from itertools import combinations
import random
import pytest
from slm.data.curation import shingles
from slm.data.schema import digest
from slm.data.prefix_near import PrefixStore,prefix_length


def test_fixed_arbitrary_and_sampled_orders_equal_full_brute_force(tmp_path):
    rng=random.Random(20);texts=[]
    for family in range(4):
        base=[f'family{family}word{i}' for i in range(100)]
        for changes in (0,1,2,3,6,12):
            words=list(base)
            for pos in rng.sample(range(100),changes):words[pos]='replacement'+str(pos)
            texts.append(' '.join(words))
    values=[shingles(t) for t in texts]
    orders=[{}, {bytes.fromhex(digest(v)):rng.randrange(1,9) for v in values[0]}]
    for arm,order in enumerate(orders):
        s=PrefixStore(tmp_path/str(arm),order,cache_kib=2048)
        ids=[s.insert_facet(i,'text',t) for i,t in enumerate(texts)]
        expected={tuple(sorted((ids[i],ids[j]))) for i,j in combinations(range(len(texts)),2)
                  if 20*len(values[i]&values[j])>=17*len(values[i]|values[j])}
        assert expected and set(s.db.execute('SELECT a,b FROM near_pairs'))==expected
        assert s.postings==sum(prefix_length(len(v)) for v in values)
        assert s.postings<s.features//3
        s.close()


def test_exact_aliases_keep_every_source_and_raw_text(tmp_path):
    s=PrefixStore(tmp_path/'db',{},cache_kib=2048);text='  Here is an exact source passage.\n'
    assert s.insert_facet(0,'text',text)==s.insert_facet(1,'seed',text)
    assert s.facets==1 and s.db.execute('SELECT count(*) FROM facet_sources').fetchone()[0]==2
    assert s.db.execute('SELECT data FROM records').fetchone()[0]==text
    s.close()
    with pytest.raises(FileExistsError):PrefixStore(tmp_path/'db',{})


def test_caps_refuse_without_truncation_or_partial_success(tmp_path):
    s=PrefixStore(tmp_path/'features',{},max_shingles=1,cache_kib=2048)
    with pytest.raises(ValueError,match='cap'):s.insert_facet(0,'text','one two three four five six seven')
    assert s.facets==0;s.close()
    s=PrefixStore(tmp_path/'pairs',{},max_pairs=0,cache_kib=2048)
    base=' '.join('word'+str(i) for i in range(150));s.insert_facet(0,'text',base)
    with pytest.raises(ValueError,match='pair cap'):s.insert_facet(1,'text',base+' suffix')
    assert s.db.execute('SELECT count(*) FROM near_pairs').fetchone()[0]==0;s.close()


def test_small_sets_punctuation_and_stream_counts(tmp_path):
    s=PrefixStore(tmp_path/'db',{},cache_kib=2048)
    texts=['one two three four','one TWO three four','One two three, four.','Different text stays separate here.']
    ids=[s.insert_facet(i,'text',t) for i,t in enumerate(texts)]
    assert (ids[0],ids[1]) in set(s.db.execute('SELECT a,b FROM near_pairs'))
    assert s.features*32==(s.root/'full-shingles.bin').stat().st_size
    for sid,n,offset in s.db.execute('SELECT sid,n,offset FROM records'):
        s.file.seek(offset);assert len(s.file.read(32*n))==32*n
    s.close()


def test_asymmetric_sizes_and_exact_threshold_in_arbitrary_insertion_order(tmp_path):
    words=['token'+str(i) for i in range(104)]
    texts=[' '.join(words+['extra'+str(i) for i in range(17)]),
           ' '.join(words[15:]),' '.join(words),' '.join(words[16:]),
           ' '.join(words+['extra'+str(i) for i in range(18)])]
    values=[shingles(t) for t in texts];s=PrefixStore(tmp_path/'db',{},cache_kib=2048)
    ids=[s.insert_facet(i,'text',t) for i,t in enumerate(texts)]
    expected={(ids[i],ids[j]) for i,j in combinations(range(len(texts)),2)
              if 20*len(values[i]&values[j])>=17*len(values[i]|values[j])}
    assert (ids[1],ids[2]) in expected and (ids[2],ids[3]) not in expected
    assert set(s.db.execute('SELECT a,b FROM near_pairs'))==expected
    s.close()
