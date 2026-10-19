#!/usr/bin/env python3
"""Reopen frozen diagnostics, raw replies and direct judgments without replay."""
# Creator: Navneet Prabhakar
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil
import numpy as np
from slm.common.tokenizer import BPE
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.eval.fresh_session import ROOT,checked,validate_cases,validate_response
from slm.eval.iteration_two_selection import checked_checkpoint
from slm.eval.research_sft import publish


def read(p):return json.loads(Path(p).read_text())
def lines(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]


def main():
    p=checked();config=read(p['config_file']);execution=ROOT/'execution';summary=read(execution/'summary.json')
    bpe=BPE.load(p['terminal']['tokenizer_path']);validate_cases(config,bpe)
    checked_checkpoint(Path(p['terminal']['model_path']).parent.parent,p['terminal']['checkpoint_manifest_sha256'])
    assert summary['status']=='complete' and summary['protocol_sha256']==sha(ROOT/'protocol.json')
    for name,want in summary['files_sha256'].items():assert sha(execution/name)==want
    rows=lines(execution/'responses.jsonl');refs=lines(execution/'references.jsonl');reservations=lines(execution/'reservations.jsonl')
    expected=[(c,b) for c in config['cases'] for b in (64,256)]
    assert len(rows)==len(reservations)==32 and len(refs)==16
    for seq,((case,budget),row,reserve) in enumerate(zip(expected,rows,reservations),1):
        assert (row['case_id'],row['budget'])==(case['id'],budget) and row['context_sha256']==digest(case['messages'])
        assert reserve==dict(sequence=seq,case_id=case['id'],budget=budget,protocol_sha256=sha(ROOT/'protocol.json'))
        validate_response(case,row['response'],bpe,budget)
    assert sum(r['budget'] for r in reservations)==5120
    assert sum(r['response']['generated_tokens'] for r in rows)==summary['actual_generated_tokens']<=5120
    for i,case in enumerate(config['cases']):
        short,long=rows[i*2]['response'],rows[i*2+1]['response']
        assert short['token_ids']==long['token_ids'][:len(short['token_ids'])]
        ref=refs[i];m=ref['metrics'];content=m['content_token_stats']
        assert ref['case_id']==case['id'] and ref['context_sha256']==digest(case['messages'])
        assert m['content_targets']==len(content)==len(bpe.encode(case['reference']))
        assert [r['token_id'] for r in content]==bpe.encode(case['reference'])
        assert np.isclose(sum(r['nll'] for r in content),m['content_nll_sum'],rtol=0,atol=1e-10)
        for stat in [*content,m['message_end_after_reference'],m['eos_after_reference'],m['eos_after_message_end']]:
            assert np.isfinite([stat['nll'],stat['probability']]).all() and 0<=stat['probability']<=1 and 1<=stat['rank']<=bpe.vocab_size
            assert np.isclose(stat['probability'],np.exp(-stat['nll']),rtol=1e-12,atol=1e-15)
    bare_root=Path('data/iteration-four-system-role-ablation-v1');a=read(bare_root/'protocol.json');s=read(bare_root/'summary.json')
    assert s['status']=='complete' and s['protocol_sha256']==sha(bare_root/'protocol.json')
    assert a['terminal']==p['terminal'] and a['source_protocol_sha256']==sha(ROOT/'protocol.json')
    assert a['source_summary_sha256']==sha(execution/'summary.json') and a['source_config_sha256']==sha(p['config_file'])
    assert a['source_response_sha256']==sha(execution/'responses.jsonl') and a['script_sha256']==sha('scripts/diagnose-system-role.py')
    assert a['helper_sha256']==sha('src/slm/eval/fresh_session.py')
    assert s['responses_sha256']==sha(bare_root/'responses.jsonl') and s['reservations_sha256']==sha(bare_root/'reservations.jsonl')
    bare=lines(bare_root/'responses.jsonl');br=lines(bare_root/'reservations.jsonl')
    assert len(bare)==len(br)==a['max_generations']==16 and a['max_generated_tokens']==1024
    for seq,(original,case,row,reserve) in enumerate(zip(config['cases'],a['cases'],bare,br),1):
        expected_case=deepcopy(original);expected_case['messages']=expected_case['messages'][1:]
        assert case==expected_case and row['case_id']==case['id'] and row['budget']==64
        assert row['context_sha256']==digest(case['messages'])
        assert reserve==dict(sequence=seq,case_id=case['id'],budget=64,protocol_sha256=sha(bare_root/'protocol.json'))
        validate_response(case,row['response'],bpe,64)
    assert sum(r['response']['generated_tokens'] for r in bare)==s['actual_generated_tokens']<=1024
    grades=read(ROOT/'direct-judgments.json');judged={(r['condition'],r['case_id'],r['budget']):r for r in grades['judgments']}
    assert grades['creator']=='Navneet Prabhakar' and grades['review_mode']=='delegated_expert'
    assert grades['human_attestation'] is False and grades['all_48_complete_responses_read'] is True
    assert grades['training_approved'] is False and len(judged)==len(grades['judgments'])==12
    conditions={f'with_system_{b}':[r for r in rows if r['budget']==b] for b in (64,256)}
    conditions['without_system_64']=bare;counts={}
    source={c['id']:c for c in config['cases']}
    for condition,outputs in conditions.items():
        successes=0
        for row in outputs:
            case=source[row['case_id']]
            if case['oracle']['kind']=='exact':success=row['response']['text'].strip() in case['oracle']['accepted']
            else:
                key=('without_system' if condition.startswith('without') else 'with_system',case['id'],row['budget'])
                j=judged[key];assert type(j['task_succeeded']) is bool and j['reason'].strip()
                success=j['task_succeeded']
            successes+=int(success)
        counts[condition]=dict(task_successes=successes,cases=len(outputs),stop_reasons=dict(Counter(r['response']['stop_reason'] for r in outputs)))
    report=dict(creator='Navneet Prabhakar',kind='actual-fresh-session-diagnostic-assessment-v1',
        protocol_sha256=sha(ROOT/'protocol.json'),ablation_protocol_sha256=sha(bare_root/'protocol.json'),
        judgment_sha256=sha(ROOT/'direct-judgments.json'),source_summary=summary,ablation_summary=s,
        direct_human_oracle_judgments=grades,conditions=counts,
        conditional_reference_summary=dict(
            first_content_greedy_matches=sum(r['metrics']['content_token_stats'][0]['greedy_target'] for r in refs),
            first_content_rank_median=float(np.median([r['metrics']['content_token_stats'][0]['rank'] for r in refs])),
            message_end_greedy_matches=sum(r['metrics']['message_end_after_reference']['greedy_target'] for r in refs),
            eos_after_end_probability_range=[float(min(r['metrics']['eos_after_message_end']['probability'] for r in refs)),float(max(r['metrics']['eos_after_message_end']['probability'] for r in refs))]),
        actual_generated_tokens=summary['actual_generated_tokens']+s['actual_generated_tokens'],actual_generations=48,
        prior_conversation_score=5,prior_score_changed=False,new_training_updates=0,
        checker_sha256=sha(__file__),
        interpretation='All16tasksfailatbothbudgets;removingsystemmessagealso0of16. Fresh-request failures persist outside the erroneous interview history; longer budget/removing system alone does not recover tasks on these cases. Conditional EOS-after-end is learned strongly, but content choice and message-end probabilities remain weak. No training root cause or population rate established; exact contexts/IDs protected, arbitrary paraphrase contamination not certified.')
    publish(ROOT/'assessment.json',report)
    publish('reports/milestone-sixty-five-fresh-session-assessment.json',report)
    for src,dest in [(execution/'responses.jsonl','iteration-four-fresh-responses.jsonl'),
                     (execution/'references.jsonl','iteration-four-forced-references.jsonl'),
                     (bare_root/'responses.jsonl','iteration-four-no-system-responses.jsonl')]:
        target=Path('reports')/dest
        if target.exists():raise FileExistsError(target)
        shutil.copyfile(src,target);assert sha(src)==sha(target)
    print(json.dumps(dict(conditions=counts,conditional=report['conditional_reference_summary'],actual_generated_tokens=report['actual_generated_tokens']),indent=2))


if __name__=='__main__':main()
