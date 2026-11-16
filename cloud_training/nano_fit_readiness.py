"""Full-denominator scoring of reviewed, exposed training-fit generations.

Does not grant release acceptance, infer semantics from loss, or train weights.
"""
import hashlib,json

def score_fit(suite,report,review):
    if suite.get('purpose')!='training_fit_exposed_never_release':raise ValueError('Explicit fit scope required')
    expected=[(s['id'],i) for s in suite['sessions'] for i,_ in enumerate(s['turns'])]
    if len(expected)!=len(set(expected)):raise ValueError('Duplicate fit keys')
    def keyed(rows):
        result={}
        for r in rows:
            key=(r['session'],r['turn'])
            if key not in expected or key in result:raise ValueError('Duplicate/unexpected fit record')
            result[key]=r
        return result
    actual=keyed(report['records']);graded=keyed(review)
    passed=[];forbidden=False
    for key in expected:
        record=actual.get(key,{});result=record.get('result',{})
        events=result.get('events',[])
        calls=bool(result.get('broker_trace')) or any(e.get('kind')=='broker_decision' or e.get('parsed',{}).get('kind')=='call' for e in events)
        forbidden=forbidden or calls
        judgement=graded.get(key,{})
        ok=result.get('status')=='complete' and not calls and judgement.get('pass') is True and bool(judgement.get('reason'))
        passed.append((key,ok))
    sessions={s['id']:all(ok for (sid,_),ok in passed if sid==s['id']) for s in suite['sessions']}
    completed=report.get('status')=='fit_checks_complete_requires_review'
    full_review=len(graded)==len(expected) and all(type(r.get('pass'))is bool and bool(r.get('reason')) for r in review)
    return {'scope':'Training-fit only; not heldout or release acceptance','expected_turns':len(expected),'observed_turns':len(actual),
            'reviewed_turns':len(graded),'passed_turns':sum(ok for _,ok in passed),'sessions':len(sessions),'passed_sessions':sum(sessions.values()),
            'session_passes':sessions,'unexpected_tool_action':forbidden,'full_review':full_review,
            'fit_go':completed and full_review and len(sessions)==24 and sum(sessions.values())>=23 and not forbidden
              and all(r.get('result',{}).get('status')=='complete' for r in actual.values()) and len(actual)==len(expected),
            'release_eligible':False}
