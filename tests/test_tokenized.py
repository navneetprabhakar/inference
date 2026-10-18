from copy import deepcopy
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
pytest.importorskip('tokenizers')
from slm.common.tokenizer import train_core,BPE,STRUCTURAL
from slm.common.config import Config,initialize
from slm.common.training import Batches,Trainer
from slm.data.tokenized import build_shards,ShardBatches,INDEX
from slm.data.review import prepare,release,training_examples
from test_review import fixture_snapshot,approved_packet


def reviewed(tmp_path,kind="dialogue"):
    fixture_snapshot(tmp_path/'raw',kind=kind);prepare(tmp_path/'raw',tmp_path/'review',30)
    approved_packet(tmp_path/'review');release(tmp_path/'raw',tmp_path/'review',tmp_path/'reviewed')
    return tmp_path/'reviewed'


def tokenizer(tmp_path):
    t=train_core(['Question Answer Keep 12.50 not 1250.']*20,512)
    t.save(tmp_path/'tokenizer',{'scope':'Synthetic mechanics fixture, not production selection'})
    return tmp_path/'tokenizer'


def setup(tmp_path,objective='sft',context=64,shard=80):
    data=reviewed(tmp_path);tok=tokenizer(tmp_path)
    report=build_shards(data,tok,tmp_path/'tokens',objective,context,shard)
    return data,tok,report


def test_sft_roundtrip_masks_counts_and_heldout_exclusion(tmp_path):
    release_,tok,r=setup(tmp_path)
    expected=list(training_examples(release_));bpe=BPE.load(tok)
    lineage=[json.loads(s) for s in (tmp_path/'tokens/lineage.jsonl').read_text().splitlines()]
    assert {e['example_id'] for e in expected}=={e['example_id'] for e in lineage}
    assert not {'fixture:0','fixture:1','fixture:2'} & {e['example_id'] for e in lineage}
    with ShardBatches(tmp_path/'tokens',tok,expected_fingerprint=r['dataset_hash']) as batches:
        assert batches._cache is None and batches.items is batches
        for i,e in enumerate(expected):
            actual=batches[i];x,y,m=bpe.serialize(e['messages'])
            for a,b in zip(actual,(x,y,m)):np.testing.assert_array_equal(a,[b])
            assert all(not a.flags.writeable for a in actual)
        assert batches.counts(len(batches))==(r['processed_prediction_positions'],r['supervised_positions'])
        assert batches.counts(0)==(0,0)
        assert r['supervised_positions']<r['processed_prediction_positions']
        assert len(batches._stamps)<=7
    with pytest.raises(ValueError,match='closed'):batches[0]


def test_foundation_packing_preserves_every_transition_eos_and_final_tail(tmp_path):
    release_,tok,r=setup(tmp_path,'foundation',context=17,shard=35)
    bpe=BPE.load(tok);stream=[]
    for e in training_examples(release_):
        x,y,_=bpe.serialize(e['messages'],objective='all');stream.extend(x+[y[-1]])
    with ShardBatches(tmp_path/'tokens',tok) as batches:
        x=np.concatenate([batches[i][0].ravel() for i in range(len(batches))])
        y=np.concatenate([batches[i][1].ravel() for i in range(len(batches))])
        mask=np.concatenate([batches[i][2].ravel() for i in range(len(batches))])
        np.testing.assert_array_equal(x,stream[:-1]);np.testing.assert_array_equal(y,stream[1:])
        assert np.all(mask==1) and int((y==STRUCTURAL['eos']).sum())==len(list(training_examples(release_)))
        assert r['one_pass_encoded_positions']==len(stream) and r['processed_prediction_positions']==len(stream)-1
        assert len(batches)>1 and r['shards']>1 and r['cross_document_attention'] is True


def test_unreviewed_empty_overlong_and_over_budget_intake_never_publish(tmp_path):
    data=reviewed(tmp_path);tok=tokenizer(tmp_path)
    with pytest.raises(ValueError,match='sample-only'):build_shards(tmp_path/'raw',tok,tmp_path/'unreviewed','sft')
    with pytest.raises(ValueError,match='No eligible'):build_shards(data,tok,tmp_path/'overlong','sft',context_length=1,shard_positions=16)
    with pytest.raises(ValueError,match='position budget'):build_shards(data,tok,tmp_path/'budget','foundation',context_length=8,shard_positions=16,max_positions=1)
    assert not any((tmp_path/name).exists() for name in ('unreviewed','overlong','budget'))
    assert not list(tmp_path.glob('.token-shards-*'))


def test_dataset_and_tokenizer_hashes_and_live_mutations_are_refused(tmp_path):
    _,tok,r=setup(tmp_path)
    with pytest.raises(ValueError,match='Pinned token dataset'):ShardBatches(tmp_path/'tokens',tok,'0'*64)
    other=train_core(['Different vocabulary fixture.']*10,512);other.save(tmp_path/'other',{'scope':'synthetic'})
    with pytest.raises(ValueError,match='tokenizer differs'):ShardBatches(tmp_path/'tokens',tmp_path/'other')
    with ShardBatches(tmp_path/'tokens',tok) as batches:
        batches[0]
        name=batches.manifest['shards'][0]['files']['x'];path=tmp_path/'tokens'/name
        with path.open('r+b') as f:f.write(b'\xff\xff\xff\xff')
        with pytest.raises(ValueError,match='changed after verification'):batches[0]
    with ShardBatches(tmp_path/'tokens',tok) as batches:
        with pytest.raises(ValueError,match='checksum'):batches[0]


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_same_backend_resume_across_shard_boundary_with_independent_numeric_control(tmp_path,backend):
    if backend=='mlx':pytest.importorskip('mlx.core')
    _,tok,r=setup(tmp_path,'sft',context=28,shard=28)
    with ShardBatches(tmp_path/'tokens',tok) as batches:
        assert len(batches.manifest['shards'])>1
        config=Config(vocab_size=batches.vocab_size,max_seq_len=64)
        memory=Batches([batches[i] for i in range(len(batches))],batches.vocab_size)
        reference=Trainer(config,initialize(config),memory,backend,tokenizer_hash=batches.tokenizer_hash)
        original=Trainer(config,initialize(config),batches,backend,tokenizer_hash=batches.tokenizer_hash)
        for _ in range(3):
            a,b=original.update(),reference.update()
            np.testing.assert_allclose(a["loss"],b["loss"],atol=1e-5,rtol=1e-4)
        original.save(tmp_path/'state')
        with ShardBatches(tmp_path/'tokens',tok) as reopened:
            resumed=Trainer.resume(tmp_path/'state',reopened,backend,tokenizer_hash=reopened.tokenizer_hash)
            for _ in range(3):
                resumed_result,original_result,memory_result=resumed.update(),original.update(),reference.update()
                assert resumed_result==original_result
                np.testing.assert_allclose(original_result['loss'],memory_result['loss'],atol=1e-5,rtol=1e-4)
                actual=resumed.impl.export(resumed.params);uninterrupted=original.impl.export(original.params)
                memory_weights=reference.impl.export(reference.params)
                for name,a in actual.items():
                    np.testing.assert_array_equal(a,uninterrupted[name])
                    np.testing.assert_allclose(a,memory_weights[name],atol=1e-5,rtol=1e-4)
                for slot in (0,1):
                    a=resumed.impl.export({k:v[slot] for k,v in resumed.moments.items()})
                    b=original.impl.export({k:v[slot] for k,v in original.moments.items()})
                    for name in a:np.testing.assert_array_equal(a[name],b[name])
            assert resumed.tokens==reference.tokens and resumed.supervised_tokens==reference.supervised_tokens
            with pytest.raises(ValueError,match='tokenizer'):Trainer.resume(tmp_path/'state',reopened,backend)


def test_trainer_rejects_vocab_context_and_tokenizer_mismatch_before_update(tmp_path):
    _,tok,_=setup(tmp_path)
    with ShardBatches(tmp_path/'tokens',tok) as batches:
        with pytest.raises(ValueError,match='vocabulary'):Trainer(Config(),initialize(Config()),batches)
        c=Config(vocab_size=batches.vocab_size,max_seq_len=1)
        with pytest.raises(ValueError,match='context'):Trainer(c,initialize(c),batches,tokenizer_hash=batches.tokenizer_hash)
        c=Config(vocab_size=batches.vocab_size)
        with pytest.raises(ValueError,match='tokenizer'):Trainer(c,initialize(c),batches)


def test_interrupted_publication_leaves_no_partial_dataset(tmp_path,monkeypatch):
    import slm.data.tokenized as module
    data=reviewed(tmp_path);tok=tokenizer(tmp_path)
    def fail(*args):raise OSError('synthetic disk failure')
    monkeypatch.setattr(module.os,'rename',fail)
    with pytest.raises(OSError):build_shards(data,tok,tmp_path/'out','sft')
    assert not (tmp_path/'out').exists() and not list(tmp_path.glob('.token-shards-*'))


def test_prose_foundation_encoding_has_eos_and_sft_never_treats_prose_as_dialogue(tmp_path):
    data=reviewed(tmp_path,kind='prose');tok=tokenizer(tmp_path);bpe=BPE.load(tok)
    r=build_shards(data,tok,tmp_path/'prose','foundation',context_length=16,shard_positions=40)
    stream=[]
    for record in training_examples(data):stream.extend(bpe.encode(record['messages'][0]['content'])+[STRUCTURAL['eos']])
    with ShardBatches(tmp_path/'prose',tok) as batches:
        np.testing.assert_array_equal(np.concatenate([batches[i][0].ravel() for i in range(len(batches))]),stream[:-1])
        np.testing.assert_array_equal(np.concatenate([batches[i][1].ravel() for i in range(len(batches))]),stream[1:])
    with pytest.raises(ValueError,match='not_dialogue'):build_shards(data,tok,tmp_path/'not-sft','sft')


@pytest.mark.parametrize('defect',['offset','token','loss'])
def test_rehashed_payloads_still_must_pass_semantic_invariants(tmp_path,defect):
    _,tok,_=setup(tmp_path)
    root=tmp_path/'tokens';manifest=json.loads((root/'manifest.json').read_text())
    if defect=='offset':
        filename='index.bin';index=np.fromfile(root/filename,dtype=INDEX);index[0]['offset']=1;index.tofile(root/filename)
    else:
        filename=manifest['shards'][0]['files']['x' if defect=='token' else 'loss']
        dtype='<u4' if defect=='token' else 'u1';values=np.fromfile(root/filename,dtype=dtype)
        values[0]=2**32-1 if defect=='token' else 2;values.tofile(root/filename)
    manifest['files'][filename]=hashlib.sha256((root/filename).read_bytes()).hexdigest()
    (root/'manifest.json').write_text(json.dumps(manifest))
    if defect=='offset':
        with pytest.raises(ValueError,match='cursor/index'):ShardBatches(root,tok)
    else:
        with ShardBatches(root,tok) as batches:
            with pytest.raises(ValueError,match='Invalid shard token/mask'):batches[0]


def test_records_requiring_dedicated_supervision_or_tool_serialization_fail_closed(tmp_path):
    from slm.data.tokenized import document_tokens
    tok=tokenizer(tmp_path);bpe=BPE.load(tok)
    e={'task':'student_correction','messages':[{'role':'assistant','content':'Incorrect historical reply.'}]}
    with pytest.raises(ValueError,match='Continuation-only'):document_tokens(bpe,e,'sft',64)
    e={'task':'conversation','messages':[{'role':'assistant','content':'','tool_calls':[{'name':'lookup'}]}]}
    with pytest.raises(ValueError,match='dedicated tool'):document_tokens(bpe,e,'sft',64)


def test_rebuilding_same_release_and_tokenizer_produces_identical_shard_identity(tmp_path):
    data,tok,r=setup(tmp_path)
    again=build_shards(data,tok,tmp_path/'again','sft',context_length=64,shard_positions=80)
    assert again['dataset_hash']==r['dataset_hash']
    assert (tmp_path/'tokens/manifest.json').read_bytes()==(tmp_path/'again/manifest.json').read_bytes()


def test_content_category_selection_is_explicit_and_counted(tmp_path):
    fixture_snapshot(tmp_path/'raw');prepare(tmp_path/'raw',tmp_path/'review',30);approved_packet(tmp_path/'review')
    packet=json.loads((tmp_path/'review').read_text())
    packet['source_reviews']['fixture']['allowed_categories']=['sfw','adult_topic']
    for i,entry in enumerate(packet['examples'].values()):
        if i%2:entry['decision']['content_category']='adult_topic'
    (tmp_path/'review').write_text(json.dumps(packet));release(tmp_path/'raw',tmp_path/'review',tmp_path/'reviewed')
    tok=tokenizer(tmp_path)
    expected=list(training_examples(tmp_path/'reviewed'));counts={c:sum(e['content_category']==c for e in expected) for c in ('sfw','adult_topic')}
    default=build_shards(tmp_path/'reviewed',tok,tmp_path/'sfw','sft')
    assert default['retained_records']==counts['sfw'] and default['excluded_records']['content_category_excluded']==counts['adult_topic']
    explicit=build_shards(tmp_path/'reviewed',tok,tmp_path/'adult','sft',allowed_categories=('adult_topic',))
    assert explicit['retained_records']==counts['adult_topic'] and explicit['categories']=={'adult_topic':counts['adult_topic']}


def test_tiny_mlx_cpu_roundtrip_uses_same_shard_cursor_and_original_tolerances(tmp_path):
    pytest.importorskip('mlx.core')
    _,tok,_=setup(tmp_path,'sft',context=28,shard=28)
    with ShardBatches(tmp_path/'tokens',tok) as batches:
        c=Config(vocab_size=batches.vocab_size,max_seq_len=64)
        reference=Trainer(c,initialize(c),batches,'mlx',tokenizer_hash=batches.tokenizer_hash)
        reference.update();reference.update();reference.save(tmp_path/'mlx')
        cpu=Trainer.resume(tmp_path/'mlx',batches,'torch',tokenizer_hash=batches.tokenizer_hash)
        for _ in range(2):reference.update();cpu.update()
        cpu.save(tmp_path/'cpu')
        returned=Trainer.resume(tmp_path/'cpu',batches,'mlx',tokenizer_hash=batches.tokenizer_hash)
        for _ in range(2):reference.update();returned.update()
        expected=reference.impl.export(reference.params);actual=returned.impl.export(returned.params)
        for name in expected:np.testing.assert_allclose(actual[name],expected[name],atol=1e-5,rtol=1e-4)
        assert (returned.cursor,returned.tokens,returned.supervised_tokens)==(reference.cursor,reference.tokens,reference.supervised_tokens)


def test_cuda_consumes_shards_and_matches_cpu_at_existing_tiny_bounds(tmp_path):
    import torch
    if not torch.cuda.is_available():pytest.skip('NVIDIA CUDA device unavailable')
    from slm.eval.portability import environment,compare,capture
    environment('torch','cuda')
    _,tok,_=setup(tmp_path,'sft',context=28,shard=28)
    with ShardBatches(tmp_path/'tokens',tok) as batches:
        c=Config(vocab_size=batches.vocab_size,max_seq_len=64)
        a=Trainer(c,initialize(c),batches,'torch','cpu',tokenizer_hash=batches.tokenizer_hash)
        b=Trainer(c,initialize(c),batches,'torch','cuda',tokenizer_hash=batches.tokenizer_hash)
        for _ in range(6):a.update();b.update()
        compare(capture(b),capture(a))


@pytest.mark.parametrize('defect',['next_token_shift','role_mask'])
def test_rehashed_in_range_labels_cannot_change_autoregressive_shift_or_sft_role_masks(tmp_path,defect):
    _,tok,_=setup(tmp_path);root=tmp_path/'tokens';manifest=json.loads((root/'manifest.json').read_text())
    if defect=='next_token_shift':
        filename=manifest['shards'][0]['files']['y'];values=np.fromfile(root/filename,dtype='<u4')
        values[2]=(int(values[2])+1)%manifest['vocab_size'];values.tofile(root/filename)
    else:
        filename=manifest['shards'][0]['files']['loss'];values=np.fromfile(root/filename,dtype='u1')
        index=np.fromfile(root/'index.bin',dtype=INDEX);length=int(index[0]['length'])
        supervised=int(np.flatnonzero(values[:length])[0]);values[0]=1;values[supervised]=0;values.tofile(root/filename)
    manifest['files'][filename]=hashlib.sha256((root/filename).read_bytes()).hexdigest()
    (root/'manifest.json').write_text(json.dumps(manifest))
    with ShardBatches(root,tok) as batches:
        with pytest.raises(ValueError,match='shift differs|role-derived'):batches[0]
