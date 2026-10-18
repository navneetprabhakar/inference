from dataclasses import replace, asdict
import hashlib
import json
import pytest
from slm.data.schema import Source, make_example, digest
from slm.data.adapters import rows, trees
from slm.data.curation import curate, clean
from slm.data.build import build, verify, read_source


def source(name='fixture'):
    return Source(name,'a'*40,'https://example.org/source','fixture-license','b'*64,'c'*64,('fixture',))


def example(key, prompt='Hello', answer='Hi', group=None, split=None, src=None):
    return make_example(src or source(),key,group or key,
        [{'role':'user','content':prompt},{'role':'assistant','content':answer}],
        language='en',official_split=split)


def test_source_must_be_pinned():
    with pytest.raises(ValueError): replace(source(),revision='main')
    with pytest.raises(ValueError): replace(source(),license_text_sha256='')
    with pytest.raises(ValueError): replace(source(),review_status='guess')


def test_tree_reconstruction_rank_cap_context_and_no_mutation():
    raw=[dict(message_id='a',parent_id=None,role='prompter',lang='en',text='First question'),
         dict(message_id='b',parent_id='a',role='assistant',lang='en',text='Answer',rank=1),
         dict(message_id='c',parent_id='a',role='assistant',lang='en',text='Better answer',rank=0),
         dict(message_id='d',parent_id='c',role='prompter',lang='en',text='Follow up'),
         dict(message_id='e',parent_id='d',role='assistant',lang='en',text='Follow up answer',rank=0)]
    out=trees(source(),raw,max_paths_per_tree=1)
    assert len(out)==1 and len(out[0].messages)==4
    assert out[0].messages[2]['content']=='Follow up'
    assert out[0].parent_group_id=='fixture:a'
    assert out[0].lineage==['a','c','d','e']
    assert 'messages' not in raw[0]
    with pytest.raises(ValueError,match='missing parent'): trees(source(),raw[1:])
    with pytest.raises(ValueError,match='Cyclic'):
        trees(source(),[dict(raw[0],parent_id='b'),raw[1]])
    raw[2]['lang']='fr'
    assert [x.example_id for x in trees(source(),raw)]==['fixture:b']


def test_source_adapters_preserve_context_and_drop_metadata():
    src=source()
    d=rows(src,[dict(instruction='Extract the name',context='Name: Maya',response='Maya')],'dolly')[0]
    assert 'Name: Maya' in d.messages[0]['content']
    d2=rows(src,[dict(messages=[dict(role='user',content='Yo',ip='private'),
                               dict(role='assistant',content='Hi')],ip='private')],'messages')[0]
    assert d2.messages[0]==dict(role='user',content='Yo')
    assert rows(src,[dict(id='doc',text='A short English text.')],'prose')[0].task=='prose'
    with pytest.raises(ValueError): rows(src,[{}],'unknown')


def test_privacy_filter_preserves_amounts_slang_and_negation():
    item=example('x',"yo don't spend over $100, need 2; email me at forge@example.com; phone: +91 98765 43210")
    result=clean(item)
    prompt=result.messages[0]['content']
    assert "yo don't spend over $100, need 2" in prompt
    assert '[EMAIL]' in prompt and '[PHONE]' in prompt
    assert 'forge@example.com' not in prompt and '98765' not in prompt
    assert 'forge@example.com' in item.messages[0]['content']
    with pytest.raises(ValueError,match='Credential'): clean(example('secret','password=not-a-real-secret'))
    with pytest.raises(ValueError,match='boilerplate'): clean(example('spam','Buy now\n'*10))
    with pytest.raises(ValueError): clean(example('bad','\ufffd'))
    with pytest.raises(ValueError): clean(replace(item,messages=[]))


def test_group_before_split_prevents_cross_source_and_test_leakage():
    a,b=source('a'),source('b')
    records=[example('a','Select the second product','Product 2',src=a),
             example('b','Select the second product','Product 2',split='test',src=b),
             example('c','Select the second product','Different answer',src=a),
             example('d','Switch to terse style','Product 2',group='c',src=a)]
    out,r=curate(records,{'a':a,'b':b})
    assert len(out)==3 and {e.split for e in out}=={'test'}
    assert r['exact_duplicates_removed']==1
    assert 'b:b' in {e.example_id for e in out}
    assert r['heldout_groups']['a:a']=='test'  # removed duplicate's family stays protected
    extension=example('new','A fresh prompt','A fresh answer',group='a',src=a)
    out2,_=curate([extension],{'a':a},frozen_groups=r['heldout_groups'])
    assert out2[0].split=='test'


def test_near_prompt_grouping_retains_changed_semantics_and_transitivity():
    prompt=' '.join(f'word{i}' for i in range(100))
    records=[example('a',prompt,'Yes',split='validation'),
             example('b',prompt.replace('word99','different99'),'No'),
             example('c','Completely different','Second reply',group='b')]
    out,r=curate(records,{'fixture':source()})
    assert len(out)==3 and {e.split for e in out}=={'validation'}
    assert r['near_pairs_grouped']>=1
    assert len({e.validation_results['split_group'] for e in out})==1


def test_determinism_validation_and_training_release_gate():
    records=[example(str(i),f'Question number {i}',f'Reply {i}') for i in range(20)]
    a,r=curate(records,{'fixture':source()}); b,s=curate(records[::-1],{'fixture':source()})
    assert [e.to_dict() for e in a]==[e.to_dict() for e in b] and r==s
    with pytest.raises(ValueError,match='Training release'):
        curate(records,{'fixture':source()},training_release=True)
    with pytest.raises(ValueError,match='Duplicate example'):
        curate([records[0],records[0]],{'fixture':source()})
    with pytest.raises(ValueError,match='provenance'):
        curate([replace(records[0],source_revision='b'*40)],{'fixture':source()})
    with pytest.raises(ValueError,match='Unknown official'):
        curate([replace(records[0],official_split='test_sft')],{'fixture':source()})
    rejected=replace(records[0],language='fr')
    assert curate([rejected],{'fixture':source()})[1]['rejections']=={'declared_non_english':1}
    x=replace(records[0],content_category='sfw')
    approved=replace(source(),review_status='training_approved')
    x.license_record=digest(asdict(approved))
    assert curate([x],{'fixture':approved},training_release=True)[1]['release']=='training'


def test_deterministic_shards_evidence_corruption_and_no_partial_build(tmp_path,monkeypatch):
    card=b'Fixture card'; license_text=b'Fixture license'
    (tmp_path/'card').write_bytes(card); (tmp_path/'license').write_bytes(license_text)
    src=replace(source(),card_sha256=hashlib.sha256(card).hexdigest(),
                license_text_sha256=hashlib.sha256(license_text).hexdigest())
    raw=asdict(src); raw['evidence_files']={'card':'card','license':'license'}
    (tmp_path/'source.json').write_text(json.dumps(raw))
    data=tmp_path/'rows.jsonl'
    data.write_text('\n'.join(json.dumps({'id':str(i),'text':f'The topic {i} has enough prose for this fixture.','language':'en'}) for i in range(5)))
    specs=[dict(path=str(data),source_record=str(tmp_path/'source.json'),adapter='prose')]
    build(specs,tmp_path/'first',shard_size=2); build(specs,tmp_path/'second',shard_size=2)
    assert verify(tmp_path/'first')==verify(tmp_path/'second')
    for p in (tmp_path/'first').iterdir(): assert p.read_bytes()==(tmp_path/'second'/p.name).read_bytes()
    with pytest.raises(FileExistsError): build(specs,tmp_path/'first')
    with (tmp_path/'first/report.json').open('a') as f: f.write('corrupt')
    with pytest.raises(ValueError,match='checksum'): verify(tmp_path/'first')
    (tmp_path/'license').write_text('wrong')
    with pytest.raises(ValueError,match='evidence checksum'): build(specs,tmp_path/'bad')
    assert not (tmp_path/'bad').exists()


def test_official_train_can_have_local_holdout_and_global_families():
    a,b=source('a'),source('b')
    records=[example(str(i),f'item {i}',f'value {i}',split='train',src=a) for i in range(100)]
    out,_=curate(records,{'a':a})
    assert {'train','test','validation'}=={e.split for e in out}
    records=[example('base','Longer original question','Original',group='family:scenario42',split='test',src=a),
             example('style','Different surface form','Different surface reply',group='family:scenario42',src=b)]
    assert {e.split for e in curate(records,{'a':a,'b':b})[0]}=={'test'}


def test_bounded_acquisition_rejects_stale_viewer_and_truncated_cells(tmp_path,monkeypatch):
    import slm.data.acquire as acquisition
    def stale(url):
        return json.dumps({'rows':[]}).encode(),{'X-Revision':'b'*40}
    monkeypatch.setattr(acquisition,'fetch',stale)
    with pytest.raises(ValueError,match='revision differs'):
        acquisition.sample(source(),'default','train',tmp_path/'stale',1)
    assert not (tmp_path/'stale').exists()
    def truncated(url):
        return json.dumps({'rows':[{'row':{},'truncated_cells':['text']}]}).encode(),{'x-revision':'a'*40}
    monkeypatch.setattr(acquisition,'fetch',truncated)
    with pytest.raises(ValueError,match='Truncated'):
        acquisition.sample(source(),'default','train',tmp_path/'truncated',1)
    assert not (tmp_path/'truncated').exists()
    def complete(url):
        return json.dumps({'rows':[{'row':{'text':'A complete row.'},'truncated_cells':[]}]}).encode(),{'x-revision':'a'*40}
    monkeypatch.setattr(acquisition,'fetch',complete)
    report=acquisition.sample(source(),'default','train',tmp_path/'complete',1)
    assert report['rows']==1 and report['pages'][0]['revision']=='a'*40
    with pytest.raises(ValueError): acquisition.sample(source(),'default','train',tmp_path/'large',501)


def test_interrupted_output_leaves_no_partial_snapshot(tmp_path,monkeypatch):
    import slm.data.build as module
    src=source()
    monkeypatch.setattr(module,'read_source',lambda _:src)
    p=tmp_path/'raw';p.write_text(json.dumps(dict(text='Example paragraph'))+'\n')
    def fail(*args): raise OSError('Injected rename failure')
    monkeypatch.setattr(module.os,'rename',fail)
    with pytest.raises(OSError,match='Injected'):
        build([dict(source_record='fixture',path=str(p),adapter='prose')],tmp_path/'output')
    assert not (tmp_path/'output').exists()
    assert not list(tmp_path.glob('.data-build-*'))


def test_frozen_snapshot_blocks_new_source_near_duplicates(tmp_path,monkeypatch):
    import slm.data.build as module
    srcs={'old':source('old'),'new':source('new')}
    monkeypatch.setattr(module,'read_source',lambda key:srcs[key])
    prose=' '.join(f'word{i}' for i in range(100))
    old=tmp_path/'old.jsonl'
    old.write_text(json.dumps(dict(id='original',text=prose))+'\n')
    build([dict(path=str(old),source_record='old',adapter='prose',official_split='test')],tmp_path/'frozen')
    new=tmp_path/'new.jsonl'
    new.write_text(json.dumps(dict(id='copy',text=prose.replace('word99','changed99')))+'\n')
    build([dict(path=str(new),source_record='new',adapter='prose')],tmp_path/'extended',frozen_dataset=tmp_path/'frozen')
    items=[]
    for shard in (tmp_path/'extended').glob('*-*.jsonl'):
        items.extend(json.loads(line) for line in shard.read_text().splitlines())
    assert len(items)==2 and {item['split'] for item in items}=={'test'}
    assert json.loads((tmp_path/'extended/manifest.json').read_text())['frozen_dataset_manifest_sha256']
    old.write_text(json.dumps(dict(id='original',text='Changed the frozen original'))+'\n')
    with pytest.raises(ValueError,match='Frozen example changed'):
        build([dict(path=str(old),source_record='old',adapter='prose')],tmp_path/'changed',frozen_dataset=tmp_path/'frozen')


def test_oasst_public_adapter_rejects_flat_slices_and_requires_nested_export():
    root=dict(message_id='a',text='Question',role='prompter',lang='en',replies=[
        dict(message_id='b',text='Answer',role='assistant',lang='en',replies=[])])
    exported=dict(message_tree_id='a',tree_state='ready_for_export',prompt=root)
    assert rows(source(),[exported],'oasst')[0].lineage==['a','b']
    with pytest.raises(ValueError,match='complete ready-tree'):
        rows(source(),[dict(message_id='a',parent_id=None)],'oasst')
    root['replies'][0].pop('replies')
    with pytest.raises(ValueError,match='explicit'): rows(source(),[exported],'oasst')


def test_gzip_tree_sampler_reads_complete_records_and_bounds_output(tmp_path,monkeypatch):
    import gzip,io
    import slm.data.acquire as acquisition
    data=gzip.compress((json.dumps(dict(tree_state='ready_for_export',prompt={}))+'\n').encode()*3)
    monkeypatch.setattr(acquisition.urllib.request,'urlopen',lambda *a,**k:io.BytesIO(data))
    src=source('OpenAssistant/oasst2')
    r=acquisition.sample_ready_trees(src,tmp_path/'trees',2)
    assert r['rows']==2 and r['raw_response_bytes']==len(data)
    with pytest.raises(ValueError,match='Insufficient complete'):
        acquisition.sample_ready_trees(src,tmp_path/'partial',4)
    assert not (tmp_path/'partial').exists()


def test_exact_dedup_respects_message_boundaries_and_code_whitespace():
    records=[example('a','a\nassistant:b','c'),example('b','a','b\nassistant:c'),
             example('c','Run code','if True:\n  print(1)'),
             example('d','Run code','if True:\nprint(1)')]
    out,r=curate(records,{'fixture':source()})
    assert len(out)==4 and r['exact_duplicates_removed']==0


def test_audit_http_retries_are_bounded_and_do_not_retry_permissions(monkeypatch):
    import urllib.error
    import slm.data.acquire as acquisition
    attempts=[]
    response=object()
    def transient(*args,**kwargs):
        attempts.append(1)
        if len(attempts)<3: raise urllib.error.HTTPError('https://example.org',502,'test',{},None)
        return response
    monkeypatch.setattr(acquisition.urllib.request,'urlopen',transient)
    monkeypatch.setattr(acquisition.time,'sleep',lambda _:None)
    assert acquisition.open_response('https://example.org') is response
    assert len(attempts)==3
    attempts.clear()
    def forbidden(*args,**kwargs):
        attempts.append(1)
        raise urllib.error.HTTPError('https://example.org',403,'test',{},None)
    monkeypatch.setattr(acquisition.urllib.request,'urlopen',forbidden)
    with pytest.raises(urllib.error.HTTPError): acquisition.open_response('https://example.org')
    assert len(attempts)==1


def test_frozen_local_holdout_keeps_identity_when_new_official_train_copies_it():
    old=example('old','Question','Answer')
    new=example('new','Question','Answer',split='train')
    out,r=curate([old,new],{'fixture':source()},frozen_groups={'fixture:old':'test'},
                 frozen_example_ids={'fixture:old'})
    assert len(out)==1 and out[0].example_id=='fixture:old' and out[0].split=='test'


def test_audit_command_refuses_corrupted_cache_before_output(tmp_path,monkeypatch):
    import runpy,sys
    from pathlib import Path
    folder=tmp_path/'cache'/'fixture'
    (folder/'source').mkdir(parents=True);(folder/'sample').mkdir()
    for name in ('card','license'):(folder/'source'/name).write_text(name)
    src=replace(source(),card_sha256=hashlib.sha256(b'card').hexdigest(),
                license_text_sha256=hashlib.sha256(b'license').hexdigest())
    record=asdict(src);record['evidence_files']={'card':'card','license':'license'}
    (folder/'source/source.json').write_text(json.dumps(record))
    (folder/'sample/rows.jsonl').write_text('{}\n')
    (folder/'sample/acquisition.json').write_text(json.dumps(dict(revision=src.revision,rows=1,rows_sha256='wrong')))
    registry=tmp_path/'registry.json'
    registry.write_text(json.dumps([dict(name='fixture',source=asdict(src),sample_count=1)]))
    command=Path(__file__).resolve().parents[1]/'scripts/audit-data.py'
    monkeypatch.setattr(sys,'argv',[str(command),'--registry',str(registry),'--cached-input',str(tmp_path/'cache'),'--output',str(tmp_path/'output')])
    with pytest.raises(ValueError,match='Cached acquisition'):
        runpy.run_path(str(command),run_name='__main__')
    assert not (tmp_path/'output').exists()
