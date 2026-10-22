"""Recompute generation diagnostics from retained token streams, never summaries.

This verifies internal evidence consistency. Scoped execution must separately
establish checkpoint/model provenance; tokens alone cannot prove sampling.
"""
from slm.common.tokenizer import STRUCTURAL
from .generation_metrics import diagnostics,copy_match,copy_gate
from .numerical_monitor_comparison import exact


def verify_stream(prefix,raw,tokenizer,*,seed=None,copying=False):
    if (not isinstance(prefix,list) or not prefix or len(prefix)>=512
            or any(type(t) is not int or not 10<=t<tokenizer.vocab_size for t in prefix)):
        raise ValueError('Invalid bound prefix')
    tokens=raw.get('generated_token_ids')
    if (not isinstance(tokens,list) or not tokens or len(tokens)>512-len(prefix)
            or any(type(t) is not int or not 0<=t<tokenizer.vocab_size for t in tokens)):
        raise ValueError('Invalid generated token stream')
    text='';reason=None
    for index,token in enumerate(tokens):
        if token==STRUCTURAL['eos']:reason='eos'
        elif token<10:reason='invalid_structural_token'
        else:
            text=tokenizer.decode(tokens[:index+1])
            if copying and index+1==64:reason='copy_64_tokens'
            elif not copying and len(text.split())>=120:reason='word_limit'
            elif index+1==512-len(prefix):reason='context_limit'
        if reason is not None:
            if index!=len(tokens)-1:raise ValueError('Tokens retained after first required stop')
            break
    if reason is None:raise ValueError('Truncated generation without a stop')
    expected={'generated_token_ids':tokens,'text':text,'stop_reason':reason,'ended_with_eos':reason=='eos',
              'decode_policy':'greedy-lowest-id-tie' if copying else 'temperature-.7-top-p-.9-PCG64',
              'seed':None if copying else seed}
    if not exact({k:raw.get(k) for k in expected},expected):raise ValueError('Generation metadata differs from raw tokens')
    return diagnostics(text,ended_with_eos=reason=='eos')


def narrative(items,outputs,tokenizer,*,smoke_ids):
    if (len(items)!=100 or len({i['id'] for i in items})!=100 or len(outputs)!=100
            or len(smoke_ids)!=20 or len(set(smoke_ids))!=20
            or not set(smoke_ids)<=set(i['id'] for i in items)):
        raise ValueError('Frozen narrative and smoke denominators required')
    by_id={}
    for raw in outputs:
        if raw['id'] in by_id:raise ValueError('Duplicate narrative output')
        by_id[raw['id']]=raw
    if set(by_id)!=set(i['id'] for i in items):raise ValueError('Missing/unknown narrative output')
    judged=[]
    for item in items:
        if tokenizer.encode(item['prefix'])!=item['prefix_token_ids']:raise ValueError('Changed narrative prefix')
        raw=by_id[item['id']]
        d=verify_stream(item['prefix_token_ids'],raw,tokenizer,seed=item['generation_seed'])
        failed=raw['stop_reason']=='invalid_structural_token'
        if not exact(raw.get('diagnostics'),d) or not exact(raw.get('execution_failure'),failed):
            raise ValueError('Changed narrative diagnostics')
        if failed:raise ValueError('Invalid structural narrative output')
        judged.append({'id':item['id'],'diagnostics':d})
    count=sum(r['id'] in smoke_ids and (r['diagnostics']['fourgram_failure'] or r['diagnostics']['threefold_sentence_failure']) for r in judged)
    return {'items':judged,'smoke_degenerate_outputs':count,'smoke_denominator':20,'narrative_denominator':100}


def copying(pairs,result,tokenizer):
    outputs=result.get('outputs')
    if (len(pairs)!=100 or len({p['pair_id'] for p in pairs})!=100
            or not isinstance(outputs,list) or len(outputs)!=100):raise ValueError('Fixed copy denominator required')
    by_id={}
    for raw in outputs:
        if raw['pair_id'] in by_id:raise ValueError('Duplicate copy output')
        by_id[raw['pair_id']]=raw
    if set(by_id)!=set(p['pair_id'] for p in pairs):raise ValueError('Unknown/missing copy output')
    matched={'training':[],'heldout':[]}
    for pair in pairs:
        for role in matched:
            item=pair[role];raw=by_id[pair['pair_id']][role]
            if len(item['prefix_token_ids'])!=64 or tokenizer.encode(item['prefix'])!=item['prefix_token_ids']:
                raise ValueError('Changed copy prefix')
            verify_stream(item['prefix_token_ids'],raw,tokenizer,copying=True)
            if raw['stop_reason']=='invalid_structural_token':raise ValueError('Invalid structural copying output')
            value=copy_match(raw['generated_token_ids'],item['expected_next_64_token_ids'])
            if not exact(raw.get('match'),value):raise ValueError('Altered copying match')
            matched[role].append(value)
    metrics=copy_gate(matched['training'],matched['heldout'])
    if not exact(result.get('metrics'),metrics):raise ValueError('Altered aggregate copying metrics')
    return metrics


def apply_copying(monitor,pairs,result,tokenizer):
    try:
        metrics=copying(pairs,result,tokenizer)
        monitor.copying(metrics['training_copies'],metrics['heldout_copies'])
        return metrics
    except Exception as error:
        if monitor.terminal is None:monitor.terminal='copy evaluation failed: '+str(error)
        raise
