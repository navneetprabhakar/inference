"""Exposed development review only. Never modifies raw reports or rubrics."""
import collections,hashlib,json,pathlib,sys
from fractions import Fraction
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from own_base_dev_eval import resolve,number_answer
OUT=pathlib.Path(__file__).resolve().parent
RAW=ROOT/'runs/own-base-dev-grounded-diagnostic-01/primary_tools.json';CASES=ROOT/'data/own-base-tool-dev-rubrics-v4/cases.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,v):(OUT/name).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
r=json.loads(RAW.read_text());cases={c['id']:c for c in json.loads(CASES.read_text())};pins={str(p.relative_to(ROOT)):sha(p) for p in [RAW,CASES]}
partition=collections.Counter();calls=collections.Counter();args=collections.Counter();readbacks=collections.Counter();failures=collections.Counter();answers=collections.Counter();families=collections.defaultdict(collections.Counter);modes=collections.defaultdict(collections.Counter);names=collections.defaultdict(collections.Counter);slot_details=[];decisions=[];examples=[];equivalent=[];overlay_sessions=overlay_turns=0;full_families=collections.defaultdict(collections.Counter);pending_families=collections.Counter();required_no_call_answers=collections.Counter();success_turns=[]
def arithmetic(c):
 if c['name']!='calculate':raise ValueError()
 a,b=map(lambda x:Fraction(str(x)),[c['arguments']['a'],c['arguments']['b']]);op=c['arguments']['op'];return {'add':lambda:a+b,'subtract':lambda:a-b,'multiply':lambda:a*b,'divide':lambda:a/b}[op]()
for session in r['sessions']:
 case=cases[session['id']];observations=[];proposals=[];passed=[]
 for i,t in enumerate(session['turns']):
  expected=case['turns'][i];response=t['response'];score=t['score'];family='/'.join(session['family'].split('/')[:2]);observations.append(response['trace']);actual=[f['parsed']['call'] for f in response['frame_records'] if 'call' in f.get('parsed',{})];proposals.append(actual)
  answers[response['answer']]+=1;failures[response['failure_kind'] or 'none']+=1
  key='raw_pass' if score['passed'] is True else 'protocol_failure' if not score['protocol_pass'] else 'wrong_call_sequence' if not score['call_sequence_pass'] else 'manual_pending' if score['manual_pending'] else 'content_failure'
  partition[key]+=1
  for bucket in [families[family],full_families[session['family']],modes[expected['answer']['mode']]]:
   bucket['turns']+=1;bucket[key]+=1;bucket['required_call_turns']+=bool(expected['calls']);bucket['no_parsed_call']+=bool(expected['calls']) and not actual
  if expected['calls'] and not actual:required_no_call_answers[response['answer']]+=1
  if expected['calls']:calls['required_turns']+=1;calls['required_turn_no_parsed_call']+=not actual;calls['required_turn_no_call_protocol_valid']+=not actual and score['protocol_pass']
  for j,want in enumerate(expected['calls']):
   names[want['name']]['expected_slots']+=1;detail=dict(id=session['id'],turn=i,slot=j,requested=want,actual=actual[j] if j<len(actual) else None)
   try:resolved=dict(name=want['name'],arguments={k:resolve(v,observations,proposals) for k,v in want['arguments'].items()})
   except (ValueError,KeyError,IndexError,TypeError):resolved=None
   detail['resolved']=resolved
   if j>=len(actual):kind='missing_proposal'
   elif resolved is None:kind='unresolvable_expected_dependency'
   elif actual[j]['name']!=resolved['name']:kind='wrong_tool'
   elif actual[j]==resolved:kind='exact'
   else:
    kind='same_tool_wrong_arguments'
    for k in set(resolved['arguments'])|set(actual[j]['arguments']):
     if resolved['arguments'].get(k)!=actual[j]['arguments'].get(k):args[k]+=1
    try:
     if arithmetic(resolved)==arithmetic(actual[j]):equivalent.append(detail)
    except (ValueError,KeyError,ZeroDivisionError,TypeError):pass
   detail['classification']=kind;slot_details.append(detail);calls[kind]+=1;names[want['name']][kind]+=1
  calls['extra_proposals']+=max(0,len(actual)-len(expected['calls']))
  if score['expected_readback']:
   if not score['observation_present']:readbacks['no_observation']+=1
   elif score['faithful_to_actual_observation'] is True:readbacks['faithful_raw']+=1
   elif score['faithful_to_actual_observation'] is None:readbacks['manual_pending']+=1
   else:
    answer=expected['answer'];unit_bad=False
    if answer['mode']=='observed_status':
     try:answer=answer['success' if resolve(answer['observation'],observations,proposals) else 'error']
     except (ValueError,KeyError,IndexError):pass
    if 'unit' in answer:
     try:resolve(answer['unit'],observations,proposals)
     except (ValueError,KeyError,IndexError):unit_bad=True
    if unit_bad:readbacks['unresolvable_unit_binding']+=1
    elif response['answer'] is None:readbacks['no_complete_answer']+=1
    elif answer['mode']=='number':
     try:
      value=resolve(answer['value'],observations,proposals)
      if number_answer(response['answer'],value,display=answer.get('display')):readbacks['numeric_matches_but_unit_or_format_fails']+=1
      else:readbacks['wrong_or_absent_numeric_readback']+=1
     except (ValueError,KeyError,IndexError):readbacks['unresolvable_numeric_binding']+=1
    else:readbacks['status_or_error_or_other_content_failure']+=1
  outcome=score['passed'] is True
  if score['manual_pending']:
   pending_families[family]+=1
   if family=='special/missing_divisor':
    assert response['answer']=='What is the second operand?';decision=True;reason='In the stated division, the missing second operand is the divisor/recipient count. The rubric permits equivalent requests and does not require a particular noun.'
   elif expected['answer']['mode']=='observed_status':
    assert response['answer']=='1.' and observations[0][0]['ok'] is True and observations[0][0]['data']['result']==1;decision=True;reason='Faithful bare numeric return implicitly confirms a numeric result; applies prior root adjudication precedent. Actual wrong operation 11/11 returned1.0; this does not credit the requested calculation or session.'
   else:decision=False;reason='Asks for a second operand instead of the missing starting quantity/destination unit, or fails to identify addition; frozen rubric not satisfied.'
   decisions.append(dict(id=session['id'],turn=i,user=expected['user'],rubric=expected['answer'],answer=response['answer'],original_score=score,review_content_pass=decision,reason=reason,reviewer='preflight_activation independent review'))
   outcome=decision and score['protocol_pass'] and score['call_sequence_pass'] and score['bindings_valid']
  passed.append(outcome);overlay_turns+=outcome
  if outcome:success_turns.append(dict(id=session['id'],turn=i,user=expected['user'],answer=response['answer'],original_score=score))
  if len(examples)<40 and (len(examples)<8 or actual):examples.append(dict(id=session['id'],turn=i,family=family,user=expected['user'],answer=response['answer'],frames=response['frames'],expected_calls=expected['calls'],actual_calls=actual,observations=response['trace'],failure=response['failure'],score=score))
 overlay_sessions+=all(passed)
manual=dict(source_pins=pins,scope='Separate exposed-development overlay; raw scores and frozen rubric unchanged; no training/private inputs.',raw=r['summary'],decisions=decisions,manual_pass=sum(d['review_content_pass'] for d in decisions),manual_fail=sum(not d['review_content_pass'] for d in decisions),pending=0,overlay=dict(sessions_passed=overlay_sessions,sessions_total=422,turns_passed=overlay_turns,turns_total=583))
analysis=dict(source_pins=pins,raw_summary=r['summary'],overlay=manual['overlay'],manual_families=dict(pending_families),exclusive_turn_partition=dict(partition),call_diagnosis=dict(calls),argument_mismatch_fields=dict(args),readback_diagnosis=dict(readbacks),failure_kinds=dict(failures),top_answers=answers.most_common(20),required_no_call_answers=required_no_call_answers.most_common(15),by_family=dict(families),by_construction_family=dict(full_families),by_mode=dict(modes),by_expected_tool=dict(names),arithmetic_equivalent_exact_call_mismatches=equivalent,all_expected_slots=slot_details,reviewed_success_turns=success_turns,examples=examples,prior_comparison=dict(manual_sessions_passed=92,manual_turns_passed=203,sessions_total=422,turns_total=583,raw_sessions_passed=78,raw_turns_passed=182,requested_call_passed=151,requested_call_total=453,protocol_failures=33,faithful_given_observation=338,observations=475))
write('primary-tools-manual-review.json',manual);write('primary-tools-analysis.json',analysis)
assert all(sha(ROOT/n)==h for n,h in pins.items())
print(json.dumps({k:v for k,v in analysis.items() if k not in ['all_expected_slots','examples','reviewed_success_turns','source_pins','by_family','by_mode']},indent=2))
