"""Synthetic supervision controls; these grant no real source approval."""
from dataclasses import asdict
import json
import numpy as np
import pytest
from slm.common.tokenizer import train_core
from slm.common.tool_serialization import serialize
from slm.data.tokenized import build_shards,ShardBatches,document_tokens,validate_batch_objective,sha
from slm.data.schema import Source,make_example
from slm.data.curation import curate
from slm.data.review import prepare,release
from test_review import approved_packet
from test_tools import transcript

MODE='last-user-turn-v1'


def conversation(typed):
    prior=[{'role':'user','content':'What was the earlier value?'},
           {'role':'assistant','content':json.dumps({'kind':'answer','text':'Wrong: 9999.','facts':{'value':9999}}) if typed else 'Wrong: 9999.'}]
    return prior+(transcript() if typed else [
        {'role':'user','content':'Correction: three notebooks at 875 each.'},
        {'role':'assistant','content':'The corrected total is 2625.'}])


def batch(bpe,messages,typed,mode=MODE):
    return (serialize(bpe,messages,supervision=mode) if typed else bpe.serialize(messages,supervision=mode))


@pytest.mark.parametrize('typed',[False,True])
def test_old_mistake_is_input_only_and_reader_rejects_old_assistant_targets(typed):
    bpe=train_core(['Synthetic correction notebooks and local tool.']*10,512)
    messages=conversation(typed);x,y,mask=batch(bpe,messages,typed)
    ids=x+[y[-1]];m=[0]+mask
    second_user=[i for i,v in enumerate(ids) if v==5][-1]
    assert not any(m[:second_user+1])
    # Independent expected segments: every role marker, user and tool span is zero;
    # only assistant content/end and terminal EOS after the final user are targets.
    positions=[i for i,v in enumerate(ids) if v in (4,5,6,7)]
    for index,start in enumerate(positions):
        end=positions[index+1] if index+1<len(positions) else len(ids)-1
        assert m[start]==0
        assert all(v==int(ids[start]==6 and start>second_user) for v in m[start+1:end])
    assert m[-1]==1 and sum(mask)>0
    format_='tool-continuation-v1' if typed else 'plain-continuation-v1'
    arrays=[np.array([v]) for v in (x,y,mask)]
    validate_batch_objective(arrays,'sft',format_,bpe)
    _,_,badmask=batch(bpe,messages,typed,'all-assistant-v1')
    assert sum(badmask)>sum(mask)
    with pytest.raises(ValueError,match='supervision'):
        validate_batch_objective([arrays[0],arrays[1],np.array([badmask])],'sft',format_,bpe)
    with pytest.raises(ValueError,match='require SFT'):
        document_tokens(bpe,{'messages':messages,'validation_results':{'supervision':MODE}},'foundation',1024)
    with pytest.raises(ValueError,match='assistant objective'):
        bpe.serialize(messages,objective='all',supervision=MODE)
    with pytest.raises(ValueError,match='Continuation requires'):
        batch(bpe,messages[:-1] if not typed else messages[:3],typed)


@pytest.mark.parametrize('typed',[False,True])
def test_reviewed_continuation_shards_roundtrip_and_rehashed_wrong_masks_fail(tmp_path,typed):
    src=Source('synthetic_continuation','a'*40,'https://example.org','fixture','b'*64,'c'*64,('fixture',))
    e=make_example(src,'one','one',conversation(typed),task='tool_dialogue' if typed else 'student_correction',
        language='en',official_split='train',validation_results={'supervision':MODE})
    for group in range(100):
        e.example_id=f'{src.source_id}:synthetic-{group}'
        items,_=curate([e],{src.source_id:src})
        if items[0].split=='train':break
    assert len(items)==1 and items[0].split=='train'
    raw=tmp_path/'raw';raw.mkdir()
    (raw/'train-00000.jsonl').write_text(json.dumps(items[0].to_dict())+'\n')
    (raw/'sources.json').write_text(json.dumps({src.source_id:asdict(src)}))
    (raw/'manifest.json').write_text(json.dumps({'version':1,'release':'sample_only','files':{p.name:sha(p) for p in raw.iterdir()}}))
    prepare(raw,tmp_path/'review',30);approved_packet(tmp_path/'review');release(raw,tmp_path/'review',tmp_path/'reviewed')
    bpe=train_core(['Synthetic continuation corrected total.']*10,512);tok=tmp_path/'tok';bpe.save(tok,{'scope':'Synthetic fixture'})
    out=tmp_path/'tokens';r=build_shards(tmp_path/'reviewed',tok,out,'sft',context_length=1024)
    with ShardBatches(out,tok,r['dataset_hash']) as data:
        assert data.manifest['version']==3
        for a,b in zip(data[0],batch(bpe,items[0].messages,typed)):np.testing.assert_array_equal(a,[b])
    # A self-consistently rehashed artifact still cannot supervise old assistants.
    p=out/'manifest.json';manifest=json.loads(p.read_text());spec=manifest['shards'][0]
    _,_,wrong=batch(bpe,items[0].messages,typed,'all-assistant-v1')
    np.asarray(wrong,dtype='u1').tofile(out/spec['files']['loss'])
    from slm.data.tokenized import INDEX
    index=np.fromfile(out/'index.bin',dtype=INDEX);index['supervised']=sum(wrong);index.tofile(out/'index.bin')
    spec['supervised']=manifest['supervised_tokens']=sum(wrong)
    # Rewrite all reported totals, file digests and lineage so only semantic validation detects it.
    for name in ('lineage.jsonl','report.json'):
        q=out/name;v=json.loads(q.read_text())
        if name=='lineage.jsonl':v['supervised_positions']=sum(wrong)
        else:
            v['supervised_positions']=sum(wrong)
            for stats in v['sources'].values():stats['supervised_positions']=sum(wrong)
        q.write_text(json.dumps(v)+'\n')
    manifest['files']={name:sha(out/name) for name in manifest['files']}
    p.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='supervision'):
        with ShardBatches(out,tok) as data:data[0]


def test_unmarked_corrections_and_unknown_contracts_remain_refused():
    bpe=train_core(['fixture'],300);e={'task':'student_correction','messages':conversation(False)}
    with pytest.raises(ValueError,match='adapter required'):document_tokens(bpe,e,'sft',1024)
    e['validation_results']={'supervision':'made-up'}
    with pytest.raises(ValueError,match='Unknown supervision'):document_tokens(bpe,e,'sft',1024)
