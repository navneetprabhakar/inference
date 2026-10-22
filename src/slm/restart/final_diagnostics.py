"""One-checkpoint final metric assembly; no launch or research approval authority.

Execution provenance, clean termination and leakage verification belong to the
scoped final parent. Passing these metrics alone never opens further training.
"""
from . import development_loss,choice_execution,generation_execution,generation_verification
from . import final_loss,research_gates,narrative_review
from .numerical_monitor_comparison import exact


def execute(*,context,store,grammar_items,grounded_items,narrative_items,copy_pairs,tokenizer,baselines,logits,heartbeat):
    if context.get('event')!='final_research_evaluation':raise ValueError('Final context required')
    result={'context':dict(context)}
    result['loss']=development_loss.score(store,context=dict(context),logits=logits,heartbeat=heartbeat)
    result['baselines'],result['baseline_receipt']=baselines.score(store,context=dict(context),heartbeat=heartbeat)
    for key,items,variant in (('grammar',grammar_items,'original'),('grounded',grounded_items,'original'),
                             ('empty_grounded',grounded_items,'empty'),('shuffled_grounded',grounded_items,'shuffled')):
        result[key]=choice_execution.execute(items,tokenizer,logits=logits,heartbeat=heartbeat,variant=variant)
        result[key]['context']=dict(context)
    result['narratives']={'context':dict(context),'outputs':generation_execution.narrative(narrative_items,tokenizer,logits=logits,heartbeat=heartbeat)}
    result['copying']=generation_execution.copying(copy_pairs,tokenizer,logits=logits,heartbeat=heartbeat)
    result['copying']['context']=dict(context)
    return result


def metric_evidence(payload,*,context,store,grammar_items,grounded_items,narrative_items,copy_pairs,tokenizer,baselines):
    keys={'context','loss','baselines','baseline_receipt','grammar','grounded','empty_grounded','shuffled_grounded','narratives','copying'}
    if set(payload)!=keys or not exact(payload['context'],context) or context.get('event')!='final_research_evaluation':
        raise ValueError('Invalid final metric envelope')
    for key in ('loss','grammar','grounded','empty_grounded','shuffled_grounded','narratives','copying'):
        if not exact(payload[key].get('context'),context):raise ValueError('Mixed final checkpoints')
    if set(payload['baselines'])!={'unigram','modified_kneser_ney'}:raise ValueError('Missing final baseline evidence')
    for value in payload['baselines'].values():
        if not exact(value.get('context'),context):raise ValueError('Mixed baseline context')
    baselines.verify()
    receipt=payload['baseline_receipt']
    if (not exact(receipt.get('artifact_sha256'),baselines.pins) or not exact(receipt.get('selection'),baselines.selection)
            or receipt.get('refitted') is not False):raise ValueError('Unbound frozen baseline receipt')
    loss=final_loss.assess(store,payload['loss'],payload['baselines'])
    choice_execution.verify(grammar_items,payload['grammar'],variant='original')
    for key,variant in (('grounded','original'),('empty_grounded','empty'),('shuffled_grounded','shuffled')):
        choice_execution.verify(grounded_items,payload[key],variant=variant)
    grammar=research_gates.grammar(grammar_items,payload['grammar']['outputs'])
    grounded=research_gates.grounded(grounded_items,payload['grounded']['outputs'],payload['empty_grounded']['outputs'],payload['shuffled_grounded']['outputs'])
    copying=generation_verification.copying(copy_pairs,payload['copying'],tokenizer)
    packet=narrative_review.prepare(narrative_items,payload['narratives'],tokenizer)
    return {'loss':loss,'grammar':grammar,'grounded':grounded,'copying':copying,'review_packet':packet}


def assess(payload,*,reviews=None,review_packet=None,**inputs):
    metrics=metric_evidence(payload,**inputs)
    if reviews is None:
        return {'status':'NARRATIVE_REVIEW_REQUIRED','metrics':metrics,'final_research_pass':False}
    narrative=narrative_review.assess(inputs['narrative_items'],payload['narratives'],inputs['tokenizer'],review_packet,reviews)
    passed=all(metrics[name]['passed'] for name in ('loss','grammar','grounded')) and metrics['copying']['final_gate_pass'] and narrative['passed']
    return {'status':'METRIC_GATES_PASS' if passed else 'METRIC_GATES_FAIL','metrics':metrics,'narrative':narrative,
            'final_research_pass':False,'remaining_authority_checks':['scoped execution provenance','clean termination','zero known cross-split leakage'],
            'scope':'Final metric assessment only; no approval for chat training or another candidate'}
