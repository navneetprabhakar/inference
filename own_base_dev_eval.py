"""Pure caller-supplied development rubric runner for own_base_chat.Chat.

No corpus/model loading. Frozen, exposed development evidence only; conservative
text checks are not semantic judges. Infrastructure aborts never yield a score.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import re
from own_base_chat import policy_text
from tools import FIELDS,UNITS

MODES={'number','error','exact','constraints','manual','observed_status'}
NUMBER=re.compile(r'(?<![\w.])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?![\w.])')


def fingerprint(cases):
    return hashlib.sha256(json.dumps(cases,sort_keys=True,ensure_ascii=False,
                                    allow_nan=False,separators=(',',':')).encode('utf-8')).hexdigest()


def _ref(value,turn,call_limit):
    if not isinstance(value,dict):return
    if set(value)!={'ref'} or type(value['ref']) is not dict:raise ValueError('invalid explicit reference')
    r=value['ref']
    if set(r)!={'turn','call','field'}:raise ValueError('reference fields')
    if type(r['turn'])!=int or type(r['call'])!=int or not 0<=r['turn']<=turn or r['call']<0:
        raise ValueError('reference position')
    if r['turn']==turn and r['call']>=call_limit:raise ValueError('forward/self reference')
    if r['field'] not in {'result','ok','argument:a','argument:b','argument:op','argument:value','argument:from','argument:to','proposal_argument:a','proposal_argument:b','proposal_argument:op','proposal_argument:value','proposal_argument:from','proposal_argument:to'}:
        raise ValueError('unknown reference field')


def validate_answer(answer,ti,call_limit):
    mode=answer.get('mode') if isinstance(answer,dict) else None
    if mode not in MODES:raise ValueError('unknown answer mode')
    fields={'number':{'mode','value','unit','allow_unitless','display'},'error':{'mode','observation'},'exact':{'mode','value'},
            'constraints':{'mode','equals','contains','forbids','max_chars'},'manual':{'mode','rubric'},'observed_status':{'mode','observation','success','error'}}[mode]
    if set(answer)-fields:raise ValueError('unknown answer fields')
    required={'number':{'value'},'error':{'observation'},'exact':{'value'},'constraints':set(),'manual':{'rubric'},'observed_status':{'observation','success','error'}}[mode]
    if not required<=answer.keys():raise ValueError('missing answer rubric')
    if mode in {'number','exact'}:
        _ref(answer['value'],ti,call_limit)
        if mode=='number' and isinstance(answer['value'],dict) and answer['value']['ref']['field'] not in {'result','argument:a','argument:b','argument:value','proposal_argument:a','proposal_argument:b','proposal_argument:value'}:
            raise ValueError('numeric answer reference must name a numeric field')
        if not isinstance(answer['value'],dict):
            if mode=='number' and type(answer['value']) not in (int,float):raise ValueError('numeric rubric needs number/reference')
            if mode=='exact' and not isinstance(answer['value'],str):raise ValueError('exact rubric needs text/reference')
    if mode=='number' and 'allow_unitless' in answer:
        if answer['allow_unitless'] is not True or 'unit' in answer:raise ValueError('explicit unitless mode must not conflict with a unit')
    if mode=='number' and 'unit' in answer:
        _ref(answer['unit'],ti,call_limit)
        if isinstance(answer['unit'],dict):
            if answer['unit']['ref']['field'] not in {'argument:to','proposal_argument:to'}:raise ValueError('unit reference must use actual conversion destination')
        elif not isinstance(answer['unit'],str) or answer['unit'] not in UNITS:raise ValueError('unknown expected unit')
    if mode in {'error','observed_status'}:
        _ref(answer['observation'],ti,call_limit)
        if not isinstance(answer['observation'],dict) or answer['observation']['ref']['field']!='ok':raise ValueError('error requires explicit observed ok reference')
    if mode=='manual' and (not isinstance(answer['rubric'],str) or not answer['rubric'].strip()):raise ValueError('manual rubric required')
    if mode=='constraints':
        if len(answer)==1 or not ('equals' in answer or 'max_chars' in answer or answer.get('contains') or answer.get('forbids')):raise ValueError('empty constraint rubric')
        for key in ('contains','forbids'):
            if key in answer and (not isinstance(answer[key],list) or any(not isinstance(x,str) or not x for x in answer[key])):raise ValueError('invalid text constraints')
        if 'equals' in answer and not isinstance(answer['equals'],str):raise ValueError('equals must be text')
        if 'max_chars' in answer and (type(answer['max_chars'])!=int or answer['max_chars']<1):raise ValueError('invalid character bound')
    if mode=='number' and 'display' in answer:
        display=answer['display']
        if (type(display)!=dict or set(display)!={'mode','digits'} or display['mode']!='python-significant'
                or type(display['digits'])!=int or not 1<=display['digits']<=17):
            raise ValueError('invalid declared numeric display precision')
    if mode=='observed_status':
        for branch in ('success','error'):
            if not isinstance(answer[branch],dict) or answer[branch].get('mode')=='observed_status':
                raise ValueError('status branches must be flat answer rubrics')
            validate_answer(answer[branch],ti,call_limit)


def prepare(cases,expected_sha256):
    """Validate every rubric before creating any chat. No inferred dependencies."""
    cases=deepcopy(cases)
    if not isinstance(cases,list) or not cases or fingerprint(cases)!=expected_sha256:
        raise ValueError('nonempty caller-pinned cases required')
    ids=set()
    for case in cases:
        if set(case)!={'id','family','turns'} or not isinstance(case['id'],str) or not case['id'] or case['id'] in ids:
            raise ValueError('invalid/duplicate case identity')
        ids.add(case['id'])
        if not isinstance(case['family'],str) or not case['family'] or not isinstance(case['turns'],list) or not case['turns']:
            raise ValueError('family and turns required')
        for ti,turn in enumerate(case['turns']):
            if set(turn)!={'user','policy','calls','answer'} or not isinstance(turn['user'],str) or not turn['user'].strip():
                raise ValueError('invalid turn')
            policy=turn['policy']
            if type(policy)!=dict or 'permit_calls' not in policy or set(policy)-{'permit_calls','allowed_names','fixture_for','fixture'}:
                raise ValueError('explicit current-turn policy required')
            policy_text(policy['permit_calls'],policy.get('allowed_names'))
            if ('fixture_for' in policy)!=('fixture' in policy):raise ValueError('fixture binding incomplete')
            if not isinstance(turn['calls'],list) or len(turn['calls'])>2:raise ValueError('calls must fit turn quota')
            if turn['calls'] and not policy['permit_calls']:raise ValueError('expected calls violate disabled policy')
            allowed=set(policy.get('allowed_names',FIELDS))
            for ci,call in enumerate(turn['calls']):
                if type(call)!=dict or set(call)!={'name','arguments'} or call['name'] not in FIELDS or type(call['arguments'])!=dict or set(call['arguments'])!=FIELDS[call['name']]:
                    raise ValueError('invalid expected call')
                if call['name'] not in allowed:raise ValueError('expected call outside allowed tool scope')
                for value in call['arguments'].values():_ref(value,ti,ci)
            validate_answer(turn['answer'],ti,len(turn['calls']))
        if sum(len(t['calls']) for t in case['turns'])>4:raise ValueError('expected calls exceed session quota')
        # Verify every reference against the frozen expected call topology.
        for turn in case['turns']:
            answer=turn['answer']
            answers=[answer]+([answer['success'],answer['error']] if answer['mode']=='observed_status' else [])
            for rubric in answers:
                if rubric['mode']=='number':
                    value=rubric['value'];target=None
                    if isinstance(value,dict):
                        ref=value['ref']
                        if ref['call']<len(case['turns'][ref['turn']]['calls']):target=case['turns'][ref['turn']]['calls'][ref['call']]
                    elif turn['calls']:target=turn['calls'][-1]
                    if target and target['name']=='convert' and 'unit' not in rubric and rubric.get('allow_unitless') is not True:
                        raise ValueError('conversion rubric requires unit or explicit unitless mode')
            values=[v for c in turn['calls'] for v in c['arguments'].values()]+[v for a in answers for v in a.values()]
            for value in values:
                if isinstance(value,dict) and 'ref' in value:
                    r=value['ref']
                    calls=case['turns'][r['turn']]['calls']
                    if r['call']>=len(calls):raise ValueError('reference to nonexistent expected observation')
                    if ':' in r['field'] and r['field'].split(':',1)[1] not in FIELDS[calls[r['call']]['name']]:
                        raise ValueError('argument reference incompatible with expected tool schema')
    return cases


def resolve(value,observations,proposals=None):
    if not isinstance(value,dict):return value
    r=value['ref']
    if r['field'].startswith('proposal_argument:'):
        if proposals is None:raise ValueError('actual parsed proposals required')
        try:return proposals[r['turn']][r['call']]['arguments'][r['field'].split(':',1)[1]]
        except (IndexError,KeyError):raise ValueError('required actual proposal argument absent') from None
    try:record=observations[r['turn']][r['call']]
    except IndexError:raise ValueError('required actual observation absent') from None
    if r['field']=='ok':return record['ok']
    if r['field']=='result':
        if record.get('ok') is not True:raise ValueError('required actual numeric result absent')
        return record['data']['result']
    return record['arguments'][r['field'].split(':',1)[1]]


def number_answer(text,want,unit=None,display=None):
    if type(want) not in (int,float) or not isinstance(text,str):return False
    expected=Decimal(str(want))
    if not expected.is_finite():return False
    if display is not None:
        # Match the declared public generator formatter exactly: integral
        # values stay integral; otherwise Python significant-digit formatting.
        rendered_want=str(int(want)) if int(want)==want else format(want,f".{display['digits']}g")
        expected=Decimal(rendered_want)
    matches=list(NUMBER.finditer(text))
    if not matches or any(Decimal(m.group())!=expected for m in matches):return False
    if re.search(r'\b(not|never|unknown|maybe|approximately|about|expected|should|might|failed|error)\b',text,re.I):return False
    # Explicit readback wrappers; arbitrary prose with a stray number is not a pass.
    rendered=NUMBER.sub('#',text).strip().rstrip('.!?')
    suffix='' if unit is None else r'\s+'+re.escape(unit)
    return re.fullmatch(r'(?:(?:the (?:tool|fixture|calculator|converter|result|value|answer)|it)\s+(?:reported|returned|is|was|gave)\s+)?#'+suffix,rendered,re.I) is not None


def answer_score(spec,text,observations,proposals=None):
    mode=spec['mode']
    if mode=='manual':return None
    if not isinstance(text,str):return False
    try:
        if mode=='observed_status':
            status=resolve(spec['observation'],observations,proposals)
            if type(status)!=bool:return False
            return answer_score(spec['success' if status else 'error'],text,observations,proposals)
        if mode=='number':return number_answer(text,resolve(spec['value'],observations,proposals),resolve(spec['unit'],observations,proposals) if 'unit' in spec else None,spec.get('display'))
        if mode=='exact':return text==str(resolve(spec['value'],observations,proposals))
        if mode=='error':
            observed=resolve(spec['observation'],observations,proposals)
            return (observed is False and not NUMBER.search(text) and
                    re.search(r'\b(error|failed|timeout|timed out|unavailable|denied|rejected|no (?:verified |numeric )?(?:result|number|value))\b',text,re.I) is not None and
                    re.search(r'\b(?:no error|did not fail|succeeded|successful)\b',text,re.I) is None)
        return (('equals' not in spec or text==spec['equals']) and
                all(s in text for s in spec.get('contains',[])) and
                all(s not in text for s in spec.get('forbids',[])) and
                ('max_chars' not in spec or len(text)<=spec['max_chars']))
    except (ValueError,KeyError,IndexError,TypeError):return False


def score_turn(turn,out,observations,authoritative,decisions,seen_ids,proposals=None):
    attempts=[f for f in out.get('frame_records',[]) if 'call' in f.get('parsed',{})]
    trace=out.get('trace',[]);bindings=trace==authoritative
    bound=[]
    for frame in attempts:
        record=frame.get('tool_record');decision=frame.get('broker_decision')
        if record is None or decision is None:bindings=False;continue
        cid=record.get('call_id')
        if cid in seen_ids or cid in bound or decision.get('call_id')!=cid or record not in authoritative or decision not in decisions:
            bindings=False
        bound.append(cid)
        call=frame['parsed']['call']
        if record.get('ok') is True and (record.get('name')!=call.get('name') or record.get('arguments')!=call.get('arguments')):bindings=False
    if bound!=[r.get('call_id') for r in trace]:bindings=False
    seen_ids.update(r.get('call_id') for r in trace)
    matched=[]
    for index,expected in enumerate(turn['calls']):
        try:
            wanted=dict(name=expected['name'],arguments={k:resolve(v,observations,proposals) for k,v in expected['arguments'].items()})
            matched.append(index<len(attempts) and attempts[index]['parsed']['call']==wanted)
        except (ValueError,KeyError,IndexError,TypeError):matched.append(False)
    call_pass=bindings and len(attempts)==len(turn['calls']) and all(matched)
    content=answer_score(turn['answer'],out.get('answer'),observations,proposals)
    protocol=not out.get('failure') and bindings
    passed=False if not protocol or not call_pass or content is False else (None if content is None else True)
    readback=turn['answer']['mode'] in {'number','error','observed_status'} and isinstance(turn['answer'].get('value',turn['answer'].get('observation')),dict)
    observation_present=False
    if readback:
        try:
            resolve(turn['answer'].get('value',turn['answer'].get('observation')),observations,proposals)
            observation_present=True
        except (ValueError,KeyError,IndexError,TypeError):pass
    return dict(passed=passed,protocol_pass=protocol,call_sequence_pass=call_pass,content_pass=content,
                proposal_count=len(attempts),matched_calls=matched,no_call_required=not turn['calls'],
                expected_readback=readback,observation_present=observation_present,faithful_to_actual_observation=content if readback else None,
                manual_pending=content is None,bindings_valid=bindings)


class EvaluationAborted(RuntimeError):
    def __init__(self,report):super().__init__('development evaluation aborted by infrastructure');self.report=report


def run(cases,*,expected_sha256,chat_factory):
    cases=prepare(cases,expected_sha256)
    report=dict(state='running',cases_sha256=expected_sha256,planned_sessions=len(cases),
                planned_turns=sum(len(c['turns']) for c in cases),sessions=[],training_admitted=False)
    try:
        for case in cases:
            chat=chat_factory(case);session=dict(id=case['id'],family=case['family'],turns=[])
            report['sessions'].append(session);observations=[];proposals=[];seen=set()
            for turn in case['turns']:
                trace_start=len(chat.session.trace);decision_start=len(chat.session.decisions);record_start=len(chat.turn_records)
                try:out=chat.turn(turn['user'],**turn['policy'])
                except Exception:
                    if len(chat.turn_records)>record_start:session['partial_turn']=deepcopy(chat.turn_records[-1])
                    raise
                if out.get('failure_kind')=='infrastructure':raise RuntimeError('chat returned infrastructure failure')
                observations.append(chat.session.trace[trace_start:])
                saved=chat.turn_records[-1]['result']
                if saved.get('frame_records',[])!=out.get('frame_records',[]):raise RuntimeError('returned frames differ from retained parsed frames')
                proposals.append([deepcopy(f['parsed']['call']) for f in saved.get('frame_records',[]) if 'call' in f.get('parsed',{})])
                score=score_turn(turn,out,observations,chat.session.trace[trace_start:],chat.session.decisions[decision_start:],seen,proposals)
                session['turns'].append(dict(response=deepcopy(out),score=score,policy=deepcopy(turn['policy'])))
            scores=[t['score']['passed'] for t in session['turns']]
            session['passed']=False if False in scores else (None if None in scores else True)
    except Exception as error:
        report.update(state='aborted_infrastructure',error_type=type(error).__name__,error=str(error))
        raise EvaluationAborted(report) from error
    turns=[t for s in report['sessions'] for t in s['turns']]
    def fraction(values):return dict(passed=sum(v is True for v in values),total=len(values),manual_pending=sum(v is None for v in values))
    report.update(state='complete',summary=dict(sessions=fraction([s['passed'] for s in report['sessions']]),
        turns=fraction([t['score']['passed'] for t in turns]),
        no_call=fraction([t['score']['call_sequence_pass'] and t['score']['protocol_pass'] for t in turns if t['score']['no_call_required']]),
        requested_calls=fraction([t['score']['call_sequence_pass'] for t in turns if not t['score']['no_call_required']]),
        first_call_per_required_turn=fraction([t['score']['matched_calls'][0] for t in turns if t['score']['matched_calls']]),
        first_call_per_tool_session=fraction([next(t['score']['matched_calls'][0] for t in s['turns'] if t['score']['matched_calls']) for s in report['sessions'] if any(t['score']['matched_calls'] for t in s['turns'])]),
        readbacks_with_observation=fraction([t['score']['observation_present'] for t in turns if t['score']['expected_readback']]),
        faithful_given_observation=fraction([t['score']['faithful_to_actual_observation'] for t in turns if t['score']['expected_readback'] and t['score']['observation_present']]),
        forbidden_successful_calls=sum(r.get('ok') is True for t in turns if not t['policy']['permit_calls'] for r in t['response']['trace']),
        unknown_successful_calls=sum(r.get('ok') is True and r.get('name') not in FIELDS for t in turns for r in t['response']['trace']),
        all_expected_readbacks=fraction([t['score']['faithful_to_actual_observation'] for t in turns if t['score']['expected_readback']]),
        protocol_failures=sum(not t['score']['protocol_pass'] for t in turns)))
    return report
