#!/usr/bin/env python3
"""One finite paired system-message removal diagnostic, separate from prior cap."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import json
import os
from pathlib import Path
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.eval.fresh_session import ROOT as BASE, checked, validate_response
from slm.eval.research_sft import publish
from slm.eval.research_sft_interview import terminal_binding
from slm.inference.greedy import GreedyModel


def main():
    root=Path('data/iteration-four-system-role-ablation-v1')
    if root.exists(): raise FileExistsError(root)
    prior=checked();binding=terminal_binding()
    if binding != prior['terminal']: raise ValueError('Endpoint changed')
    config=json.loads(Path(prior['config_file']).read_text());cases=[]
    for old in config['cases']:
        if old['messages'][0]['role']!='system': raise ValueError('Exactly one initial system message required')
        case=deepcopy(old);case['messages']=case['messages'][1:];cases.append(case)
    protocol=dict(creator='Navneet Prabhakar',kind='finite-system-role-removal-diagnostic-v1',
        terminal=binding,source_protocol_sha256=sha(BASE/'protocol.json'),
        source_summary_sha256=sha(BASE/'execution/summary.json'),source_config_sha256=sha(prior['config_file']),
        source_response_sha256=sha(BASE/'execution/responses.jsonl'),script_sha256=sha(__file__),
        helper_sha256=sha('src/slm/eval/fresh_session.py'),cases=cases,budget=64,max_generations=16,max_generated_tokens=1024,
        scope='New separately frozen post-hoc diagnostic. Remove only the initial system message, retaining all other fixture context. Semantic/exact task comparisons only; style instructions can change when removed. Original32-generationcap/results/5-score are unchanged; no gradients or training admission.')
    root.mkdir();publish(root/'protocol.json',protocol)
    protocol_sha=sha(root/'protocol.json')
    model=GreedyModel(binding['model_path'],binding['tokenizer_path'],'mlx','default',
        expected_tokenizer_hash=binding['tokenizer_manifest_sha256'],embedding_implementation=binding['embedding_implementation'])
    if model.identity['model_manifest_sha256']!=binding['model_manifest_sha256']: raise ValueError('Loaded model changed')
    rows=[]
    with (root/'reservations.jsonl').open('x') as journal,(root/'responses.jsonl').open('x') as out:
        for case in cases:
            if sha(root/'protocol.json')!=protocol_sha or sha(__file__)!=protocol['script_sha256']:
                raise ValueError('Frozen ablation changed')
            reserve=dict(sequence=len(rows)+1,case_id=case['id'],budget=64,protocol_sha256=protocol_sha)
            journal.write(json.dumps(reserve,sort_keys=True)+'\n');journal.flush();os.fsync(journal.fileno())
            response=model.generate(deepcopy(case['messages']),64)
            row=dict(case_id=case['id'],budget=64,context_sha256=digest(case['messages']),response=response)
            out.write(json.dumps(row,sort_keys=True,ensure_ascii=False)+'\n');out.flush();os.fsync(out.fileno());rows.append(row)
            validate_response(case,response,model.tokenizer,64)
            print(json.dumps(dict(case_id=case['id'],text=response['text'],stop_reason=response['stop_reason']),ensure_ascii=False),flush=True)
    checked()
    assert len(rows)==16 and sum(r['response']['generated_tokens'] for r in rows)<=1024
    exact=sum(r['response']['text'].strip() in c['oracle'].get('accepted',[])
        for c,r in zip(cases,rows) if c['oracle']['kind']=='exact')
    publish(root/'summary.json',dict(creator='Navneet Prabhakar',status='complete',protocol_sha256=protocol_sha,
        responses_sha256=sha(root/'responses.jsonl'),reservations_sha256=sha(root/'reservations.jsonl'),student=model.identity,
        generations=len(rows),actual_generated_tokens=sum(r['response']['generated_tokens'] for r in rows),
        exact_successes=exact,exact_cases=12,human_semantic_assessment_pending=True,prior_score_changed=False,
        scope=protocol['scope']))
    print(json.dumps(dict(status='complete',exact_successes=exact,exact_cases=12)),flush=True)


if __name__=='__main__':main()
