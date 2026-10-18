from copy import deepcopy
from dataclasses import asdict,replace
import hashlib
import io
import json
from pathlib import Path
import pytest
pa=pytest.importorskip('pyarrow')
import pyarrow.parquet as pq
from slm.data.schema import Source,digest
from slm.data.partitions import RangeCache,PayloadBudget,acquire_span,join_ready,official_trees,collect,load_mapping,verify_bundle,COLUMNS
from slm.data.adapters import rows
from slm.data.build import build


def tree(root='root'):
    child={'message_id':root+'-answer','message_tree_id':None,'parent_id':root,
        'text':'A complete answer.','role':'assistant','lang':'en','replies':[]}
    return {'message_tree_id':root,'tree_state':'ready_for_export','prompt':{
        'message_id':root,'message_tree_id':None,'parent_id':None,'text':'A complete question?',
        'role':'prompter','lang':'en','replies':[child]}}


def identities(root='root'):
    return [{'message_id':root,'parent_id':None,'message_tree_id':root},
        {'message_id':root+'-answer','parent_id':root,'message_tree_id':root}]


def test_nullable_nested_tree_ids_inherit_outer_root_but_exact_membership_is_required():
    raw=tree();mapped,summary=join_ready([raw],[('validation',identities())])
    assert mapped['root']['split']=='validation' and summary['selected_trees_by_split']=={'validation':1}
    assert raw['prompt']['message_tree_id'] is None
    truncated=deepcopy(raw);truncated['prompt']['replies']=[]
    with pytest.raises(ValueError,match='Complete ready-tree membership'):join_ready([truncated],[('train',identities())])
    wrong=deepcopy(raw);wrong['prompt']['replies'][0]['message_tree_id']='other-root'
    with pytest.raises(ValueError,match='identity differs'):join_ready([wrong],[('train',identities())])
    with pytest.raises(ValueError,match='membership'):join_ready([raw],[('train',identities('different'))])


def test_official_partitions_refuse_cross_tree_leakage_duplicates_or_missing_parents():
    with pytest.raises(ValueError,match='crosses partitions'):
        official_trees([('train',identities()[:1]),('validation',identities()[1:])])
    with pytest.raises(ValueError,match='Duplicate official'):
        official_trees([('train',identities()),('validation',identities())])
    bad=identities();bad[1]['parent_id']='missing'
    with pytest.raises(ValueError,match='missing parent'):official_trees([('train',bad)])
    bad=identities();bad[1]['parent_id']='root-answer'
    with pytest.raises(ValueError,match='cycle'):official_trees([('train',bad)])


def test_sparse_cache_refuses_unplanned_io_and_corrupt_ranges(tmp_path):
    payload=b'abcd';(tmp_path/'range.bin').write_bytes(payload)
    spans=[{'start':0,'size':4,'file':'range.bin','sha256':hashlib.sha256(payload).hexdigest()}]
    r=RangeCache(100,tmp_path,spans);assert r.read(4)==payload
    with pytest.raises(ValueError,match='unacquired'):r.read(1)
    r.seek(0);(tmp_path/'range.bin').write_bytes(b'xxxx')
    with pytest.raises(ValueError,match='checksum'):r.read(4)


@pytest.mark.parametrize('status,range_value,data',[(200,'bytes 0-3/10',b'abcd'),(206,'bytes 4-7/10',b'abcd'),(206,'bytes 0-3/10',b'ab')])
def test_http_ranges_fail_closed_without_full_download(tmp_path,monkeypatch,status,range_value,data):
    import slm.data.partitions as module
    class Response(io.BytesIO):
        def __init__(self):super().__init__(data);self.status=status;self.headers={'Content-Range':range_value}
    monkeypatch.setattr(module.urllib.request,'urlopen',lambda *a,**k:Response())
    with pytest.raises(ValueError):acquire_span('https://example.org/object',10,0,4,tmp_path,PayloadBudget(4))
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError,match='budget'):PayloadBudget(3).reserve(4)


def local_projection_fixture(tmp_path,monkeypatch):
    import slm.data.partitions as module
    source_dir=tmp_path/'source';source_dir.mkdir()
    (source_dir/'card').write_text('Synthetic pinned card');(source_dir/'license').write_text('Synthetic license')
    source=Source('OpenAssistant/oasst2','a'*40,'https://example.org','fixture',
        hashlib.sha256((source_dir/'license').read_bytes()).hexdigest(),
        hashlib.sha256((source_dir/'card').read_bytes()).hexdigest(),('fixture',))
    record=asdict(source);record['evidence_files']={'card':'card','license':'license'}
    (source_dir/'source.json').write_text(json.dumps(record))
    files=[];published=[];blobs={};text_spans=[]
    for split,root in [('train','training-root'),('validation','validation-root')]:
        records=identities(root)
        table=pa.Table.from_pylist([{**r,'text':'DO NOT PROJECT TEXT '+str(i)+'x'*20000} for i,r in enumerate(records)])
        path=tmp_path/f'{split}.parquet';pq.write_table(table,path,compression='NONE',row_group_size=1)
        blob=path.read_bytes();blobs[f'data/{split}.parquet']=blob
        metadata=pq.ParquetFile(path).metadata
        for group in range(metadata.num_row_groups):
            col=metadata.row_group(group).column(3)
            start=min(col.data_page_offset,col.dictionary_page_offset)
            text_spans.append((f'data/{split}.parquet',start,start+col.total_compressed_size))
        spec={'split':split,'path':f'data/{split}.parquet','size':len(blob),'rows':2,'lfs_sha256':hashlib.sha256(blob).hexdigest()}
        files.append(spec);published.append({'path':spec['path'],'size':spec['size'],'lfs':{'oid':spec['lfs_sha256']}})
    config={'source_id':source.source_id,'revision':source.revision,'columns':COLUMNS,'max_range_payload_bytes':1024*1024,'files':files}
    config_path=tmp_path/'registry.json';config_path.write_text(json.dumps(config))
    ready=tmp_path/'ready';ready.mkdir();payload=''.join(json.dumps(tree(root))+'\n' for root in ('training-root','validation-root'))
    (ready/'rows.jsonl').write_text(payload)
    (ready/'acquisition.json').write_text(json.dumps({'source':source.source_id,'revision':source.revision,'rows':2,'rows_sha256':hashlib.sha256(payload.encode()).hexdigest()}))
    calls=[]
    def local_span(url,file_size,start,size,folder,budget):
        key='data/'+url.rsplit('/',1)[1];blob=blobs[key]
        assert file_size==len(blob)
        assert all(not (start<end and start+size>begin) for filename,begin,end in text_spans if filename==key)
        budget.reserve(size);data=blob[start:start+size];name=f'range-{start}-{size}.bin'
        (Path(folder)/name).write_bytes(data);calls.append((key,start,size))
        return {'start':start,'size':size,'file':name,'sha256':hashlib.sha256(data).hexdigest()}
    monkeypatch.setattr(module,'acquire_span',local_span)
    monkeypatch.setattr(module,'fetch',lambda *_:(json.dumps(published).encode(),{}))
    return source_dir/'source.json',source,ready,config_path,calls


def test_real_parquet_projection_join_replay_and_build_preserve_official_holdouts(tmp_path,monkeypatch):
    import slm.data.partitions as module
    source_record,source,ready,config,calls=local_projection_fixture(tmp_path,monkeypatch)
    first=collect(source_record,ready,tmp_path/'map',config)
    assert calls and first['selected_trees_by_split']=={'train':1,'validation':1}
    assert first['full_file_sha256_verified'] is False
    expected=first['bundle_sha256']
    def no_network(*args):raise AssertionError('Cached replay must not perform network reads')
    monkeypatch.setattr(module,'fetch',no_network);monkeypatch.setattr(module,'acquire_span',no_network)
    second=collect(source_record,ready,tmp_path/'replay',config,cache=tmp_path/'map')
    assert second['bundle_sha256']==expected and second['new_range_payload_bytes']==0
    mapping,h=load_mapping(tmp_path/'map',expected,source,hashlib.sha256((ready/'rows.jsonl').read_bytes()).hexdigest())
    examples=rows(source,[tree('training-root'),tree('validation-root')],'oasst',official_partitions=mapping,partition_bundle_sha256=h)
    heldout=next(e for e in examples if e.official_split=='validation')
    assert heldout.validation_results['upstream_mapping']['split']=='validation'
    spec={'source_record':str(source_record),'path':str(ready/'rows.jsonl'),'adapter':'oasst',
        'partition_map':str(tmp_path/'map'),'partition_map_sha256':expected}
    build([spec],tmp_path/'curated')
    result=[]
    for p in (tmp_path/'curated').glob('*-*.jsonl'):result.extend(json.loads(line) for line in p.read_text().splitlines())
    assert next(e for e in result if e['example_id']==heldout.example_id)['split']=='validation'
    assert all(e['split']!='train' for e in result)  # shared prompt joins both roots conservatively
    with pytest.raises(ValueError,match='global split'):
        rows(source,[tree('training-root'),tree('validation-root')],'oasst','train',mapping,h)
    with pytest.raises(ValueError,match='input/source'):
        load_mapping(tmp_path/'map',h,replace(source,revision='b'*40),hashlib.sha256((ready/'rows.jsonl').read_bytes()).hexdigest())
    with pytest.raises(ValueError,match='manifest differs'):load_mapping(tmp_path/'map','0'*64,source,'anything')
    blob=next((tmp_path/'map').rglob('*.bin'));blob.write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='checksum'):verify_bundle(tmp_path/'map')


def test_review_requires_verified_mapping_and_prefills_only_partition_evidence(tmp_path,monkeypatch):
    from slm.data.review import prepare,release,training_examples
    from test_review import approved_packet
    source_record,source,ready,config,_=local_projection_fixture(tmp_path,monkeypatch)
    result=collect(source_record,ready,tmp_path/'map',config)
    base={'source_record':str(source_record),'path':str(ready/'rows.jsonl'),'adapter':'oasst'}
    build([base],tmp_path/'unmapped')
    prepare(tmp_path/'unmapped',tmp_path/'unmapped-review',2);approved_packet(tmp_path/'unmapped-review')
    with pytest.raises(ValueError,match='Verified OASST official mapping'):
        release(tmp_path/'unmapped',tmp_path/'unmapped-review',tmp_path/'unmapped-release')
    assert not (tmp_path/'unmapped-release').exists()
    spec={**base,'partition_map':str(tmp_path/'map'),'partition_map_sha256':result['bundle_sha256']}
    build([spec],tmp_path/'mapped')
    prepare(tmp_path/'mapped',tmp_path/'mapped-review',2)
    pending=json.loads((tmp_path/'mapped-review').read_text())
    assert pending['reviewer'] is None and pending['human_attestation'] is False
    for entry in pending['examples'].values():
        assert entry['decision']['approved'] is None and entry['decision']['english_verified'] is None
        assert entry['decision']['upstream_partition']==entry['record']['official_split']
        assert 'Machine-verified' in entry['decision']['partition_evidence']
    approved_packet(tmp_path/'mapped-review')
    packet=json.loads((tmp_path/'mapped-review').read_text())
    for entry in packet['examples'].values():entry['decision']['upstream_partition']=entry['record']['official_split']
    (tmp_path/'mapped-review').write_text(json.dumps(packet))
    release(tmp_path/'mapped',tmp_path/'mapped-review',tmp_path/'mapped-release')
    assert list(training_examples(tmp_path/'mapped-release'))==[]  # shared family is wholly held out
    for entry in packet['examples'].values():entry['decision']['upstream_partition']='train'
    (tmp_path/'mapped-review').write_text(json.dumps(packet))
    with pytest.raises(ValueError,match='Manual split override'):
        release(tmp_path/'mapped',tmp_path/'mapped-review',tmp_path/'override-release')


def test_cached_upstream_split_and_config_cannot_be_relabelled_as_training(tmp_path):
    from slm.data.acquire import verified_cached_spec
    source_dir=tmp_path/'source';sample=tmp_path/'sample';source_dir.mkdir();sample.mkdir()
    (source_dir/'card').write_bytes(b'card');(source_dir/'license').write_bytes(b'license')
    src=Source('fixture','a'*40,'https://example.org','fixture',
        hashlib.sha256(b'license').hexdigest(),hashlib.sha256(b'card').hexdigest(),('fixture',))
    source=asdict(src);(source_dir/'source.json').write_text(json.dumps({**source,'evidence_files':{'card':'card','license':'license'}}))
    payload=json.dumps({'messages':[{'role':'user','content':'hello'},{'role':'assistant','content':'hi'}]})+'\n'
    (sample/'rows.jsonl').write_text(payload)
    acquisition={'source':src.source_id,'revision':src.revision,'config':'default','split':'test_sft',
        'rows':1,'rows_sha256':hashlib.sha256(payload.encode()).hexdigest()}
    p=sample/'acquisition.json';p.write_text(json.dumps(acquisition))
    item={'source':source,'adapter':'messages','config':'default','upstream_split':'train_sft','sample_count':1}
    with pytest.raises(ValueError,match='config/split'):verified_cached_spec(item,tmp_path)
    item['upstream_split']='test_sft'
    assert verified_cached_spec(item,tmp_path)['official_split']=='test'
    acquisition['config']='wrong-configuration';p.write_text(json.dumps(acquisition))
    with pytest.raises(ValueError,match='config/split'):verified_cached_spec(item,tmp_path)
