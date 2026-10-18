from dataclasses import asdict
from copy import deepcopy
import hashlib
import json
import pytest
from slm.data.schema import Source, make_example, digest
from slm.data.curation import curate
from slm.data.review import prepare, release, training_examples, check_packet
from slm.data.build import verify


def fixture_snapshot(path):
    path.mkdir()
    src=Source('fixture','a'*40,'https://example.org','fixture','b'*64,'c'*64,('fixture',))
    examples=[make_example(src,str(i),'family:shared' if i<2 else str(i),
               [{'role':'user','content':f'Question {i}'},{'role':'assistant','content':f'Answer {i}'}],
               official_split='test' if i==1 else 'validation' if i==2 else 'train',language='en') for i in range(30)]
    items,_=curate(examples,{'fixture':src})
    for split in ('train','validation','test'):
        selected=[e for e in items if e.split==split]
        if selected:(path/f'{split}-00000.jsonl').write_text(''.join(json.dumps(e.to_dict())+'\n' for e in selected))
    (path/'sources.json').write_text(json.dumps({'fixture':asdict(src)}))
    manifest={'version':1,'release':'sample_only','files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir()}}
    (path/'manifest.json').write_text(json.dumps(manifest))
    return items


def approved_packet(path):
    packet=json.loads(path.read_text())
    packet.update(reviewer='Navneet Prabhakar',human_attestation=True)
    for s in packet['source_reviews'].values():
        s.update(approved=True,terms_reviewed=True,allowed_categories=['sfw'],evidence_note='Synthetic fixture decision; not public-source approval')
    for item in packet['examples'].values():
        item['decision'].update(approved=True,english_verified=True,privacy_verified=True,
            quality_verified=True,content_category='sfw',upstream_partition='train',partition_evidence='Synthetic fixture partition')
    path.write_text(json.dumps(packet))
    return packet


def test_pending_review_never_releases_and_preparation_is_deterministic(tmp_path):
    fixture_snapshot(tmp_path/'input')
    first=tmp_path/'review.json';second=tmp_path/'other.json'
    summary=prepare(tmp_path/'input',first,12);prepare(tmp_path/'input',second,12)
    assert first.read_bytes()==second.read_bytes()
    assert summary['selected']==12 and summary['approved']==0
    packet=json.loads(first.read_text())
    assert packet['human_attestation'] is False and packet['reviewer'] is None
    assert all(e['decision']['approved'] is None for e in packet['examples'].values())
    assert {'train','validation','test'}=={e['record']['split'] for e in packet['examples'].values()}
    with pytest.raises(ValueError,match='human review'): release(tmp_path/'input',first,tmp_path/'out')
    with pytest.raises(ValueError,match='sample-only'): list(training_examples(tmp_path/'input'))
    assert not (tmp_path/'out').exists()


def test_checked_release_yields_only_approved_training_records(tmp_path):
    fixture_snapshot(tmp_path/'input')
    p=tmp_path/'review';prepare(tmp_path/'input',p,30);packet=approved_packet(p)
    packet['examples']['fixture:3']['decision']['approved']=False
    p.write_text(json.dumps(packet))
    report=release(tmp_path/'input',p,tmp_path/'out')
    assert report['approved_examples']==29
    items=list(training_examples(tmp_path/'out'))
    assert items and all(i['split']=='train' and i['language']=='en' and i['content_category']=='sfw' for i in items)
    assert all(i['validation_results']['content_review']=='human_attested' for i in items)
    assert not {'fixture:0','fixture:1','fixture:3'} & {e['example_id'] for e in items}
    assert verify(tmp_path/'out')['parent_dataset_manifest_sha256']==packet['dataset_manifest_sha256']
    with pytest.raises(FileExistsError):release(tmp_path/'input',p,tmp_path/'out')
    for shard in (tmp_path/'out').glob('train-*.jsonl'):
        with shard.open('a') as f:f.write('tampered')
        break
    with pytest.raises(ValueError,match='checksum'):list(training_examples(tmp_path/'out'))


def test_review_cannot_rewrite_content_or_source_and_must_cover_gates(tmp_path):
    fixture_snapshot(tmp_path/'input')
    p=tmp_path/'review';prepare(tmp_path/'input',p,30);packet=approved_packet(p)
    for kind in ('text','source','privacy','category','partition','manifest'):
        bad=deepcopy(packet)
        item=bad['examples']['fixture:3']
        if kind=='text':
            item['record']['messages'][0]['content']='Changed after review'
            item['record_sha256']=digest(item['record'])
        if kind=='source':bad['source_reviews']['fixture']['source_record']['revision']='b'*40
        if kind=='privacy':item['decision']['privacy_verified']=1
        if kind=='category':item['decision']['content_category']='adult_topic'
        if kind=='partition':item['decision']['partition_evidence']=''
        if kind=='manifest':bad['dataset_manifest_sha256']='f'*64
        p.write_text(json.dumps(bad))
        with pytest.raises(ValueError):release(tmp_path/'input',p,tmp_path/kind)
        assert not (tmp_path/kind).exists()


def test_rejected_known_test_item_still_protects_approved_group(tmp_path):
    fixture_snapshot(tmp_path/'input');p=tmp_path/'review'
    prepare(tmp_path/'input',p,30);packet=approved_packet(p)
    records=packet['examples']
    group=records['fixture:2']['record']['validation_results']['split_group']
    records['fixture:3']['record']['validation_results']['split_group']=group
    records['fixture:3']['record_sha256']=digest(records['fixture:3']['record'])
    records['fixture:3']['decision'].update(approved=False,upstream_partition='test')
    sources=json.loads((tmp_path/'input/sources.json').read_text())
    result=check_packet(packet,sources)
    assert result['fixture:2']['split']=='test'


def test_semantic_consumer_rejects_resealed_unapproved_record(tmp_path):
    fixture_snapshot(tmp_path/'input');p=tmp_path/'review';prepare(tmp_path/'input',p,30);approved_packet(p)
    release(tmp_path/'input',p,tmp_path/'out')
    shard=next((tmp_path/'out').glob('train-*.jsonl'))
    rows=[json.loads(line) for line in shard.read_text().splitlines()]
    rows[0]['content_category']='adult_fiction'
    shard.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    manifest=json.loads((tmp_path/'out/manifest.json').read_text())
    manifest['files'][shard.name]=hashlib.sha256(shard.read_bytes()).hexdigest()
    (tmp_path/'out/manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='differ from approved'):list(training_examples(tmp_path/'out'))


def test_interrupted_release_cleans_temporary_output(tmp_path,monkeypatch):
    import slm.data.review as module
    fixture_snapshot(tmp_path/'input');p=tmp_path/'review'
    prepare(tmp_path/'input',p,30);approved_packet(p)
    def fail(*args):raise OSError('Injected publication interruption')
    monkeypatch.setattr(module.os,'rename',fail)
    with pytest.raises(OSError,match='Injected'):release(tmp_path/'input',p,tmp_path/'out')
    assert not (tmp_path/'out').exists()
    assert not list(tmp_path.glob('.review-release-*'))
