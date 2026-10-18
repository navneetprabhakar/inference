"""Synthetic teacher/cache/review fixtures; no real generation or approval."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sqlite3
import pytest
from slm.teacher.bridge import normalize,snapshot,source_example,review_requirements,cached_response,REVIEW_FIELDS
from slm.teacher.cli import CLIRecipe,PROMPT_V1,PROMPT_V2,generate_cli
from slm.teacher.journal import Journal
from slm.teacher.scenarios import fixture_scenario
from slm.data.schema import Source,digest
from slm.data.build import verify
from slm.data.review import prepare,release,training_examples
from slm.data.tokenized import build_shards,ShardBatches
from slm.common.tokenizer import train_core
from slm.tools.protocol import parse,canonical,validate_messages
from slm.tools.local import LocalTools
from slm.inference.tools import tool_context,run_turn
from test_teacher_cli import FakeCLI
from test_review import approved_packet


def fixture(tmp_path,task='tool_trajectory',style='professional',version=PROMPT_V2,mutate=None):
    scenario=fixture_scenario(task,style)
    if mutate:mutate(scenario)
    j=Journal(tmp_path/'journal.sqlite',0,'synthetic-bridge-test',20)
    record=generate_cli(j,FakeCLI(),CLIRecipe(prompt_version=version),scenario)
    return record,j


def source_descriptor(tmp_path,source_id='teacher_fixture'):
    card=tmp_path/'card.txt';terms=tmp_path/'terms.txt'
    card.write_text('Synthetic fixture source card, not a real teacher permission.')
    terms.write_text('Synthetic test-only terms; no actual account clearance.')
    source=Source(source_id,'a'*40,'https://example.org/synthetic-teacher','Synthetic-test-only',
        hashlib.sha256(terms.read_bytes()).hexdigest(),hashlib.sha256(card.read_bytes()).hexdigest(),('codex-cli-chatgpt-v1',))
    path=tmp_path/'source.json';path.write_text(json.dumps({**asdict(source),'evidence_files':{'card':card.name,'license':terms.name}}))
    return source,path


def record_file(tmp_path,r):
    path=tmp_path/(r['request_key']+'.json');path.write_text(json.dumps(r,sort_keys=True));return path


@pytest.mark.parametrize('task',['conversation','clarification','correction','style_pair','tool_trajectory','student_correction'])
@pytest.mark.parametrize('style',['professional','casual','terse','humorous','caveman'])
def test_all_task_style_shapes_are_typed_pending_continuations(tmp_path,task,style):
    record,j=fixture(tmp_path,task,style);before=j.summary();preview=normalize(record,j.path)
    assert j.summary()==before and preview['training_eligible'] is False
    messages=preview['messages'];validate_messages(messages)
    assert f'Response style: {style}. Content setting: sfw.' in messages[0]['content']
    assert messages[0]['content'].endswith(tool_context(LocalTools()))
    history=record['request']['scenario']['context'];proof=preview['proof']
    for original,composed in zip(history,messages[1:]):
        assert original['role']==composed['role']
        assert (parse(composed['content'])['text'] if original['role']=='assistant' else composed['content'])==original['content']
        if original['role']=='assistant':assert parse(composed['content'])['facts']=={}
    assert proof['composed_messages_sha256']==digest(messages)
    assert not proof['legacy_tool_reply_role_ambiguous'] and set(preview['required_human_checks'])==set(REVIEW_FIELDS)
    if task=='tool_trajectory':
        call=parse(messages[-3]['content']);result=parse(messages[-2]['content']);answer=parse(messages[-1]['content'])
        assert call['name']=='arithmetic' and call['arguments']=={'operation':'multiply','left':1250,'right':2}
        assert result==LocalTools().execute(call) and answer['facts']['total_minor']==2500
        assert 'multiply_amount' not in messages[-3]['content']
    elif task=='clarification':assert parse(messages[-1]['content'])['missing']==['quantity']
    else:assert parse(messages[-1]['content'])['kind']=='answer'


@pytest.mark.parametrize('task',['conversation','correction','clarification','student_correction'])
def test_plain_mode_preserves_reply_without_json_wrappers(tmp_path,task):
    r,j=fixture(tmp_path,task);preview=normalize(r,j.path,'plain')
    assert preview['messages'][-1]['content']==r['validation']['candidate']['reply']
    assert preview['proof']['host_mapping'] is None and preview['proof']['history_assistant_wrappers']==0
    assert not preview['messages'][0]['content'].endswith(tool_context(LocalTools()))


def test_legacy_cache_order_is_read_without_reservation_or_generation(tmp_path):
    r,j=fixture(tmp_path,version=PROMPT_V1);r.pop('submitted_prompt_sha256');p=record_file(tmp_path,r)
    before=j.path.read_bytes();preview=normalize(json.loads(p.read_text()),j.path)
    assert j.path.read_bytes()==before
    assert preview['proof']['legacy_tool_reply_role_ambiguous']
    assert not preview['proof']['submitted_prompt_hash_previously_recorded']
    assert not preview['training_eligible']
    with pytest.raises(ValueError,match='Completed CLI'):cached_response(j.path,'0'*64)
    assert j.path.read_bytes()==before
    absent=tmp_path/'missing.sqlite'
    with pytest.raises(FileNotFoundError):cached_response(absent,'0'*64)
    assert not absent.exists()


@pytest.mark.parametrize('defect',['request_key','schema','controls','candidate','response','prompt','usage','scenario'])
def test_record_tampering_cannot_bypass_cache_binding(tmp_path,defect):
    r,j=fixture(tmp_path);before=j.summary();r=deepcopy(r)
    if defect=='request_key':r['request_key']='0'*64
    elif defect=='schema':r['request']['schema']['additionalProperties']=True
    elif defect=='controls':r['request']['controls']['features.shell_tool']=True
    elif defect=='candidate':r['validation']['candidate']['reply']='Tampered reply.'
    elif defect=='response':r['provider_response_sha256']='0'*64
    elif defect=='prompt':r['submitted_prompt_sha256']='0'*64
    elif defect=='usage':r['usage']['output_tokens']+=1
    else:r['request']['scenario']['facts']['quantity']=3
    with pytest.raises(ValueError):normalize(r,j.path)
    assert j.summary()==before


def test_rehashed_request_without_completed_cache_is_read_only_failure(tmp_path):
    r,j=fixture(tmp_path);r['request']['scenario']['scenario_id']='new-key'
    r['request_key']=digest(r['request']);r['scenario_sha256']=digest(r['request']['scenario'])
    r['submitted_prompt_sha256']=hashlib.sha256(__import__('slm.teacher.cli',fromlist=['render_prompt']).render_prompt(r['request']['scenario'],PROMPT_V2)).hexdigest()
    before=j.summary()
    with pytest.raises(ValueError,match='Completed CLI'):normalize(r,j.path)
    assert j.summary()==before


@pytest.mark.parametrize('defect',['partial_tool','assistant_end','nonalternating','inconsistent_facts','host_bounds','unknown_clarification'])
def test_unsupported_context_or_oracle_never_becomes_training_data(tmp_path,defect):
    task='clarification' if defect=='unknown_clarification' else 'tool_trajectory'
    def mutate(s):
        if defect=='partial_tool':s['context']=[{'role':'user','content':'Old task.'},{'role':'tool','content':'Unresolved old result.'},{'role':'user','content':'Continue.'}]
        elif defect=='assistant_end':s['context'].append({'role':'assistant','content':'Already done.'})
        elif defect=='nonalternating':s['context'].insert(0,{'role':'user','content':'Duplicate user.'})
        elif defect=='inconsistent_facts':s['facts']['quantity']=3
        elif defect=='host_bounds':s['facts']['unit_price_minor']=s['expected_action']['arguments']['unit_price_minor']=1000001
        else:s['facts']['quantity']=2
    r,j=fixture(tmp_path,task,mutate=mutate)
    with pytest.raises(ValueError):normalize(r,j.path)
    if defect=='unknown_clarification':
        with pytest.raises(ValueError,match='unknown fact'):normalize(r,j.path,'plain')
    with pytest.raises(ValueError,match='typed'):normalize(fixture(tmp_path,'tool_trajectory')[0],j.path,'plain')


def test_bad_cache_hash_or_uncertain_entry_is_never_read_as_completed(tmp_path):
    r,j=fixture(tmp_path)
    with sqlite3.connect(j.path) as db:db.execute('UPDATE requests SET response_hash=?',('0'*64,))
    with pytest.raises(ValueError,match='checksum'):normalize(r,j.path)
    with sqlite3.connect(j.path) as db:db.execute("UPDATE requests SET status='uncertain'")
    with pytest.raises(ValueError,match='Completed CLI'):normalize(r,j.path)


class Scripted:
    identity={'source':'synthetic transcript compatibility control'}
    def __init__(self,call,final):self.steps=iter([call,final]);self.histories=[]
    def generate_decision(self,messages,max_new_tokens):
        self.histories.append(deepcopy(messages));return {'scope':'scripted fixture'},next(self.steps)


def test_composed_tool_transcript_matches_actual_host_runtime_messages(tmp_path):
    r,j=fixture(tmp_path);v=normalize(r,j.path);messages=v['messages'];n=v['proof']['history_messages']
    history=deepcopy(messages[:n]);history[0]['content']=history[0]['content'].removesuffix('\n'+tool_context(LocalTools()))
    model=Scripted(parse(messages[-3]['content']),parse(messages[-1]['content']))
    report=run_turn(model,history,LocalTools())
    assert model.histories[0]==messages[:n] and model.histories[1]==messages[:-1]
    assert report['status']=='answer' and report['executed_calls']==1 and report['call_attempts']==1


@pytest.mark.parametrize('format_',['plain','typed'])
@pytest.mark.parametrize('backend',['torch','mlx'])
def test_source_review_release_shards_and_history_mask_are_connected(tmp_path,format_,backend):
    if backend=='mlx':pytest.importorskip('mlx.core')
    r,j=fixture(tmp_path,'student_correction');path=record_file(tmp_path,r)
    from slm.data.curation import curate
    # Choose a synthetic source identity in the train subdivision. Real families are never moved.
    for i in range(100):
        source,descriptor=source_descriptor(tmp_path,'teacher_fixture_'+str(i))
        e=source_example(r,j.path,source,format_);items,_=curate([e],{source.source_id:source})
        if items[0].split=='train':break
    assert items[0].split=='train'
    out=tmp_path/'sample';snapshot([path],j.path,descriptor,out,format_);verify(out)
    assert (out/'source-card.txt').read_bytes()==(tmp_path/'card.txt').read_bytes()
    assert json.loads((out/'report.json').read_text())['training_eligible'] is False
    with pytest.raises(ValueError,match='sample-only'):list(training_examples(out))
    packet=tmp_path/'review.json';prepare(out,packet)
    review=json.loads(packet.read_text());entry=next(iter(review['examples'].values()))
    assert all(v is None for v in entry['decision']['teacher_review'].values())
    assert review_requirements(entry['record'])==REVIEW_FIELDS
    from slm.data.review_console import render
    assert render(out,packet,tmp_path/'console.html')['pinned_evidence_sources']==1
    approved_packet(packet)
    with pytest.raises(ValueError,match='Explicit teacher'):release(out,packet,tmp_path/'not-released')
    review=json.loads(packet.read_text())
    for entry in review['examples'].values():entry['decision']['teacher_review']={k:True for k in REVIEW_FIELDS}
    packet.write_text(json.dumps(review));release(out,packet,tmp_path/'reviewed')
    records=list(training_examples(tmp_path/'reviewed'));assert len(records)==1
    bpe=train_core(['Synthetic teacher correction masks and tools.']*10,512);tok=tmp_path/'tok';bpe.save(tok,{'scope':'Synthetic bridge mechanics'})
    report=build_shards(tmp_path/'reviewed',tok,tmp_path/'tokens','sft',context_length=4096)
    with ShardBatches(tmp_path/'tokens',tok,report['dataset_hash']) as batches:
        x,y,mask=batches[0];ids=[*x[0],y[0,-1]];fullmask=[0,*mask[0]];last_user=max(i for i,v in enumerate(ids) if v==5)
        assert not any(fullmask[:last_user+1]) and any(fullmask[last_user+1:])
        assert batches.manifest['version']==3
    # Two explicit repeats are synthetic pipeline mechanics, not real teacher training.
    from slm.common.config import Config,initialize
    from slm.common.training import Batches,Recipe,Trainer
    from test_resume import compare
    arrays=(x,y,mask);data=Batches([arrays,arrays],bpe.vocab_size)
    config=Config(vocab_size=bpe.vocab_size,max_seq_len=4096)
    trainer=Trainer(config,initialize(config),data,backend,'cpu',recipe=Recipe(embedding_implementation='dense-onehot-v1'))
    trainer.update();trainer.save(tmp_path/'checkpoint')
    resumed=Trainer.resume(tmp_path/'checkpoint',data,backend,'cpu');compare(trainer,resumed,True)
    assert trainer.update()==resumed.update();compare(trainer,resumed,True)
    assert trainer.supervised_tokens==2*int(mask.sum())<trainer.tokens
    record=entry['record'];record['messages'][-1]['content']+=' altered'
    with pytest.raises(ValueError,match='receipt'):review_requirements(record)


def test_missing_false_or_partial_teacher_gates_refuse_release(tmp_path):
    r,j=fixture(tmp_path);p=record_file(tmp_path,r);_,descriptor=source_descriptor(tmp_path)
    out=tmp_path/'sample';snapshot([p],j.path,descriptor,out);reviewpath=tmp_path/'review';prepare(out,reviewpath);base=approved_packet(reviewpath)
    for gate in REVIEW_FIELDS:
        packet=deepcopy(base);decision=next(iter(packet['examples'].values()))['decision'];decision['teacher_review']={k:True for k in REVIEW_FIELDS};decision['teacher_review'][gate]=False
        reviewpath.write_text(json.dumps(packet))
        with pytest.raises(ValueError,match='Explicit teacher'):release(out,reviewpath,tmp_path/'no-release')
    assert not (tmp_path/'no-release').exists()
    packet=deepcopy(base);decision=next(iter(packet['examples'].values()))['decision']
    decision['teacher_review']={k:True for k in REVIEW_FIELDS};decision['content_category']='adult_topic'
    next(iter(packet['source_reviews'].values()))['allowed_categories'].append('adult_topic')
    reviewpath.write_text(json.dumps(packet))
    with pytest.raises(ValueError,match='cannot be relabeled'):release(out,reviewpath,tmp_path/'no-release')


def test_source_evidence_and_atomic_snapshot_guards(tmp_path):
    r,j=fixture(tmp_path);p=record_file(tmp_path,r);source,descriptor=source_descriptor(tmp_path)
    with pytest.raises(ValueError,match='Duplicate teacher'):snapshot([p,p],j.path,descriptor,tmp_path/'duplicate')
    assert not (tmp_path/'duplicate').exists()
    (tmp_path/'terms.txt').write_text('Changed terms.')
    with pytest.raises(ValueError,match='checksum'):snapshot([p],j.path,descriptor,tmp_path/'bad')
    assert not (tmp_path/'bad').exists()
    with pytest.raises(ValueError,match='sample-only'):source_example(r,j.path,Source(**{**asdict(source),'review_status':'training_approved'}))
    with pytest.raises(ValueError,match='origin'):source_example(r,j.path,Source(**{**asdict(source),'upstream_origins':('other',)}))



def test_derived_parent_claims_require_actual_approved_train_membership(tmp_path):
    from test_review import fixture_snapshot
    raw=tmp_path/'parent-input';fixture_snapshot(raw)
    reviewpath=tmp_path/'parent-review';prepare(raw,reviewpath,30);approved_packet(reviewpath)
    release(raw,reviewpath,tmp_path/'parents');parent=next(iter(training_examples(tmp_path/'parents')))
    def mutate(s):
        s['family_id']=parent['parent_group_id']
        s['parents']=[{'example_id':parent['example_id'],'family_id':s['family_id'],'split':'train'}]
    r,j=fixture(tmp_path,mutate=mutate)
    with pytest.raises(ValueError,match='parent release required'):normalize(r,j.path)
    result=normalize(r,j.path,parent_release=tmp_path/'parents')
    assert result['proof']['verified_parent_records'][0]['record_sha256']==digest(parent)
    assert result['proof']['parent_release_manifest_sha256']
    def heldout(s):
        mutate(s);s['parents'][0]['example_id']='fixture:1'
    bad,_=fixture(tmp_path,mutate=heldout)
    with pytest.raises(ValueError,match='approved train member'):normalize(bad,j.path,parent_release=tmp_path/'parents')
    with pytest.raises(ValueError,match='sample-only'):normalize(r,j.path,parent_release=raw)


@pytest.mark.parametrize('defect',['mapping','total','host_result','boundary','family','supervision'])
def test_semantic_receipt_checks_reject_rehashed_compositions(tmp_path,defect):
    r,j=fixture(tmp_path);source,_=source_descriptor(tmp_path);record=source_example(r,j.path,source).to_dict()
    proof=record['validation_results']['teacher_bridge']
    if defect=='mapping':proof['host_mapping']['result']['total_minor']='different'
    elif defect=='total':
        final=parse(record['messages'][-1]['content']);final['facts']['total_minor']=9999;record['messages'][-1]['content']=canonical(final)
    elif defect=='host_result':
        result=parse(record['messages'][-2]['content']);result['data']['value']=9999;record['messages'][-2]['content']=canonical(result);proof['host_result']=result
    elif defect=='boundary':proof['history_messages']+=1;proof['generated_messages']-=1
    elif defect=='family':record['parent_group_id']='family:wrong'
    else:record['validation_results']['supervision']='all-assistant-v1'
    proof['composed_messages_sha256']=digest(record['messages'])
    with pytest.raises(ValueError):review_requirements(record)
