"""Evidence-bound stage screens; a passing screen is not production acceptance."""
from slm.data.schema import digest
from slm.eval.conversation import score


def assess(suite,result,policy,*,suite_review=None,output_review=None,baseline=None,baseline_review=None):
    required={'version','policy_id','status','min_cases','min_scenarios','min_template_families','min_cases_per_slice',
        'min_human_per_style','required_slices','required_styles','exact_min_rate','human_min_rate',
        'max_rate_regression','max_relative_nll_increase','requires_baseline'}
    if (set(policy)!=required or type(policy['version']) is not int or policy['version']!=1
        or policy['status'] not in ('proposed','accepted') or type(policy['requires_baseline']) is not bool):raise ValueError('Explicit stage policy required')
    for k in ('min_cases','min_scenarios','min_template_families','min_cases_per_slice','min_human_per_style'):
        if type(policy[k]) is not int or policy[k]<1:raise ValueError('Positive sample minimum required')
    for k in ('exact_min_rate','human_min_rate','max_rate_regression','max_relative_nll_increase'):
        if type(policy[k]) not in (int,float) or not 0<=policy[k]<=1:raise ValueError('Invalid stage threshold')
    for k in ('required_slices','required_styles'):
        if not policy[k] or len(set(policy[k]))!=len(policy[k]) or any(not isinstance(v,str) or not v for v in policy[k]):raise ValueError('Explicit required coverage needed')
    report=score(suite,result,suite_review=suite_review,output_review=output_review)
    overall=report['overall'];missing=[];failed=[]
    if policy['status']!='accepted':missing.append('stage_policy_not_accepted')
    for k,p in [('cases','min_cases'),('scenarios','min_scenarios'),('template_families','min_template_families')]:
        if overall[k]<policy[p]:missing.append('insufficient_'+k)
    if overall['approved_cases']!=overall['cases']:missing.append('suite_cases_not_all_human_approved')
    if overall['human_pending']:missing.append('human_output_grades_pending')
    if report['reference_loss']['failed_cases']:missing.append('reference_loss_incomplete')
    if overall['generation_errors']:failed.append('generation_errors')
    for kind,keys in [('slices',policy['required_slices']),('styles',policy['required_styles'])]:
        for key in keys:
            row=report[kind].get(key)
            if row is None:missing.append(f'missing_{kind}:{key}');continue
            minimum=policy['min_cases_per_slice'] if kind=='slices' else policy['min_human_per_style']
            if row['cases' if kind=='slices' else 'human_cases']<minimum:missing.append(f'insufficient_{kind}:{key}')
            if row['exact_cases'] and row['exact_rate']<policy['exact_min_rate']:failed.append(f'exact_below_target:{kind}:{key}')
            if row['human_cases'] and row['human_graded']==row['human_cases']:
                if row['human_all_rubrics_passes']/row['human_cases']<policy['human_min_rate']:failed.append(f'human_below_target:{kind}:{key}')
    baseline_report=None
    if baseline is None:
        if policy['requires_baseline']:missing.append('pre_stage_baseline_required')
    else:
        for k in ('architecture','tokenizer_manifest_sha256','decoding','embedding_implementation','inference_sha256'):
            if result['identity'].get(k) is None or result['identity'].get(k)!=baseline['identity'].get(k):raise ValueError('Baseline evaluation conventions differ')
        if baseline.get('max_new_tokens')!=result['max_new_tokens']:raise ValueError('Baseline decoding budget differs')
        baseline_report=score(suite,baseline,suite_review=suite_review,output_review=baseline_review)
        if baseline_report['overall']['human_pending']:missing.append('baseline_human_grades_pending')
        if baseline_report['reference_loss']['failed_cases']:missing.append('baseline_reference_loss_incomplete')
        for kind in ('slices','styles'):
            for key,row in report[kind].items():
                old=baseline_report[kind][key]
                if row['exact_rate'] is not None and old['exact_rate']-row['exact_rate']>policy['max_rate_regression']+1e-12:
                    failed.append(f'exact_regression:{kind}:{key}')
                if row['human_cases'] and row['human_graded']==row['human_cases'] and old['human_graded']==old['human_cases']:
                    before=old['human_all_rubrics_passes']/old['human_cases'];after=row['human_all_rubrics_passes']/row['human_cases']
                    if before-after>policy['max_rate_regression']+1e-12:failed.append(f'human_regression:{kind}:{key}')
        old=baseline_report['reference_loss']['mean_content_nll'];new=report['reference_loss']['mean_content_nll']
        if old is not None and new is not None and new>old*(1+policy['max_relative_nll_increase'])+1e-12:failed.append('reference_nll_regression')
    return {'version':1,'policy_hash':digest(policy),'suite_hash':report['suite_hash'],'result_hash':report['result_hash'],
        'baseline_hash':digest(baseline) if baseline else None,'score_hash':digest(report),
        'decision':'reject' if failed else 'insufficient_evidence' if missing else 'screen_passed',
        'missing_evidence':missing,'failed_checks':failed,'score':report,
        'production_accepted':False,'scope':'Stage screen only. Does not establish source rights, broad fluency, mature-content/tool/MCP quality, performance acceptance or full-size portability. Caller owns curriculum continuation.'}
