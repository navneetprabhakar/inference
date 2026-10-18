"""Explicit-row streaming review parity, rejected-group protection and tamper gates."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from slm.data.review import prepare,release as legacy_release,training_examples
from slm.data.review_stream import export_packet,release,open_checked,DEFAULT_LIMITS
from slm.data.staging import canonical
from slm.data.tokenized import sha
from slm.data.schema import digest
from test_review import fixture_snapshot,approved_packet


def bundle(tmp_path,approved=True):
    dataset=tmp_path/'data';fixture_snapshot(dataset)
    packet=tmp_path/'packet.json';prepare(dataset,packet,30)
    if approved:approved_packet(packet)
    review=tmp_path/'review';export_packet(packet,review)
    return dataset,packet,review


def reseal(root):
    manifest=json.loads((root/'manifest.json').read_text())
    manifest['files']={p.name:sha(p) for p in root.iterdir() if p.name!='manifest.json'}
    (root/'manifest.json').write_text(canonical(manifest))


def write_ledger(review,entries):
    (review/'decisions.jsonl').write_text(''.join(canonical(e)+'\n' for e in entries))
    header=json.loads((review/'header.json').read_text());header['decisions_sha256']=sha(review/'decisions.jsonl')
    (review/'header.json').write_text(canonical(header))


def test_legacy_parity_lookup_and_mutable_return_isolation(tmp_path):
    dataset,packet,review=bundle(tmp_path)
    legacy_release(dataset,packet,tmp_path/'v1');r=release(dataset,review,tmp_path/'v2',limits=DEFAULT_LIMITS,shard_size=2)
    old=list(training_examples(tmp_path/'v1'));new=list(training_examples(tmp_path/'v2'))
    assert r['approved_examples']==30
    for rows in (old,new):
        for row in rows:row['validation_results'].pop('human_review')
    assert new==old and new
    for root in (tmp_path/'v1',tmp_path/'v2'):
        with open_checked(root) as index:
            assert list(index)==[e['example_id'] for e in old]
            key=next(iter(index));value=index[key];value['messages'].clear()
            assert index[key]['messages'] and index.get('missing') is None
            assert index.claim(key) and not index.claim(key)
            index.clear_seen();assert index.claim(key)


def test_pending_conversion_does_not_approve(tmp_path):
    dataset,packet,review=bundle(tmp_path,False);header=json.loads((review/'header.json').read_text())
    assert header['human_attestation'] is False and header['reviewer'] is None
    before=sha(packet)
    with pytest.raises(ValueError,match='human review'):release(dataset,review,tmp_path/'out',limits=DEFAULT_LIMITS)
    assert sha(packet)==before and not (tmp_path/'out').exists()


def test_subset_does_not_approve_unreviewed_snapshot_rows(tmp_path):
    dataset,packet,review=bundle(tmp_path)
    entries=[json.loads(line) for line in (review/'decisions.jsonl').read_text().splitlines()]
    selected=next(e for e in entries if e['record']['split']=='train')
    write_ledger(review,[selected]);out=tmp_path/'out';r=release(dataset,review,out,limits=DEFAULT_LIMITS)
    assert r['approved_examples']==1 and len(list(training_examples(out)))==1


@pytest.mark.parametrize('kind',['duplicate','changed','boolean','privacy','category','scope','hash','membership'])
def test_bad_reviews_fail_before_publication(tmp_path,kind):
    dataset,packet,review=bundle(tmp_path)
    entries=[json.loads(line) for line in (review/'decisions.jsonl').read_text().splitlines()]
    if kind=='duplicate':entries.append(deepcopy(entries[0]))
    if kind=='changed':entries[0]['record']['messages'][0]['content']='Changed';entries[0]['record_sha256']=digest(entries[0]['record'])
    if kind=='boolean':entries[0]['decision']['approved']=1
    if kind=='privacy':entries[0]['decision']['privacy_verified']=False
    if kind=='category':entries[0]['decision']['content_category']='adult_fiction'
    if kind=='membership':entries[0]['record']['example_id']='fixture:missing';entries[0]['record_sha256']=digest(entries[0]['record'])
    write_ledger(review,entries)
    if kind in ('scope','hash'):
        header=json.loads((review/'header.json').read_text());header['scope' if kind=='scope' else 'decisions_sha256']='whole_corpus' if kind=='scope' else '0'*64
        (review/'header.json').write_text(canonical(header))
    with pytest.raises(ValueError):release(dataset,review,tmp_path/'out',limits=DEFAULT_LIMITS)
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.review-stream-*'))


@pytest.mark.parametrize('mode',['content','missing','extra','duplicate','heldout'])
def test_resealed_release_cannot_change_approved_rows(tmp_path,mode):
    dataset,packet,review=bundle(tmp_path);out=tmp_path/'out';release(dataset,review,out,limits=DEFAULT_LIMITS)
    path=next(out.glob('train-*.jsonl'));rows=[json.loads(line) for line in path.read_text().splitlines()]
    if mode=='content':rows[0]['messages'][0]['content']='Invented after review'
    if mode=='missing':rows.pop()
    if mode=='extra':rows.append({**deepcopy(rows[0]),'example_id':'fixture:extra'})
    if mode=='duplicate':rows.append(deepcopy(rows[0]))
    if mode=='heldout':
        other=next(out.glob('test-*.jsonl'));bad=json.loads(other.read_text().splitlines()[0]);bad['split']='train';rows.append(bad)
    path.write_text(''.join(canonical(row)+'\n' for row in rows));reseal(out)
    iterator=training_examples(out)
    with pytest.raises(ValueError):next(iterator)


def test_rejected_entry_can_strengthen_peer_holdout(tmp_path):
    dataset,packet,review=bundle(tmp_path);entries=[json.loads(line) for line in (review/'decisions.jsonl').read_text().splitlines()]
    # Both first family siblings already share test; reviewer test evidence on a
    # rejected same-family entry must still retain protection of approved peer.
    siblings=[e for e in entries if e['record']['parent_group_id']=='family:shared']
    assert len(siblings)==2
    siblings[0]['decision'].update(approved=False,upstream_partition='test')
    write_ledger(review,entries);out=tmp_path/'out';release(dataset,review,out,limits=DEFAULT_LIMITS)
    with open_checked(out) as index:assert all(e['record']['example_id'] not in index for e in siblings)


@pytest.mark.parametrize('field,value',[('max_records',1),('max_record_bytes',20),('max_input_bytes',100)])
def test_limits_abort_without_output(tmp_path,field,value):
    dataset,packet,review=bundle(tmp_path)
    with pytest.raises(ValueError):release(dataset,review,tmp_path/'out',limits={**DEFAULT_LIMITS,field:value})
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.review-stream-*'))


def test_dataset_verification_hashes_shards_without_read_bytes(tmp_path,monkeypatch):
    from slm.data.build import verify
    dataset,packet,review=bundle(tmp_path);original=Path.read_bytes
    def blocked(path):
        if path.suffix=='.jsonl':raise AssertionError('Whole shard materialization')
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',blocked)
    verify(dataset);release(dataset,review,tmp_path/'out',limits=DEFAULT_LIMITS)
    assert list(training_examples(tmp_path/'out'))


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_v2_tokenizer_shards_and_actual_tiny_pilot(tmp_path,backend):
    if backend=='mlx':pytest.importorskip('mlx.core')
    from dataclasses import asdict
    from slm.common.tokenizer import train_release,BPE
    from slm.data.tokenized import build_shards
    from slm.common.config import Config
    from slm.common.training import Recipe
    from slm.train import run
    dataset,packet,review=bundle(tmp_path);out=tmp_path/'out';release(dataset,review,out,limits=DEFAULT_LIMITS)
    tok=tmp_path/'tok';train_release(out,tok,512,max_bytes=100000)
    token_data=tmp_path/'tokens';report=build_shards(out,tok,token_data,'sft',64,256)
    s=dict(version=1,config=Config(vocab_size=BPE.load(tok).vocab_size,max_seq_len=64).to_dict(),recipe=asdict(Recipe()),seed=19,
           tokenizer=str(tok),data=dict(kind='tokens',path=str(token_data),fingerprint=report['dataset_hash']),
           releases={sha(out/'manifest.json'):str(out)},limits=dict(updates=1,processed_positions=10000),
           checkpoint=dict(every_updates=1,keep=2),scope='synthetic_mechanics')
    r=run(s,tmp_path/'attempt',backend=backend,device='cpu' if backend=='torch' else 'default')
    assert r['status']=='update_target_reached' and r['final']['step']==1


def test_tokenizer_identity_and_generator_intake_preserve_legacy_contract(tmp_path,monkeypatch):
    from slm.common import tokenizer
    dataset,packet,review=bundle(tmp_path);out=tmp_path/'out';release(dataset,review,out,limits=DEFAULT_LIMITS)
    examples=list(training_examples(out));original=tokenizer.train_core;calls=[]
    def checked(texts,*args):
        assert not isinstance(texts,(list,tuple))
        values=list(texts);calls.append(values);return original(iter(values),*args)
    monkeypatch.setattr(tokenizer,'train_core',checked)
    report=tokenizer.train_release(out,tmp_path/'tok',512)
    assert report['train_record_identity_sha256']==digest([(e['example_id'],digest(e)) for e in examples])
    assert calls==[[m['content'] for e in examples for m in e['messages']]]


def test_database_limit_rolls_back_and_cleans_up(tmp_path):
    import sqlite3
    dataset=tmp_path/'data';fixture_snapshot(dataset,kind='prose',repeat_words=3000)
    packet=tmp_path/'packet';prepare(dataset,packet,30);approved_packet(packet)
    review=tmp_path/'review';export_packet(packet,review)
    with pytest.raises(sqlite3.DatabaseError):release(dataset,review,tmp_path/'out',limits={**DEFAULT_LIMITS,'max_db_bytes':1024*1024})
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.review-stream-*'))


def test_review_input_mutation_is_not_published(tmp_path,monkeypatch):
    import slm.data.review_stream as module
    dataset,packet,review=bundle(tmp_path);original=module.check_entry;changed=False
    def mutate(*args,**kwargs):
        nonlocal changed
        result=original(*args,**kwargs)
        if not changed:
            with (review/'decisions.jsonl').open('a') as f:f.write('\n')
            changed=True
        return result
    monkeypatch.setattr(module,'check_entry',mutate)
    with pytest.raises(ValueError,match='changed'):release(dataset,review,tmp_path/'out',limits=DEFAULT_LIMITS)
    assert not (tmp_path/'out').exists()
