#!/usr/bin/env python3
"""Read-only first-canonical-error check; no generation or gradients."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import numpy as np
from slm.common.tokenizer import STRUCTURAL
from slm.data.tokenized import sha
from slm.eval.fitting_control import ROOT,checked,verified_terminal,publish
from slm.eval.fresh_session import forced,token_stats
from slm.inference.greedy import GreedyModel,prompt_ids


def main():
    p=checked();path=verified_terminal();spec=json.loads((ROOT/'spec.json').read_text())
    model=GreedyModel(path/'state/model',spec['tokenizer'],'mlx','default',
        expected_tokenizer_hash=p['plan']['tokenizer_hash'],embedding_implementation=p['plan']['recipe']['embedding_implementation'])
    rows=[json.loads(x) for x in (ROOT/'terminal/responses.jsonl').read_text().splitlines()]
    cases=[];targets=correct=0
    for source,row in zip(p['train'],rows):
        assert source['example_id']==row['example_id']
        history=source['messages'][:-1];reference=source['messages'][-1]['content']
        case=dict(messages=history,reference=reference)
        stats=forced(model,case);content=stats['content_token_stats']
        targets+=len(content);correct+=sum(s['greedy_target'] for s in content)
        ref=model.tokenizer.encode(reference);actual=row['response']['token_ids']
        record=dict(example_id=row['example_id'],exact_reference=row['exact_reference'],
            final_reference_content_targets=len(content),teacher_forced_greedy_content_matches=sum(s['greedy_target'] for s in content))
        if not row['exact_reference']:
            wanted=[*ref,STRUCTURAL['message_end']]
            first=next(i for i,(a,b) in enumerate(zip(actual,wanted)) if a!=b)
            prefix=[*prompt_ids(model.tokenizer,history),*ref[:first]]
            with model.context():
                logits,_,_=model.impl.forward(model.params,model.config,model.array([prefix]),embedding_implementation=model.embedding_implementation)
                last=model.impl.export({'last':logits[0,-1]})['last']
            full=content[first] if first<len(content) else stats['message_end_after_reference']
            record.update(first_canonical_token_divergence=first,expected_token_id=wanted[first],cached_generated_token_id=actual[first],
                uncached_prefix_greedy_token_id=int(np.argmax(last)),full_reference_greedy_token_id=full['greedy_token_id'],
                uncached_prefers_same_error=bool(int(np.argmax(last))==actual[first]),
                expected_token=token_stats(last,int(wanted[first])),generated_token=token_stats(last,int(actual[first])))
        cases.append(record)
    result=dict(creator='Navneet Prabhakar',kind='post-hoc-fitting-first-error-diagnostic-v1',
        protocol_sha256=sha(ROOT/'protocol.json'),terminal_responses_sha256=sha(ROOT/'terminal/responses.jsonl'),
        conversation_assessment_sha256=sha(ROOT/'conversation-assessment.json'),script_sha256=sha(__file__),
        cases=cases,final_reference_content_targets=targets,teacher_forced_greedy_matches=correct,
        nonexact_cases=sum(not r['exact_reference'] for r in cases),
        uncached_agrees_at_first_error=sum(r.get('uncached_prefers_same_error',False) for r in cases),
        new_generation_calls=0,new_optimizer_updates=0,
        scope='Canonical BPE-token divergence, not necessarily the first semantic error. Each nonexact reply is compared at its first divergence where the reference prefix still matches. Uncached prefix/full-reference choices diagnose these particular decisions, not all cache states or universal decoding parity. No rerun of free generation or change to the failed fitting criterion.')
    checked();publish(ROOT/'first-error-diagnostic.json',result)
    publish('reports/milestone-sixty-six-first-error-diagnostic.json',result)
    print(json.dumps({k:result[k] for k in ('final_reference_content_targets','teacher_forced_greedy_matches','nonexact_cases','uncached_agrees_at_first_error')},indent=2))


if __name__=='__main__':main()
