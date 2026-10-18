"""Separate syntax, action semantics, execution and final metadata from text quality."""
from slm.data.schema import digest


def action_semantics(value):
    if value is None:return None
    if value['kind']=='call':return {k:value[k] for k in ('kind','name','arguments')}
    if value['kind']=='clarify':return {k:value[k] for k in ('kind','missing')}
    return {'kind':value['kind']}


def score_task(scenario,report):
    first=report['trace'][0] if report['trace'] else None
    actual=first['decision'] if first else None;expected=scenario['expected_action'];final=report['final_decision']
    is_call=expected['kind']=='call';is_clarify=expected['kind']=='clarify';is_answer=expected['kind']=='answer'
    first_match=digest(action_semantics(actual))==digest(action_semantics(expected))
    final_match=False
    if final is not None:
        target=scenario['expected_final']
        final_match=(final['kind']==target['kind'] and
            digest(final.get('missing') if is_clarify else final.get('facts'))==digest(target.get('missing') if is_clarify else target.get('facts')))
    execution=bool(first and first['result'] is not None and first['result']['ok']) if is_call else report['executed_calls']==0
    expected_data=scenario.get('expected_tool_data')
    execution_value_match=(digest(first['result']['data'])==digest(expected_data) if execution and expected_data is not None else None)
    checks={'protocol_valid_first':bool(first and first['protocol_valid']),'first_kind_correct':actual is not None and actual['kind']==expected['kind'],
        'tool_name_correct':bool(actual and actual['kind']=='call' and actual['name']==expected['name']) if is_call else None,
        'arguments_exact':bool(actual and actual['kind']=='call' and digest(actual['arguments'])==digest(expected['arguments'])) if is_call else None,
        'no_tool_correct':first_match and report['executed_calls']==0 if is_answer else None,
        'clarification_correct':first_match and report['executed_calls']==0 if is_clarify else None,
        'execution_success':execution,'tool_result_data_exact':execution_value_match,'final_metadata_exact':final_match}
    success=all(v for v in checks.values() if v is not None)
    return {'scenario_id':scenario['scenario_id'],'scenario_hash':digest(scenario),'trace_hash':digest(report),
        'checks':checks,'structured_task_passed':success,'free_text_quality_verified':False,'style_verified':False,
        'scope':'First-attempt exact action/argument and final metadata checks; correct metadata does not prove truthful free text, style or student generalization'}
