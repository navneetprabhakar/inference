"""Pure synthetic tools and scripted runtime controls, never student competence."""
from copy import deepcopy
import pytest
pytest.importorskip('jsonschema')
from slm.tools.protocol import canonical,parse,decision,validate_messages
from slm.tools.local import LocalTools,Session


def call(name,arguments,id='c1'):return {'kind':'call','id':id,'name':name,'arguments':arguments}


@pytest.mark.parametrize('name,args,expected',[
 ('arithmetic',{'operation':'multiply','left':1250,'right':2},{'value':2500}),
 ('arithmetic',{'operation':'subtract','left':10,'right':17},{'value':-7}),
 ('product_lookup',{'product_id':'P001'},'P001'),
 ('product_compare',{'product_ids':['P002','P001']},['P002','P001']),
 ('catalog_search',{'query':'headphones','max_price_minor':7000,'excluded_brands':['Acorn'],'limit':5},['P002']),
 ('catalog_search',{'query':'headphones','max_price_minor':1000,'excluded_brands':[],'limit':5},[]),
 ('document_lookup',{'document_id':'D001'},'Fixture returns window: 14 days with a receipt.')])
def test_five_mock_tools_execute_exact_contracts(name,args,expected):
    registry=LocalTools();r=Session(registry).call(call(name,args))
    assert r['ok'] and r['error'] is None and (r['id'],r['name'])==('c1',name)
    if name=='arithmetic':assert r['data']==expected
    elif name=='product_lookup':assert r['data']['product']['product_id']==expected
    elif name in ('product_compare','catalog_search'):assert [p['product_id'] for p in r['data']['products']]==expected
    else:assert r['data']['body']==expected


@pytest.mark.parametrize('bad',[
 call('unknown',{}),call('arithmetic',{'operation':'multiply','left':True,'right':2}),
 call('arithmetic',{'operation':'multiply','left':1.0,'right':2}),
 call('arithmetic',{'operation':'divide','left':1,'right':2}),
 call('arithmetic',{'operation':'add','left':1000001,'right':2}),
 call('arithmetic',{'operation':'add','left':1,'right':2,'extra':3}),
 call('product_compare',{'product_ids':['P001','P001']}),call('product_compare',{'product_ids':['P001']}),
 call('catalog_search',{'query':' ','max_price_minor':100,'excluded_brands':[],'limit':1}),
 call('document_lookup',{}),call('product_lookup',{'product_id':'P001'},'../oops')])
def test_invalid_calls_never_invoke_handler(bad,monkeypatch):
    registry=LocalTools();seen=[];monkeypatch.setattr(registry,'_execute',lambda *a:seen.append(a))
    with pytest.raises(ValueError):Session(registry).call(bad)
    assert seen==[]


def test_discovery_is_cloned_and_budget_duplicate_registry_mutation_and_large_results_fail_closed():
    registry=LocalTools();assert len(registry.discover())==5
    described=registry.discover();described[0]['input_schema']['required'].append('injected')
    assert described!=registry.discover()
    s=Session(registry,max_calls=2);r=s.call(call('product_lookup',{'product_id':'missing'}))
    assert not r['ok'] and r['error']['code']=='not_found'
    with pytest.raises(ValueError,match='consumed'):s.call(call('document_lookup',{'document_id':'D001'}))
    assert s.attempts==2 and s.executed==1
    with pytest.raises(ValueError,match='budget'):s.call(call('document_lookup',{'document_id':'D001'},'c2'))
    capped=Session(registry,max_result_bytes=256)
    r=capped.call(call('product_compare',{'product_ids':['P001','P002','P003']},'x'*64))
    assert not r['ok'] and r['error']['code']=='result_too_large' and len(canonical(r).encode())<=256
    s=Session(registry);registry._specs['arithmetic']=('changed',*registry._specs['arithmetic'][1:])
    with pytest.raises(ValueError,match='changed'):s.call(call('arithmetic',{'operation':'add','left':1,'right':2}))


@pytest.mark.parametrize('text',['{"kind":"answer","kind":"call"}','{"n":NaN}','{"n":1.0}','{"n":9007199254740992}','['*10+'0'+']'*10])
def test_json_payloads_are_duplicate_free_exact_and_bounded(text):
    with pytest.raises(ValueError):parse(text)


def transcript():
    c=call('arithmetic',{'operation':'multiply','left':1250,'right':2});r=LocalTools().execute(c)
    return [{'role':'user','content':'Two at 1250. Find total.'},{'role':'assistant','content':canonical(c)},
        {'role':'tool','content':canonical(r)},{'role':'assistant','content':canonical({'kind':'answer','text':'Total is 2500.','facts':{'total_minor':2500}})}]


@pytest.mark.parametrize('defect',['id','name','orphan','pending','duplicate','plain_answer','two_calls','extra_field'])
def test_transcript_correlation_order_and_typed_decisions_are_required(defect):
    history=transcript()
    if defect in ('id','name'):
        r=parse(history[2]['content']);r[defect]='different';history[2]['content']=canonical(r)
    elif defect=='orphan':history=history[2:]
    elif defect=='pending':history=history[:2]
    elif defect=='duplicate':history+=deepcopy(history)
    elif defect=='plain_answer':history[-1]['content']='The total is 2500.'
    elif defect=='two_calls':history[1]['content']=canonical([parse(history[1]['content'])]*2)
    else:history[0]['unexpected']=True
    with pytest.raises(ValueError):validate_messages(history)
