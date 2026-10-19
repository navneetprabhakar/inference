# Creator: Navneet Prabhakar
import json
import sqlite3
import pytest
from slm.data.facet_near import FacetStore
from slm.data.near_audit import require_terminal,verify_source_mappings,verify_feature_index,verify_prefix_counts,verify_near_pairs


def fixture(tmp_path):
    source=sqlite3.connect(':memory:');source.execute('CREATE TABLE records(sid INTEGER,data TEXT)')
    text=' '.join('originalword'+str(i) for i in range(100));other=text.replace('originalword50','changed')
    source.executemany('INSERT INTO records VALUES(?,?)',[(0,json.dumps(dict(texts=dict(content=text,short='blue'),candidate=False))),(1,json.dumps(dict(texts=dict(seed=other),candidate=True)))])
    store=FacetStore(tmp_path/'db',max_bytes=16*1024**2,max_facets=10,max_features=10000,max_shingles=1000)
    a=store.insert_facet(0,'content',text);b=store.insert_facet(1,'seed',other);store.group(10000)
    return source,store,a,b


def test_actual_full_source_and_reference_checks(tmp_path):
    source,s,a,b=fixture(tmp_path)
    assert verify_source_mappings(source,s.db)==dict(records=2,facet_references=2,excluded_short_facets=1)
    assert verify_feature_index(s.db)['unique_raw_facets']==2
    assert verify_prefix_counts(s.db)==2 and verify_near_pairs(s.db)==1
    s.db.close();source.close()


def test_live_job_refused_without_opening_database(tmp_path):
    with pytest.raises(ValueError,match='before opening'):require_terminal(tmp_path)


def test_missing_noncandidate_witness_mapping_rejected(tmp_path):
    source,s,a,b=fixture(tmp_path);s.db.execute('DELETE FROM facet_sources WHERE source_sid=0')
    with pytest.raises(ValueError,match='coverage'):verify_source_mappings(source,s.db)
    s.db.close();source.close()


def test_corrupt_feature_count_and_wrong_posting_rejected(tmp_path):
    source,s,a,b=fixture(tmp_path);s.db.execute('UPDATE counts SET n=n+1 WHERE sid=?',(a,))
    with pytest.raises(ValueError,match='count'):verify_feature_index(s.db)
    s.db.execute('UPDATE counts SET n=n-1 WHERE sid=?',(a,))
    s.db.execute('UPDATE dictionary SET feat=? WHERE fid=(SELECT min(fid) FROM dictionary)',(b'x'*32,))
    with pytest.raises(ValueError,match='shingles'):verify_feature_index(s.db)
    s.db.close();source.close()


def test_false_near_pair_cannot_pass_threshold(tmp_path):
    source,s,a,b=fixture(tmp_path);c=s.insert_facet(2,'content','Entirely separate words with different content and unrelated reference tokens.')
    s.db.execute('INSERT INTO near_pairs VALUES(?,?)',(a,c))
    with pytest.raises(ValueError,match='threshold'):verify_near_pairs(s.db)
    s.db.close();source.close()
