"""Exact-denominator numerical-suite aggregation, never a training permit."""
import math


def aggregate(expected_ids,groups):
    expected=tuple(expected_ids)
    if len(expected)!=40 or len(set(expected))!=40:raise ValueError('Exactly 40 distinct bound cases required')
    found={}
    for group in groups:
        if not isinstance(group,dict) or not isinstance(group.get('cases'),dict):raise ValueError('Missing case results')
        for key,value in group['cases'].items():
            if key not in expected or key in found:raise ValueError('Unknown or duplicate case ID')
            if not isinstance(value,dict) or type(value.get('passed')) is not bool:raise ValueError('Missing explicit case result')
            if 'maximum_absolute_error' in value:
                error=value['maximum_absolute_error']
                if type(error) not in (int,float) or not math.isfinite(error) or error<0:raise ValueError('Invalid numeric case error')
                if value.get('absolute_tolerance')!=1e-5 or value.get('relative_tolerance')!=0:raise ValueError('Changed numerical tolerance')
                if error>1e-5 and value['passed']:raise ValueError('Contradictory numerical pass')
            found[key]=value
    missing=sorted(set(expected)-set(found));failed=sorted(k for k,v in found.items() if not v['passed'])
    return {'status':'NUMERICAL_CASE_RESULTS_PASS' if not missing and not failed else 'NUMERICAL_CASE_RESULTS_FAIL',
            'required_cases':40,'reported_cases':len(found),'passed_cases':sum(v['passed'] for v in found.values()),
            'missing':missing,'failed':failed,'cases':found,'training_authorized_by_this_check':False}
