"""Disk staging preserves the independent reference curator and fails closed."""
from dataclasses import asdict, replace
import json
import random
import subprocess
import sys
import pytest
from slm.data.schema import Source, make_example
from slm.data.curation import curate
from slm.data.build import verify
from slm.data.staging import stage, Store
from slm.data.tokenized import sha

LIMITS=dict(max_input_bytes=64*1024*1024,max_records=20000,max_record_bytes=100000,
            max_shingles=4096,max_pair_checks=100000,max_db_bytes=256*1024*1024)


def setup(tmp_path):
    (tmp_path/'card').write_text('Synthetic test source. No training clearance.')
    (tmp_path/'license').write_text('Synthetic fixture only.')
    src=Source('fixture','a'*40,'https://example.org/fixture','fixture',sha(tmp_path/'license'),sha(tmp_path/'card'),('fixture',))
    (tmp_path/'source.json').write_text(json.dumps({**asdict(src),'evidence_files':dict(card='card',license='license')}))
    return src


def item(src,key,prompt=None,answer='A useful answer.',**kw):
    return make_example(src,str(key),str(key),[dict(role='user',content=prompt or f'Question number {key}?'),dict(role='assistant',content=answer)],language='en',**kw)


def spec(tmp_path,records,name='input'):
    path=tmp_path/(name+'.jsonl');path.write_text(''.join(json.dumps(x.to_dict())+'\n' for x in records))
    return dict(path=str(path),sha256=sha(path),source_record=str(tmp_path/'source.json'),adapter='canonical')


def read(root):
    return [json.loads(line) for p in sorted(root.glob('*.jsonl')) for line in p.read_text().splitlines()]


def test_reference_parity_and_input_order(tmp_path):
    src=setup(tmp_path)
    base=' '.join(f'word{i}' for i in range(100))
    records=[item(src,'a',base),item(src,'b',base+' extra',official_split='test'),
             item(src,'c',base,answer='Different response.'),item(src,'d','Separate request'),
             item(src,'e','Separate request',official_split='train'),item(src,'z','Other topic')]
    expected,report=curate(records,{src.source_id:src})
    for n,seq in enumerate((records,list(reversed(records)))):
        out=tmp_path/f'out{n}';r=stage([spec(tmp_path,seq)],out,limits=LIMITS,shard_size=1)
        verify(out)
        assert read(out)==[e.to_dict() for e in expected]
        assert r['near_pairs_grouped']==report['near_pairs_grouped']
        assert r['training_eligible'] is False and r['source_rights_approved'] is False
        assert len(list(out.glob('*.jsonl')))==len(expected)


def test_prefix_matches_bruteforce_random_and_boundary(tmp_path):
    # Independent set oracle; directly seed features to cover arbitrary set systems,
    # including exact threshold (intersection 17, union 20) and unequal lengths.
    import hashlib
    rng=random.Random(91)
    sets=[set(range(17)),set(range(20)),set(range(16)),set(range(18))]
    for _ in range(120):
        common=set(rng.sample(range(60),rng.randint(1,35)))
        sets.extend([common,common|{rng.randrange(60)}])
    src=setup(tmp_path);store=Store(tmp_path/'test.sqlite',LIMITS['max_db_bytes'])
    try:
        from collections import Counter
        for i in range(len(sets)):store.insert(item(src,i),0,False,4096)
        store.db.execute('DELETE FROM features');store.db.execute('DELETE FROM counts');store.db.execute('DELETE FROM dictionary')
        frequency=Counter(v for values in sets for v in values)
        for v,n in frequency.items():
            store.db.execute('INSERT INTO dictionary(feat,n_full,n_prompt) VALUES(?,?,0)',(hashlib.sha256(str(v).encode()).digest(),n))
        ids={feat:fid for fid,feat in store.db.execute('SELECT fid,feat FROM dictionary')}
        for i,values in enumerate(sets):
            sid=i+1
            store.db.execute('INSERT INTO counts VALUES(?,?,?)',(sid,0,len(values)))
            store.db.executemany('INSERT INTO features VALUES(?,?,?)',((0,ids[hashlib.sha256(str(v).encode()).digest()],sid) for v in values))
        store.db.commit();store.group(100000)
        expected={(i+1,j+1) for i,a in enumerate(sets) for j,b in enumerate(sets) if j>i and len(a&b)/len(a|b)>=.85}
        actual=set(store.db.execute('SELECT a,b FROM near_pairs'))
        assert actual==expected
    finally:store.db.close()


@pytest.mark.parametrize('field,value', [('max_input_bytes',1),('max_records',1),('max_record_bytes',10),('max_shingles',1),('max_pair_checks',1)])
def test_limits_remove_partial_output(tmp_path,field,value):
    src=setup(tmp_path);records=[item(src,i,'Same question') for i in range(4)]
    limits={**LIMITS,field:value};out=tmp_path/'out'
    with pytest.raises(ValueError):stage([spec(tmp_path,records)],out,limits=limits)
    assert not out.exists() and not list(tmp_path.glob('.corpus-stage-*'))


def test_database_limit_removes_partial_output(tmp_path):
    src=setup(tmp_path)
    records=[item(src,i,' '.join(f'unique{i}term{j}' for j in range(300))) for i in range(40)]
    out=tmp_path/'out'
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError):stage([spec(tmp_path,records)],out,limits={**LIMITS,'max_db_bytes':1024*1024})
    assert not out.exists() and not list(tmp_path.glob('.corpus-stage-*'))


def test_duplicate_rejected_id_fails(tmp_path):
    src=setup(tmp_path);bad=item(src,1,'password=fixture-secret')
    with pytest.raises(ValueError,match='Duplicate'):stage([spec(tmp_path,[bad,bad])],tmp_path/'out',limits=LIMITS)


def test_pinned_input_and_evidence(tmp_path):
    src=setup(tmp_path);s=spec(tmp_path,[item(src,1)])
    s['sha256']='0'*64
    with pytest.raises(ValueError,match='checksum'):stage([s],tmp_path/'out',limits=LIMITS)
    s['sha256']=sha(s['path']);(tmp_path/'license').write_text('changed')
    with pytest.raises(ValueError,match='evidence checksum'):stage([s],tmp_path/'out',limits=LIMITS)


def test_frozen_holdout_and_immutable_record(tmp_path):
    src=setup(tmp_path);old=item(src,'old','A protected question',official_split='validation')
    frozen=tmp_path/'frozen';stage([spec(tmp_path,[old])],frozen,limits=LIMITS)
    newer=item(src,'new','A protected question',answer='Another answer.',official_split='test')
    out=tmp_path/'out';stage([spec(tmp_path,[old,newer])],out,limits=LIMITS,frozen_dataset=frozen)
    assert len(read(out))==2 and {r['split'] for r in read(out)}=={'test'}
    assert set(json.loads((out/'heldout-groups.json').read_text()).values())=={'test'}
    with pytest.raises(ValueError,match='Frozen example changed'):
        stage([spec(tmp_path,[replace(old,messages=newer.messages)])],tmp_path/'bad',limits=LIMITS,frozen_dataset=frozen)


def test_cli_spec_relative_paths(tmp_path):
    src=setup(tmp_path);s=spec(tmp_path,[item(src,1)])
    s['path']='input.jsonl';s['source_record']='source.json'
    settings=tmp_path/'spec.json';settings.write_text(json.dumps(dict(inputs=[s],limits=LIMITS)))
    out=tmp_path/'out'
    result=subprocess.run([sys.executable,'-m','slm.data.staging','--spec',str(settings),'--output',str(out)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['training_eligible'] is False
    verify(out)


def test_sample_staging_is_refused_by_training_reader(tmp_path):
    from slm.data.review import training_examples
    src=setup(tmp_path);out=tmp_path/'out';stage([spec(tmp_path,[item(src,1)])],out,limits=LIMITS)
    with pytest.raises(ValueError):list(training_examples(out))


def test_input_mutation_aborts_publication(tmp_path,monkeypatch):
    import slm.data.staging as module
    src=setup(tmp_path);s=spec(tmp_path,[item(src,1)]);original=module.clean
    def mutate(value):
        from pathlib import Path
        with Path(s['path']).open('a') as f:f.write('\n')
        return original(value)
    monkeypatch.setattr(module,'clean',mutate)
    with pytest.raises(ValueError,match='changed'):stage([s],tmp_path/'out',limits=LIMITS)
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.corpus-stage-*'))


def test_oasst_requires_projection(tmp_path):
    src=setup(tmp_path);s=spec(tmp_path,[item(src,1)]);s['adapter']='oasst'
    with pytest.raises(ValueError,match='projection'):stage([s],tmp_path/'out',limits=LIMITS)


def test_frozen_invalid_replacement_and_repeated_incoming_ids_fail(tmp_path):
    src=setup(tmp_path);old=item(src,'old','A protected question',official_split='test')
    frozen=tmp_path/'frozen';stage([spec(tmp_path,[old])],frozen,limits=LIMITS)
    bad=replace(old,messages=[dict(role='user',content='password=synthetic-secret'),dict(role='assistant',content='ok')])
    with pytest.raises(ValueError,match='cannot be dropped'):stage([spec(tmp_path,[bad])],tmp_path/'bad',limits=LIMITS,frozen_dataset=frozen)
    with pytest.raises(ValueError,match='Duplicate'):stage([spec(tmp_path,[old,old])],tmp_path/'double',limits=LIMITS,frozen_dataset=frozen)


def test_code_stamp_change_aborts_publication(tmp_path,monkeypatch):
    from pathlib import Path
    import slm.data.staging as module
    src=setup(tmp_path);s=spec(tmp_path,[item(src,1)]);original=module.stamp;seen=0
    def changed(path):
        nonlocal seen
        value=original(path)
        if Path(path).resolve()==Path(module.__file__).resolve():
            seen+=1
            if seen>1:return ('changed',)
        return value
    monkeypatch.setattr(module,'stamp',changed)
    with pytest.raises(ValueError,match='changed'):stage([s],tmp_path/'out',limits=LIMITS)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('adapter,raw',[
    ('prose',[dict(text='First English paragraph.'),dict(text='Second unrelated paragraph.')]),
    ('messages',[dict(messages=[dict(role='user',content='Hello'),dict(role='assistant',content='Hi')]),dict(messages=[dict(role='user',content='Goodbye'),dict(role='assistant',content='Bye')])]),
    ('dolly',[dict(instruction='Extract',context='Name: Maya',response='Maya'),dict(instruction='Add',context='2 and 3',response='5')])])
def test_streaming_adapters_preserve_reference_identity(tmp_path,adapter,raw):
    from slm.data.adapters import rows
    src=setup(tmp_path);path=tmp_path/'raw.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in raw))
    s=dict(path=str(path),sha256=sha(path),source_record=str(tmp_path/'source.json'),adapter=adapter)
    expected,_=curate(rows(src,raw,adapter),{src.source_id:src})
    out=tmp_path/'out';stage([s],out,limits=LIMITS)
    assert read(out)==[e.to_dict() for e in expected]


def test_interning_preserves_hashes_memberships_and_separate_frequencies(tmp_path):
    from collections import Counter
    from slm.data.curation import clean,key_text,shingles
    from slm.data.schema import digest
    src=setup(tmp_path)
    records=[item(src,'a','one two three four five six seven','eight nine ten eleven twelve'),
             item(src,'b','eight nine ten eleven twelve','one two three four five six seven'),
             item(src,'c','one two three four five six seven','An entirely different response.')]
    expected=Counter();memberships={};store=Store(tmp_path/'interning.sqlite',LIMITS['max_db_bytes'])
    try:
        for record in records:
            record=clean(record);sid=store.insert(record,0,False,4096)
            for kind,text in ((0,key_text(record)),(1,record.messages[0]['content'])):
                values={bytes.fromhex(digest(v)) for v in shingles(text)}
                memberships[sid,kind]=values;expected.update((kind,v) for v in values)
        actual={}
        for fid,feat,full,prompt in store.db.execute('SELECT fid,feat,n_full,n_prompt FROM dictionary'):
            assert len(feat)==32
            if full:actual[0,feat]=full
            if prompt:actual[1,feat]=prompt
        assert actual==dict(expected)
        assert store.db.execute('SELECT count(*) FROM dictionary').fetchone()[0]==len({v for _,v in expected})
        assert any(actual.get((0,v),0)!=n for (kind,v),n in actual.items() if kind==1)
        for (sid,kind),wanted in memberships.items():
            found={r[0] for r in store.db.execute('SELECT d.feat FROM features f JOIN dictionary d ON d.fid=f.fid WHERE f.sid=? AND f.kind=?',(sid,kind))}
            assert found==wanted
        store.usage();assert store.scratch_peak>0
    finally:store.db.close()
