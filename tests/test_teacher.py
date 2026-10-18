from copy import deepcopy
from datetime import datetime,timezone
import json
import sqlite3
import pytest
pytest.importorskip('jsonschema')
from slm.data.schema import digest
from slm.teacher.journal import Journal
from slm.teacher.workflow import Recipe,Approval,request_payload,generate,parse_json
from slm.teacher.providers import Replay,OpenAIResponses
from slm.teacher.scenarios import fixture_scenario,output_schema,execute_mock,validate


@pytest.fixture(autouse=True)
def fixed_quote_test_clock(monkeypatch):
    import slm.teacher.workflow as module
    class FixedClock(datetime):
        @classmethod
        def now(cls,tz=None):return datetime(2026,10,18,tzinfo=timezone.utc)
    monkeypatch.setattr(module,'datetime',FixedClock)


def candidate(s):
    return {'reply':'The total is 2500 minor currency units.','facts':deepcopy(s['facts']),
        'action':deepcopy(s['expected_action']),'tool_result':execute_mock(s['expected_action']),
        'style':s['style'],'content_category':s['content_category']}


def raw(recipe,value,**kw):
    result={'id':'resp-offline-fixture','model':recipe.model_id,'status':'completed',
        'usage':{'input_tokens':100,'output_tokens':200},'service_tier':'default',
        'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':json.dumps(value)}]}]}
    result.update(kw);return result


def setup(tmp_path,*,billable=False,value=None,model_id="gpt-6-luna"):
    s=fixture_scenario();schema=output_schema(s)
    r=Recipe('Synthetic transport fixture; not an actual teacher', model_id,'openai-responses-v1' if billable else Replay.identity)
    payload=request_payload(r,s,schema)
    p=Replay({digest(payload):raw(r,candidate(s) if value is None else value)})
    if billable:p.identity=r.provider_id;p.billable=True
    journal=Journal(tmp_path/'journal.sqlite',1_000_000_000 if billable else 0,'synthetic-test-only')
    return s,schema,r,p,journal


def approval(model_id="gpt-6-luna"):
    input_rate,output_rate={"gpt-6-luna":(250,750),"gpt-5.6-luna":(500,1800)}[model_id]
    return Approval('synthetic-test-only',model_id,'synthetic terms fixture, not actual approval',
        'synthetic access fixture','synthetic pricing fixture',
        '2026-10-19',('sfw',),922000,input_rate,output_rate)


def run(items,**kwargs):
    s,schema,r,p,j=items
    return generate(j,p,r,s,schema,validate,'structured-oracle-v1',**kwargs)


def test_cache_survives_restart_and_revalidates_without_new_generation(tmp_path):
    items=setup(tmp_path);s,schema,r,p,j=items
    a=run(items);assert not a['cache_hit'] and p.calls==1
    restarted=Journal(j.path,0,'synthetic-test-only')
    b=generate(restarted,p,r,s,schema,lambda *_:{'new_check':False},'new-validator-v2')
    assert b['cache_hit'] and p.calls==1 and b['validation']['status']=='rejected'
    assert a['request_key']==b['request_key'] and b['validation']['validator_version']=='new-validator-v2'
    assert a['validation']['status']=='pending_human_review' and not a['validation']['training_eligible']
    assert b['request_payload']==request_payload(r,s,schema) and b['family_id']==s['family_id']


def test_no_budget_approval_means_no_paid_provider_call_or_reservation(tmp_path):
    items=setup(tmp_path,billable=True)
    with pytest.raises(ValueError,match='authorization is absent'):run(items)
    assert items[3].calls==0 and items[4].summary()['states']=={}


@pytest.mark.parametrize('model_id',['gpt-6-luna','gpt-5.6-luna'])
def test_paid_fixture_accounting_preserves_full_model_reservation_and_rejects_underquote(tmp_path,model_id):
    items=setup(tmp_path,billable=True,model_id=model_id);a=approval(model_id)
    value=run(items,approval=a)
    assert value['journal']['states']['complete']['accounted_or_reserved_nanousd']==100*a.input_nanousd_per_token+200*a.output_nanousd_per_token
    assert value['journal']['settled_cost_usd'] is None
    assert run(items,approval=a)['cache_hit'] and items[3].calls==1
    altered=deepcopy(items[0]);altered['scenario_id']='new-variant'
    bad=Approval(**{**a.__dict__,'max_input_tokens':100})
    with pytest.raises(ValueError,match='understates'):
        generate(items[4],items[3],items[2],altered,items[1],validate,'v1',bad)
    assert items[3].calls==1


def test_budget_cannot_reset_and_rejects_request_before_transport(tmp_path):
    s,schema,r,p,_=setup(tmp_path,billable=True)
    j=Journal(tmp_path/'small.sqlite',100,'synthetic-test-only')
    with pytest.raises(ValueError,match='exceeds authorized'):generate(j,p,r,s,schema,validate,'v1',approval())
    assert p.calls==0
    with pytest.raises(ValueError,match='refusing reset'):Journal(j.path,200,'synthetic-test-only')
    with pytest.raises(ValueError,match='refusing reset'):Journal(j.path,100,'different-approval')


def test_timeout_uncertain_usage_is_reserved_and_never_retried(tmp_path):
    s,schema,r,p,j=setup(tmp_path,billable=True)
    def timeout(_):p.calls+=1;raise TimeoutError('fixture timeout')
    p.generate=timeout
    with pytest.raises(TimeoutError):generate(j,p,r,s,schema,validate,'v1',approval())
    state=j.summary();assert state['halted'] and state['states']['uncertain']['accounted_or_reserved_nanousd']==922000*250+2048*750
    with pytest.raises(RuntimeError,match='never replay'):generate(j,p,r,s,schema,validate,'v1',approval())
    s['scenario_id']='another'
    with pytest.raises(RuntimeError,match='halted'):generate(j,p,r,s,schema,validate,'v1',approval())
    assert p.calls==1


def test_crash_reservation_and_single_outstanding_request_block_duplicate_calls(tmp_path):
    items=setup(tmp_path);s,schema,r,p,j=items
    j.reserve('crashed-worker',0)
    restarted=Journal(j.path,0,'synthetic-test-only')
    with pytest.raises(RuntimeError,match='Outstanding'):generate(restarted,p,r,s,schema,validate,'v1')
    assert p.calls==0


def test_cached_response_tampering_is_refused_without_fresh_call(tmp_path):
    items=setup(tmp_path);run(items)
    with sqlite3.connect(items[4].path) as db:db.execute("UPDATE requests SET response='{}'")
    with pytest.raises(ValueError,match='checksum'):run(items)
    assert items[3].calls==1


@pytest.mark.parametrize('change',['split','parent'])
def test_held_out_generation_or_derivative_is_rejected_before_transport(tmp_path,change):
    items=setup(tmp_path);s=items[0]
    if change=='split':s['split']='test'
    else:s['parents']=[{'example_id':'heldout-1','family_id':s['family_id'],'split':'validation'}]
    with pytest.raises(ValueError,match='Held-out'):run(items)
    assert items[3].calls==0 and items[4].summary()['states']=={}


@pytest.mark.parametrize('defect',['arguments','tool_result','facts','style','additional','invalid_json','duplicate_key','refusal','incomplete'])
def test_schema_and_executable_failures_never_gain_training_eligibility(tmp_path,defect):
    items=setup(tmp_path);s,schema,r,p,j=items;value=candidate(s)
    if defect=='arguments':value['action']['arguments']['quantity']=3
    if defect=='tool_result':value['tool_result']['total_minor']=999
    if defect=='facts':value['facts']['quantity']=True
    if defect=='style':value['style']='caveman'
    if defect=='additional':value['extra']='not in schema'
    response=raw(r,value)
    if defect=='invalid_json':response['output'][0]['content'][0]['text']='not JSON'
    if defect=='duplicate_key':response['output'][0]['content'][0]['text']='{"reply":"a","reply":"b"}'
    if defect=='refusal':response['output'][0]['content']=[{'type':'refusal','refusal':'fixture refusal'}]
    if defect=='incomplete':response['status']='incomplete'
    p.records[digest(request_payload(r,s,schema))]=response
    result=run(items)
    assert result['validation']['status']=='rejected' and not result['validation']['training_eligible']
    assert run(items)['cache_hit'] and p.calls==1  # rejected responses still incurred a request


def test_free_text_truth_and_style_are_not_claimed_by_structured_checks(tmp_path):
    items=setup(tmp_path);s,schema,r,p,j=items;value=candidate(s)
    value['reply']='The total is 999999. This deliberately contradicts the valid metadata.'
    p.records[digest(request_payload(r,s,schema))]=raw(r,value)
    result=run(items)['validation']
    assert result['semantic_passed'] and not result['free_text_verified']
    assert not result['style_verified'] and not result['content_verified'] and not result['training_eligible']


def test_remote_schema_refs_cannot_trigger_network_resolution(tmp_path):
    items=setup(tmp_path);items[1]['$ref']='https://example.org/never-fetch'
    with pytest.raises(ValueError,match='Reference-free'):run(items)
    assert items[3].calls==0


def test_provider_usage_over_limit_halts_and_keeps_full_reservation(tmp_path):
    items=setup(tmp_path,billable=True);s,schema,r,p,j=items
    response=raw(r,candidate(s));response['usage']['output_tokens']=999999
    p.records[digest(request_payload(r,s,schema))]=response
    with pytest.raises(ValueError,match='usage exceeds'):run(items,approval=approval())
    assert j.summary()['halted'] and 'uncertain' in j.summary()['states']


def test_http_adapter_without_credentials_performs_no_request(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    import slm.teacher.providers as module
    def forbidden(*args):raise AssertionError('No HTTP attempt permitted')
    monkeypatch.setattr(module,'build_opener',forbidden)
    with pytest.raises(RuntimeError,match='OPENAI_API_KEY'):OpenAIResponses().generate({})


def test_invalid_json_numbers_are_rejected():
    for text in ('{"x":NaN}','{"x":1e999}'):
        with pytest.raises(ValueError,match='Nonfinite'):parse_json(text)


def test_http_contract_uses_fixed_endpoint_one_attempt_and_no_credential_persistence(tmp_path,monkeypatch):
    import slm.teacher.providers as module
    items=setup(tmp_path,billable=True);s,schema,r,_,journal=items
    calls=[]
    class Response:
        def read(self,limit):return json.dumps(raw(r,candidate(s))).encode()
        def __enter__(self):return self
        def __exit__(self,*args):pass
    class Opener:
        def open(self,request,timeout):
            calls.append(request)
            assert request.full_url=='https://api.openai.com/v1/responses' and timeout==60
            payload=json.loads(request.data)
            assert payload['store'] is False and payload['service_tier']=='default'
            assert payload['text']['format']['strict'] and 'tools' not in payload
            assert 'temperature' not in payload and payload['reasoning']['effort']=='none'
            return Response()
    monkeypatch.setenv('OPENAI_API_KEY','fixture-key')
    monkeypatch.setattr(module,'build_opener',lambda *_:Opener())
    result=generate(journal,OpenAIResponses(),r,s,schema,validate,'v1',approval())
    assert len(calls)==1 and result['validation']['status']=='pending_human_review'
    assert b'fixture-key' not in journal.path.read_bytes() and 'fixture-key' not in json.dumps(result)


def test_expired_or_category_mismatched_approval_prevents_transport(tmp_path):
    items=setup(tmp_path,billable=True);a=approval()
    for fields in ({'valid_until_utc':'2000-01-01'},{'allowed_categories':('adult_topic',)},
                   {'model_id':'gpt-5.6-luna'},{'valid_until_utc':'2099-01-01'}):
        bad=Approval(**{**a.__dict__,**fields})
        with pytest.raises(ValueError):run(items,approval=bad)
    assert items[3].calls==0 and items[4].summary()['states']=={}


def test_concurrent_workers_cannot_duplicate_reservations(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    j=Journal(tmp_path/'parallel.sqlite',100,'synthetic-test-only');barrier=Barrier(2)
    def reserve(i):
        barrier.wait(timeout=5)
        try:j.reserve(str(i),60);return 'reserved'
        except RuntimeError:return 'refused'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(reserve,[1,2]))
    assert sorted(results)==['refused','reserved']
    assert j.summary()['states']['reserved']=={'requests':1,'accounted_or_reserved_nanousd':60}


def test_shipped_live_configuration_is_disabled_before_reading_scenario_or_credentials(tmp_path,monkeypatch):
    from pathlib import Path
    from slm.teacher.run import run as run_config
    import slm.teacher.providers as module
    def forbidden(*args):raise AssertionError('No network')
    monkeypatch.setattr(module,'build_opener',forbidden)
    config=Path(__file__).resolve().parents[1]/'configs/teacher-disabled.json'
    with pytest.raises(ValueError,match='disabled'):run_config(config,tmp_path/'missing-scenario',tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_request_count_cap_survives_restarts_and_cache_reads_do_not_consume_it(tmp_path):
    j=Journal(tmp_path/'count.sqlite',0,'synthetic-test-only',max_requests=1)
    j.reserve('first',0);j.finish('first',{'fixture':True},0)
    restarted=Journal(j.path,0,'synthetic-test-only',max_requests=1)
    assert restarted.cached('first')=={'fixture':True}
    with pytest.raises(ValueError,match='request-count'):restarted.reserve('second',0)
    with pytest.raises(ValueError,match='refusing reset'):Journal(j.path,0,'synthetic-test-only',max_requests=2)


def test_failed_result_publication_reuses_paid_fixture_cache_on_retry(tmp_path,monkeypatch):
    from dataclasses import asdict
    import slm.teacher.run as module
    items=setup(tmp_path,billable=True);s,schema,r,p,_=items
    class PaidFixture:
        identity=p.identity
        billable=True
        def generate(self,payload):return p.generate(payload)
    monkeypatch.setattr(module,'OpenAIResponses',PaidFixture)
    config={'live_enabled':True,'recipe':asdict(r),'approval':asdict(approval()),
        'journal':{'path':str(tmp_path/'live.sqlite'),'cap_nanousd':1_000_000_000,
                   'authorization_id':'synthetic-test-only','max_requests':2}}
    (tmp_path/'config.json').write_text(json.dumps(config));(tmp_path/'scenario.json').write_text(json.dumps(s))
    original=module.os.rename
    def interrupted(*args):raise OSError('fixture publication failure')
    monkeypatch.setattr(module.os,'rename',interrupted)
    with pytest.raises(OSError):module.run(tmp_path/'config.json',tmp_path/'scenario.json',tmp_path/'output')
    assert p.calls==1 and not (tmp_path/'output').exists()
    assert not list(tmp_path.glob('.teacher-result-*'))
    monkeypatch.setattr(module.os,'rename',original)
    result=module.run(tmp_path/'config.json',tmp_path/'scenario.json',tmp_path/'output')
    assert result['cache_hit'] and p.calls==1 and (tmp_path/'output/record.json').exists()
