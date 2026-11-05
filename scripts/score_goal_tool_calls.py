"""Score exact annotated calls separately from semantic answer correctness."""
import argparse, hashlib, json
from pathlib import Path

def score(cases, rows):
    by_id={r['id']:r for r in rows}
    if len(by_id)!=len(rows) or set(by_id)!={r['id'] for r in cases}:
        raise ValueError('Raw output case coverage mismatch')
    results=[]
    for case in cases:
        row=by_id[case['id']]
        if len(row['turns'])!=len(case['turns']): raise ValueError('Turn count mismatch')
        for index,(target,actual) in enumerate(zip(case['turns'],row['turns']),1):
            if actual['user']!=target['user']:raise ValueError('Prompt mismatch')
            if 'expected_calls' not in target:continue
            events=actual.get('tool_events',[])
            accepted=[e['call'] for e in events if e.get('accepted_fixture') and 'call' in e]
            failed=any(not e.get('accepted_fixture') for e in events)
            attempted='<|tool_call|>' in actual['student_reply']['output']
            expected=target['expected_calls']
            ok=(accepted==expected and not failed and (bool(expected) or not attempted))
            results.append({'id':case['id'],'turn':index,'expected_calls':expected,'accepted_calls':accepted,'invalid_attempt':failed or (attempted and not accepted),'exact_match':ok,'kind':'required_call' if expected else 'required_abstention'})
    groups={}
    for kind in ['required_call','required_abstention']:
        r=[v for v in results if v['kind']==kind];groups[kind]={'correct':sum(v['exact_match'] for v in r),'total':len(r)}
    return {'kind':'exact_annotated_call_accuracy_not_end_to_end_success','groups':groups,'cases':results,'limitation':'Does not score final-answer grounding, conversation correctness, or unannotated follow-up turns.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cases',type=Path,required=True);p.add_argument('--raw',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=score([json.loads(x) for x in a.cases.read_text().splitlines() if x],json.loads(a.raw.read_text()))
    result['raw_sha256']=hashlib.sha256(a.raw.read_bytes()).hexdigest();result['evaluation_sha256']=hashlib.sha256(a.cases.read_bytes()).hexdigest()
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['groups']))
