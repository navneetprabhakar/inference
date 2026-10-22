"""Recompute complete development diagnostic metrics for the quality barrier.

Caller supplies pinned input stores/items/tokenizer and bound checkpoint context.
Raw metrics do not independently prove model provenance.
"""
import json
from . import development_loss,choice_execution,generation_verification
from .numerical_monitor_comparison import exact


def verifier(*,train_store,dev_store,grammar_items,grounded_items,narrative_items,smoke_ids,tokenizer):
    def verify(raw,context):
        p=json.loads(raw)
        expected={'context','training_loss','development_loss','grammar','grounded','empty_grounded','shuffled_grounded','narratives'}
        if set(p)!=expected or not exact(p['context'],context) or context['event']!='full_development_diagnostics':
            raise ValueError('Invalid full-diagnostic envelope')
        # All nested output bundles must originate at this exact checkpoint/event.
        for key in expected-{'context'}:
            if not exact(p[key].get('context'),context):raise ValueError('Mixed diagnostic checkpoint context')
        losses={}
        for name,store in (('training_loss',train_store),('development_loss',dev_store)):
            metrics=development_loss.summarize(store,p[name])
            if not exact(metrics,p[name].get('metrics')):raise ValueError('Altered loss metrics')
            losses[name]=metrics['nll']
        grammar=choice_execution.verify(grammar_items,p['grammar'],variant='original')
        grounded=choice_execution.verify(grounded_items,p['grounded'],variant='original')
        choice_execution.verify(grounded_items,p['empty_grounded'],variant='empty')
        choice_execution.verify(grounded_items,p['shuffled_grounded'],variant='shuffled')
        narrative=generation_verification.narrative(narrative_items,p['narratives']['outputs'],tokenizer,smoke_ids=smoke_ids)
        return {'train_nll':losses['training_loss'],'dev_nll':losses['development_loss'],
                'grammar':grammar['accuracy'],'grounded':grounded['accuracy'],
                'degenerate_outputs':narrative['smoke_degenerate_outputs']}
    return verify


def copying_verifier(*,pairs,tokenizer):
    def verify(raw,context):
        p=json.loads(raw)
        if not exact(p.get('context'),context) or context['event']!='copying_probes':
            raise ValueError('Wrong copying context')
        metrics=generation_verification.copying(pairs,p,tokenizer)
        return {'train_copies':metrics['training_copies'],'heldout_copies':metrics['heldout_copies']}
    return verify


def execute(*,context,train_store,dev_store,grammar_items,grounded_items,narrative_items,tokenizer,logits,heartbeat):
    """Evaluate one already-bound checkpoint; no optimizer or model construction."""
    from . import generation_execution
    if context.get('event')!='full_development_diagnostics':raise ValueError('Full-diagnostic context required')
    result={'context':dict(context)}
    for key,store in (('training_loss',train_store),('development_loss',dev_store)):
        result[key]=development_loss.score(store,context=dict(context),logits=logits,heartbeat=heartbeat)
    for key,items,variant in (('grammar',grammar_items,'original'),('grounded',grounded_items,'original'),
                             ('empty_grounded',grounded_items,'empty'),('shuffled_grounded',grounded_items,'shuffled')):
        result[key]=choice_execution.execute(items,tokenizer,logits=logits,heartbeat=heartbeat,variant=variant)
        result[key]['context']=dict(context)
    result['narratives']={'context':dict(context),'outputs':generation_execution.narrative(
        narrative_items,tokenizer,logits=logits,heartbeat=heartbeat)}
    return result
