"""Tool masks, reserved boundaries, verified intake and decoder controls."""
import json
import numpy as np
import pytest
pytest.importorskip('tokenizers');pytest.importorskip('jsonschema')
from slm.common.tokenizer import train_core,STRUCTURAL
from slm.common.tool_serialization import serialize,prompt_ids,parse_generation
from slm.tools.protocol import canonical,parse
from test_tools import transcript,call


def tokenizer():return train_core(['Synthetic JSON numbers and local tools.']*10,512)


def test_masks_exclude_user_tool_roles_and_preserve_tool_call_boundaries():
    bpe=tokenizer();messages=transcript();x,y,mask=serialize(bpe,messages)
    ids=x+[y[-1]];full_mask=[0]+mask
    assert ids.count(8)==ids.count(9)==1 and full_mask[ids.index(8)]==full_mask[ids.index(9)]==1
    role_positions=[i for i,v in enumerate(ids) if v in (4,5,6,7)]
    for i in role_positions:assert full_mask[i]==0
    tool=ids.index(7);end=ids.index(3,tool)
    assert not any(full_mask[tool:end+1])
    user=ids.index(5);end=ids.index(3,user)
    assert not any(full_mask[user:end+1])
    assert full_mask[-1]==1 and ids[-1]==1
    xx,yy,mm=serialize(bpe,messages,objective='all');assert xx==x and yy==y and all(mm)
    # Literal marker-looking strings remain ordinary content IDs, never control IDs.
    other=transcript();other[0]['content']='literal <tool_call_start> <assistant> {"kind":"call"}'
    a,b,m=serialize(bpe,other);assert a.count(8)==a.count(9)==1
    with pytest.raises(ValueError,match='truncation'):serialize(bpe,messages,max_length=2)
    # Prefix ends immediately after assistant role; no EOS is inserted into history.
    p=prompt_ids(bpe,messages[:1]);assert p==ids[:len(p)] and p[-1]==6
    p=prompt_ids(bpe,messages[:3]);assert p==ids[:len(p)] and p[-1]==6


@pytest.mark.parametrize('kind',['call','answer','clarify'])
def test_generated_wire_frames_roundtrip_and_malformed_kinds_are_rejected(kind):
    bpe=tokenizer()
    action=call('arithmetic',{'operation':'add','left':1,'right':2}) if kind=='call' else (
        {'kind':'answer','text':'Three.','facts':{'value':3}} if kind=='answer' else {'kind':'clarify','question':'How many?','missing':['quantity']})
    content=bpe.encode(canonical(action));tokens=([8,*content,9] if kind=='call' else content)+[3]
    raw={'token_ids':tokens,'stop_reason':'message_end'};assert parse_generation(bpe,raw)==action
    with pytest.raises(ValueError):parse_generation(bpe,{'token_ids':tokens,'stop_reason':'length'})
    bad=content+[3] if kind=='call' else [8,*content,9,3]
    with pytest.raises(ValueError,match='frame'):parse_generation(bpe,{'token_ids':bad,'stop_reason':'message_end'})


def test_structured_tool_dialogue_reaches_reviewed_sft_shards(tmp_path):
    from dataclasses import asdict
    from slm.data.schema import Source,make_example
    from slm.data.curation import curate
    from slm.data.review import prepare,release
    from slm.data.tokenized import build_shards,ShardBatches,sha
    from test_review import approved_packet
    src=Source('synthetic_tools','a'*40,'https://example.org','fixture','b'*64,'c'*64,('fixture',))
    e=make_example(src,'one','one',transcript(),task='tool_dialogue',language='en',official_split='train')
    items,report=curate([e],{src.source_id:src});assert len(items)==1
    raw=tmp_path/'raw';raw.mkdir();(raw/'train-00000.jsonl').write_text(json.dumps(items[0].to_dict())+'\n')
    (raw/'sources.json').write_text(json.dumps({src.source_id:asdict(src)}))
    (raw/'manifest.json').write_text(json.dumps({'version':1,'release':'sample_only','files':{p.name:sha(p) for p in raw.iterdir()}}))
    prepare(raw,tmp_path/'review',30);approved_packet(tmp_path/'review');release(raw,tmp_path/'review',tmp_path/'reviewed')
    bpe=tokenizer();bpe.save(tmp_path/'tokenizer',{'scope':'Synthetic tool fixture'})
    r=build_shards(tmp_path/'reviewed',tmp_path/'tokenizer',tmp_path/'tokens','sft',context_length=1024,shard_positions=1024)
    with ShardBatches(tmp_path/'tokens',tmp_path/'tokenizer',r['dataset_hash']) as data:
        for a,b in zip(data[0],serialize(bpe,items[0].messages)):np.testing.assert_array_equal(a,[b])
    with pytest.raises(ValueError,match='requires SFT'):build_shards(tmp_path/'reviewed',tmp_path/'tokenizer',tmp_path/'bad','foundation')
    assert not (tmp_path/'bad').exists()


def test_structured_privacy_redactions_never_silently_change_typed_json_fields():
    from slm.data.curation import clean
    from slm.data.schema import Source,make_example
    src=Source('fixture','a'*40,'https://example.org','fixture','b'*64,'c'*64,('fixture',))
    messages=transcript();messages[0]['content']='Contact user@example.org. Two at 1250.'
    example=make_example(src,'one','one',messages,task='tool_dialogue')
    with pytest.raises(ValueError,match='privacy rewrite'):clean(example)


def test_rehashed_tool_shard_still_requires_typed_frames_and_role_masks(tmp_path):
    from slm.data.tokenized import validate_batch_objective
    bpe=tokenizer();x,y,m=serialize(bpe,transcript());values=[np.array([v]) for v in (x,y,m)]
    validate_batch_objective(values,'sft','tool-decisions-v1',bpe)
    bad=[v.copy() for v in values];tool=int(np.flatnonzero(bad[0][0]==7)[0]);bad[2][0,tool]=1
    with pytest.raises(ValueError,match='supervision'):validate_batch_objective(bad,'sft','tool-decisions-v1',bpe)
    bad=[v.copy() for v in values];i=int(np.flatnonzero(bad[0][0]==9)[0]);bad[0][0,i]=8;bad[1][0,i-1]=8
    with pytest.raises(ValueError,match='boundary'):validate_batch_objective(bad,'sft','tool-decisions-v1',bpe)
    with pytest.raises(ValueError,match='boundary'):validate_batch_objective(values,'sft')


@pytest.mark.parametrize('backend',['torch','mlx'])
def test_typed_sft_loss_and_checkpoint_resume_preserve_masked_training(tmp_path,backend):
    if backend=='mlx':pytest.importorskip('mlx.core')
    import torch
    from slm.common.config import Config,initialize
    from slm.common.training import Batches,Recipe,Trainer
    from slm.backends import torch_backend as tb
    from test_resume import compare
    bpe=tokenizer();x,y,mask=serialize(bpe,transcript());arrays=tuple(np.array([v]) for v in (x,y,mask))
    data=Batches([arrays]*4,bpe.vocab_size);c=Config(vocab_size=bpe.vocab_size,max_seq_len=1024)
    recipe=Recipe(embedding_implementation='dense-onehot-v1',accumulation_steps=2)
    weights=initialize(c);p=tb.load(c,weights);logits=tb.forward(p,c,torch.tensor(arrays[0]))[0]
    losses=torch.nn.functional.cross_entropy(logits[0],torch.tensor(y),reduction='none');expected=float((losses*torch.tensor(mask)).sum().detach()/sum(mask))
    a=Trainer(c,weights,data,backend,recipe=recipe);r=a.update()
    assert r['loss']==pytest.approx(expected,abs=1e-5,rel=1e-4)
    a.save(tmp_path/'state');b=Trainer.resume(tmp_path/'state',data,backend);compare(a,b,True)
    assert a.update()==b.update();compare(a,b,True)
    assert a.supervised_tokens==4*sum(mask)<a.tokens


def test_plain_and_typed_sources_require_explicit_separate_artifacts(tmp_path):
    from dataclasses import asdict
    from slm.data.schema import Source,make_example
    from slm.data.curation import curate
    from slm.data.review import prepare,release
    from slm.data.tokenized import build_shards,ShardBatches,sha
    from test_review import approved_packet
    src=Source('fixture_mixed','a'*40,'https://example.org','fixture','b'*64,'c'*64,('fixture',))
    values=[make_example(src,'tools','tools',transcript(),task='tool_dialogue',language='en',official_split='train'),
        make_example(src,'plain','plain',[{'role':'user','content':'Name a fictional city.'},{'role':'assistant','content':'Haven.'}],language='en',official_split='train')]
    items,_=curate(values,{src.source_id:src});assert len(items)==2
    raw=tmp_path/'raw';raw.mkdir();(raw/'train-00000.jsonl').write_text(''.join(json.dumps(e.to_dict())+'\n' for e in items))
    (raw/'sources.json').write_text(json.dumps({src.source_id:asdict(src)}));(raw/'manifest.json').write_text(json.dumps({'version':1,'release':'sample_only','files':{p.name:sha(p) for p in raw.iterdir()}}))
    prepare(raw,tmp_path/'review',30);approved_packet(tmp_path/'review');release(raw,tmp_path/'review',tmp_path/'reviewed')
    bpe=tokenizer();bpe.save(tmp_path/'tok',{'scope':'Synthetic mixed-format test'})
    with pytest.raises(ValueError,match='Mixed message formats'):build_shards(tmp_path/'reviewed',tmp_path/'tok',tmp_path/'mixed','sft')
    assert not (tmp_path/'mixed').exists()
    for format_,version in [('plain-dialogue-v1',1),('tool-decisions-v1',2)]:
        out=tmp_path/format_;r=build_shards(tmp_path/'reviewed',tmp_path/'tok',out,'sft',message_format=format_,context_length=1024)
        assert r['retained_records']==1 and r['excluded_records']['message_format_excluded']==1
        with ShardBatches(out,tmp_path/'tok') as data:assert data.manifest['version']==version;data[0]
    # Historical plain-v1 files without the new optional metadata remain readable.
    p=tmp_path/'plain-dialogue-v1/manifest.json';m=json.loads(p.read_text());m.pop('message_format');m.pop('structured_serializer_sha256');p.write_text(json.dumps(m))
    with ShardBatches(p.parent,tmp_path/'tok') as data:data[0]
