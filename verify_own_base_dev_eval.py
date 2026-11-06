"""Synthetic CPU development-evaluator checks with real own-base chat/broker."""
from copy import deepcopy
from own_base_chat import Chat
from own_base_dev_eval import EvaluationAborted,answer_score,fingerprint,number_answer,prepare,run,score_turn
from tokenizer import load
from guards import ResourceStop
import json

class Guard:
    def check(self):pass

def call(a,b,op='add'):return dict(name='calculate',arguments=dict(op=op,a=a,b=b))
def ref(turn,call=0,field='result'):return {'ref':dict(turn=turn,call=call,field=field)}
def turn(user,calls,answer,permit=True,**policy):return dict(user=user,calls=calls,answer=answer,policy=dict(permit_calls=permit,**policy))
def case(turns):return dict(id='synthetic',family='public-synthetic-wiring-only',turns=turns)

def main():
    tok=load();checks=[]
    def evaluate(cases,scripts):
        def factory(c):
            script=iter(scripts[c['id']])
            def generate(prefix,budget):
                value=next(script)
                if isinstance(value,Exception):raise value
                if isinstance(value,str):return tok.encode(value).ids+[50256]
                return tok.encode(json.dumps(value)).ids+[50256]
            return Chat(None,tok,Guard(),generate=generate)
        return run(cases,expected_sha256=fingerprint(cases),chat_factory=factory)
    c=case([turn('Add two and three.',[call(2,3)],dict(mode='number',value=ref(0))),
            turn('Multiply its actual result by two.',[call(ref(0),2,'multiply')],dict(mode='number',value=ref(1))),
            turn('Repeat that actual reading.',[],dict(mode='number',value=ref(1)),False)])
    result=evaluate([c],{'synthetic':[{'call':call(2,3)},{'text':'5'}, {'call':call(5,2,'multiply')},{'text':'10'},{'text':'10'}]})
    assert result['summary']['sessions']==dict(passed=1,total=1,manual_pending=0)
    checks.append('actual prior result chain and no-call recall')
    c=case([turn('Add then multiply.',[call(2,3),call(ref(0),2,'multiply')],dict(mode='number',value=ref(0,1))),
            turn('Repeat the actual first operand.',[],dict(mode='number',value=ref(0,0,'argument:a')),False)])
    result=evaluate([c],{'synthetic':[{'call':call(2,3)},{'call':call(5,2,'multiply')},{'text':'10'},{'text':'2'}]})
    assert result['summary']['sessions']['passed']==1
    checks.append('within-turn explicit dependency and actual argument recall')
    # Wrong first call may still be read faithfully; requested-call pass remains false.
    c=case([turn('Add two and three.',[call(2,3)],dict(mode='number',value=ref(0)))])
    result=evaluate([c],{'synthetic':[{'call':call(2,4)},{'text':'6'}]})
    score=result['sessions'][0]['turns'][0]['score']
    assert not score['passed'] and not score['call_sequence_pass'] and score['faithful_to_actual_observation']
    checks.append('wrong call separated from faithful actual readback')
    c=case([turn('No tools.',[],dict(mode='exact',value='Denied.'),False)])
    result=evaluate([c],{'synthetic':[{'call':call(2,3)},{'text':'Denied.'}]})
    score=result['sessions'][0]['turns'][0]['score']
    assert score['proposal_count']==1 and not score['passed'] and result['summary']['no_call']['passed']==0
    assert not result['sessions'][0]['turns'][0]['response']['frame_records'][0]['broker_decision']['dispatched']
    checks.append('blocked attempt fails no-call despite no dispatch')
    c=case([turn('Three calls.',[call(1,1),call(2,1)],dict(mode='number',value=ref(0,1)))])
    result=evaluate([c],{'synthetic':[{'call':call(1,1)},{'call':call(2,1)},{'call':call(3,1)}]})
    score=result['sessions'][0]['turns'][0]['score'];assert score['proposal_count']==3 and not score['bindings_valid']
    checks.append('quota-exceeding parsed attempt counted without trace')
    c=case([turn('Divide by zero.',[call(2,0,'divide')],dict(mode='error',observation=ref(0,field='ok')))])
    result=evaluate([c],{'synthetic':[{'call':call(2,0,'divide')},{'text':'The calculator failed. No result was returned.'}]})
    assert result['summary']['sessions']['passed']==1
    assert answer_score(c['turns'][0]['answer'],'It succeeded.',[[dict(ok=False)]]) is False
    checks.append('actual error accepts non-teacher wording and rejects invented success')
    c=case([turn('Add two and three.',[call(2,3)],dict(mode='number',value=ref(0)),fixture_for=call(2,3),fixture={'result':91})])
    result=evaluate([c],{'synthetic':[{'call':call(2,3)},{'text':'The fixture reported 91.'}]})
    assert result['summary']['sessions']['passed']==1
    checks.append('counterfactual observed result is authoritative')
    c=case([turn('Output red.',[],dict(mode='exact',value='red')),turn('Correction: blue only.',[],dict(mode='constraints',equals='blue',max_chars=4)),turn('Discuss this.',[],dict(mode='manual',rubric='Assess relevance and factual accuracy.'))])
    result=evaluate([c],{'synthetic':[{'text':'red'},{'text':'blue'},{'text':'Open prose.'}]})
    assert result['summary']['sessions']==dict(passed=0,total=1,manual_pending=1)
    assert result['summary']['turns']==dict(passed=2,total=3,manual_pending=1)
    checks.append('caller-supplied correction constraints and manual-pending session')
    c=case([turn('Hi.',[],dict(mode='exact',value='Hi')),turn('Next.',[],dict(mode='exact',value='Next'))])
    result=evaluate([c],{'synthetic':['{bad']})
    assert result['summary']['turns']['total']==2 and result['summary']['turns']['passed']==0
    checks.append('closed malformed session keeps every planned turn denominator')
    for error in (RuntimeError('decoder fault'),ResourceStop('guard stop'),MemoryError('memory')):
        c=case([turn('Add two and three.',[call(2,3)],dict(mode='number',value=ref(0)))])
        try:evaluate([c],{'synthetic':[{'call':call(2,3)},error]})
        except EvaluationAborted as abort:
            assert abort.__cause__ is error and abort.report['state']=='aborted_infrastructure'
            assert 'summary' not in abort.report and abort.report['planned_turns']==1
            partial=abort.report['sessions'][0]['partial_turn']['result']
            assert partial['answer'] is None and partial['trace'][0]['data']['result']==5
        else:raise AssertionError('infrastructure swallowed')
    checks.append('three infrastructure classes abort with trace and no aggregate score')
    # Binding tampering fails even if prose/result happen to be correct.
    c=case([turn('Add.',[call(2,3)],dict(mode='number',value=ref(0)))])
    result=evaluate([c],{'synthetic':[{'call':call(2,3)},{'text':'5'}]})
    out=deepcopy(result['sessions'][0]['turns'][0]['response']);record=deepcopy(out['trace']);decisions=[out['frame_records'][0]['broker_decision']]
    out['frame_records'][0]['tool_record']['call_id']='wrong'
    assert not score_turn(c['turns'][0],out,[record],record,decisions,set())['bindings_valid']
    checks.append('forged returned binding rejected')
    conversion=dict(name='convert',arguments={'value':1,'from':'km','to':'m'})
    c=case([turn('Convert one kilometre to metres.',[conversion],dict(mode='number',value=ref(0),unit='m'))])
    result=evaluate([c],{'synthetic':[{'call':conversion},{'text':'1000 m'}]})
    assert result['summary']['sessions']['passed']==1
    observations=[[dict(ok=True,data={'result':1000},arguments=conversion['arguments'])]]
    spec=c['turns'][0]['answer']
    for text in ('1000 km','1000','1000 bananas'):
        assert not answer_score(spec,text,observations)
    spec=deepcopy(spec);spec['unit']=ref(0,0,'argument:to')
    assert answer_score(spec,'1000 m',observations)
    assert number_answer('5',5) and not number_answer('5 bananas',5) and not number_answer('5 m',5)
    unitless=deepcopy(c);unitless['turns'][0]['answer'].pop('unit');unitless['turns'][0]['answer']['allow_unitless']=True
    prepare([unitless],fingerprint([unitless]))
    assert answer_score(unitless['turns'][0]['answer'],'1000',observations)
    checks.append('explicit conversion units, actual-unit reference, wrong/missing units and explicit unitless mode')
    def outcome(ti,ci=0,**number_options):
        return dict(mode='observed_status',observation=ref(ti,ci,'ok'),
                    success=dict(mode='number',value=ref(ti,ci),**number_options),
                    error=dict(mode='error',observation=ref(ti,ci,'ok')))
    first=call(2,3,'multiply')
    retry=dict(name='calculate',arguments={k:ref(0,0,'proposal_argument:'+k) for k in ('op','a','b')})
    c=case([turn('Multiply two and three.',[first],outcome(0),fixture_for=first,fixture={'error':'fixture timeout'}),
            turn('Retry the actual prior call.',[retry],outcome(1)),
            turn('Did the actual retry return a number?',[],dict(mode='observed_status',observation=ref(1,0,'ok'),
                 success=dict(mode='exact',value='Yes.'),error=dict(mode='exact',value='No.')),False)])
    result=evaluate([c],{'synthetic':[{'call':first},{'text':'The tool timed out. No result was returned.'},
                                   {'call':first},{'text':'6'},{'text':'Yes.'}]})
    assert result['summary']['sessions']['passed']==1
    assert 'arguments' not in result['sessions'][0]['turns'][0]['response']['trace'][0]
    checks.append('retry uses retained parsed proposal arguments despite absent error-record arguments')
    for intended,actual,text in ((call(2,3),call(2,0,'divide'),'The calculator failed.'),
                                 (call(2,0,'divide'),call(2,3),'5')):
        c=case([turn('Perform the request.',[intended],outcome(0))])
        result=evaluate([c],{'synthetic':[{'call':actual},{'text':text}]})
        scored=result['sessions'][0]['turns'][0]['score']
        assert scored['content_pass'] and scored['faithful_to_actual_observation'] and not scored['call_sequence_pass'] and not scored['passed']
    checks.append('wrong intended calls separated from faithful actual error or success alternatives')
    display=dict(mode='python-significant',digits=9)
    assert number_answer('0.333333333',1/3,display=display)
    assert not number_answer('0.333333333',1/3)
    assert not number_answer('0.333333334',1/3,display=display)
    assert number_answer('1.23456789e+09',1234567890.25,display=display)
    assert number_answer('-0.333333333',-1/3,display=display)
    assert number_answer('1234567890123',1234567890123,display=display)
    # Compare against the actual public formatter; this imports no datasets.
    from tool_teaching import display as public_display
    for value in (1/3,-1/3,1234567890.25,1.2345678912345e-8,1234567890123):
        assert number_answer(public_display(value),value,display=display)
    checks.append('explicit nine-significant display matches public formatter; strict and adjacent-value refusals retained')
    c=case([turn('Divide one by three.',[call(1,3,'divide')],outcome(0,display=display))])
    result=evaluate([c],{'synthetic':[{'call':call(1,3,'divide')},{'text':'0.333333333'}]})
    assert result['summary']['sessions']['passed']==1
    extension_bad=[]
    bad=deepcopy(c);bad['turns'][0]['answer']['success']['value']=ref(0,0,'ok');extension_bad.append([bad])
    for precision in (0,18,True,9.5):
        bad=deepcopy(c);bad['turns'][0]['answer']['success']['display']['digits']=precision;extension_bad.append([bad])
    bad=deepcopy(c);bad['turns'][0]['answer']['observation']=ref(0,0,'result');extension_bad.append([bad])
    bad=deepcopy(c);bad['turns'][0]['answer']['error']=dict(mode='observed_status');extension_bad.append([bad])
    bad=deepcopy(c);bad['turns'][0]['answer']['success']['value']=ref(0,0,'proposal_argument:from');extension_bad.append([bad])
    bad=deepcopy(c);bad['turns'][0]['answer']['success']['unit']='bananas';extension_bad.append([bad])
    bad=deepcopy(c);bad['turns'][0]['answer']['success']['display']['mode']='approximate';extension_bad.append([bad])
    for items in extension_bad:
        try:prepare(items,fingerprint(items))
        except ValueError:pass
        else:raise AssertionError('invalid extension rubric prepared')
    checks.append('ten precision/status/proposal-reference/unit extension refusals before execution')
    c=case([turn('Convert one kilometre to metres.',[conversion],dict(mode='number',value=ref(0),unit='m'))])
    invalid=[]
    bad=deepcopy(c);bad['turns'][0]['answer']['mode']='unknown';invalid.append([bad])
    bad=deepcopy(c);bad['turns'][0]['calls'][0]['arguments']['value']=ref(0);invalid.append([bad])
    bad=deepcopy(c);bad['turns'][0]['answer']['value']=ref(8);invalid.append([bad])
    bad=deepcopy(c);bad['turns'][0]['answer']=dict(mode='constraints');invalid.append([bad])
    invalid.append([c,c])
    bad=deepcopy(c);bad['turns'][0]['policy']['permit_calls']=False;invalid.append([bad])
    bad=deepcopy(c);bad['turns'][0]['policy']['allowed_names']=['calculate'];invalid.append([bad])
    bad=deepcopy(c);bad['turns'][0]['answer']=dict(mode='constraints',contains=[]);invalid.append([bad])
    bad=deepcopy(c);bad['turns'][0]['answer'].pop('unit');invalid.append([bad])
    for items in invalid:
        try:prepare(items,fingerprint(items))
        except ValueError:pass
        else:raise AssertionError('invalid rubric prepared')
    try:prepare([c],'0'*64)
    except ValueError:pass
    else:raise AssertionError('wrong freeze accepted')
    checks.append('ten malformed/unknown/unpinned/policy/unit manifests refused before execution')
    print(json.dumps(dict(state='passed',checks=checks,model_loaded=False,gpu_operations=False,corpus_read=False,benchmark_completeness_claim=False),indent=2))

if __name__=='__main__':main()
