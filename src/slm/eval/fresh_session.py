"""Finite, frozen fresh-session and conditional-stop diagnostics after SFT."""
# Creator: Navneet Prabhakar
import argparse
from copy import deepcopy
import fcntl
import json
import math
import os
from pathlib import Path
import numpy as np
from slm.common.tokenizer import BPE, STRUCTURAL, OFFSET
from slm.data.holdout import check_training_context
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.eval.cases import candidate_suite, heldout_prompts
from slm.eval.research_sft import ROOT as SFT_ROOT, publish
from slm.eval.research_sft_interview import terminal_binding
from slm.inference.greedy import GreedyModel, prompt_ids

ROOT=Path('data/iteration-four-fresh-session-v1').resolve()
CONFIG=Path('configs/iteration-four-fresh-scenarios-v1.json')


def read(path): return json.loads(Path(path).read_text())


def validate_cases(config, bpe):
    if (config['version'] != 1 or config['creator'] != 'Navneet Prabhakar'
        or config['kind'] != 'iteration-four-fresh-session-candidates-v1'
        or config['review_status'] != 'direct_references_reviewed_for_diagnostic_only'
        or config['budgets'] != [64,256] or config['max_generations'] != 32
        or config['max_generated_tokens'] != 5120 or len(config['cases']) != 16):
        raise ValueError('Reviewed finite16-case diagnostic configuration required')
    review=config['review']
    if (review['creator'] != 'Navneet Prabhakar' or review['human_attestation'] is not False
        or review['review_mode'] != 'delegated_expert' or review['full_contexts_and_references_read'] is not True):
        raise ValueError('Direct delegated reference review required')
    source={c['id']:c for c in candidate_suite()['cases']}
    seen=set();scenarios=set()
    for case in config['cases']:
        old=source.get(case['id'])
        if (old is None or digest(old) != case['source_case_sha256'] or case['messages'] != old['messages']
            or case['oracle'] != old['oracle'] or case['family_id'] != old['family_id']
            or case['scenario_id'] != old['scenario_id'] or case['style'] != old['style']
            or case['content_category'] != 'sfw' or case['id'] in seen or case['scenario_id'] in scenarios
            or digest(case['messages']) not in heldout_prompts()
            or not isinstance(case['reference'],str) or not 1 <= len(bpe.encode(case['reference'])) <= 64):
            raise ValueError('Distinct protected source contexts and short references required')
        if case['oracle']['kind']=='exact' and case['reference'] not in case['oracle']['accepted']:
            raise ValueError('Exact oracle/reference differs')
        if len(prompt_ids(bpe,case['messages']))+256 > 2048: raise ValueError('Whole prompt plus budget must fit')
        for context in (case['messages'],case['messages'][1:]):
            try: check_training_context(context)
            except ValueError: pass
            else: raise ValueError('Existing training guard must reject protected context')
        seen.add(case['id']);scenarios.add(case['scenario_id'])


def token_stats(row, target):
    row=np.asarray(row,dtype=np.float64)
    if row.ndim != 1 or not np.isfinite(row).all() or type(target) is not int or not 0<=target<len(row):
        raise ValueError('Finite logits and valid target required')
    nll=float(np.logaddexp.reduce(row-row[target]))
    return dict(token_id=target,nll=nll,probability=float(np.exp(-nll)),
                rank=1+int((row>row[target]).sum()),greedy_token_id=int(np.argmax(row)),
                greedy_target=bool(int(np.argmax(row))==target))


def suffix_metrics(logits, x, y, prompt_length, reference_ids):
    logits=np.asarray(logits);x=np.asarray(x);y=np.asarray(y)
    start=prompt_length-1;content=list(reference_ids);stop=start+len(content)
    if (logits.ndim != 2 or logits.shape[0] != len(x) or x.shape != y.shape or not content
        or start<0 or stop+1 != len(x)-1 or y[start:stop].tolist() != content
        or int(y[stop]) != STRUCTURAL['message_end'] or int(y[stop+1]) != STRUCTURAL['eos']
        or int(x[start]) != STRUCTURAL['assistant']):
        raise ValueError('Exact final-assistant shifted content/message-end/EOS alignment required')
    rows=[token_stats(logits[i],int(y[i])) for i in range(start,stop)]
    end=token_stats(logits[stop],STRUCTURAL['message_end'])
    alternative=token_stats(logits[stop],STRUCTURAL['eos'])
    eos=token_stats(logits[stop+1],STRUCTURAL['eos'])
    return dict(content_targets=len(rows),content_nll_sum=sum(r['nll'] for r in rows),
        content_nll_mean=float(np.mean([r['nll'] for r in rows])),content_token_stats=rows,
        message_end_after_reference=end,eos_after_reference=alternative,
        either_stop_probability_after_reference=end['probability']+alternative['probability'],
        eos_after_message_end=eos,
        scope='Teacher-forced supplied reference; message-end conditional on full reference, EOS conditional on reference plus message-end. Not free-generation success.')


def forced(model, case):
    messages=case['messages'];reference=case['reference'];bpe=model.tokenizer
    x,y,_=bpe.serialize([*messages,dict(role='assistant',content=reference)],max_length=model.config.max_seq_len)
    with model.context():
        logits,_,_=model.impl.forward(model.params,model.config,model.array([x]),
            embedding_implementation=model.embedding_implementation)
        logits=model.impl.export({'logits':logits})['logits'][0]
    return suffix_metrics(logits,x,y,len(prompt_ids(bpe,messages)),bpe.encode(reference))


def validate_response(case, response, bpe, budget):
    raw=response['token_ids'];content=[t for t in raw if type(t) is int and t>=OFFSET]
    if (not raw or len(raw)>budget or any(type(t) is not int or not 0<=t<bpe.vocab_size for t in raw)
        or any(t<OFFSET for t in raw[:-1]) or response['max_new_tokens'] != budget
        or response['prompt_tokens'] != len(prompt_ids(bpe,case['messages']))
        or response['generated_tokens'] != len(raw) or response['content_tokens'] != len(content)
        or response['text'] != bpe.decode(content)):
        raise ValueError('Raw response/token/count/context binding differs')
    last=raw[-1]
    expected='eos' if last==STRUCTURAL['eos'] else 'message_end' if last==STRUCTURAL['message_end'] else 'invalid_structural' if last<OFFSET else 'length'
    if response['stop_reason'] != expected or (expected=='length' and len(raw)!=budget):
        raise ValueError('Raw stop reason/budget differs')
    if any(not math.isfinite(response[k]) or response[k]<0 for k in ('ttft_seconds','seconds')) or response['ttft_seconds']>response['seconds']:
        raise ValueError('Finite observed generation timing required')


def freeze():
    if ROOT.exists(): raise FileExistsError(ROOT)
    config=read(CONFIG);binding=terminal_binding()
    validate_cases(config,BPE.load(binding['tokenizer_path']))
    sources={str(p):sha(p) for p in map(Path,[__file__,'src/slm/inference/greedy.py',
        'src/slm/backends/mlx_backend.py','src/slm/eval/cases.py','src/slm/data/holdout.py'])}
    protocol=dict(version=1,creator='Navneet Prabhakar',kind='finite-fresh-session-diagnostic-v1',
        config_file=str(CONFIG.resolve()),config_sha256=sha(CONFIG),terminal=binding,
        source_sha256=sources,budgets=[64,256],max_generations=32,max_generated_tokens=5120,
        assessment_sha256=sha(SFT_ROOT/'conversation-assessment.json'),
        comparison='Fresh independent sessions, identical context across budgets; no reuse of generated answers between cases/budgets. Synthetic supplied fixture history is explicitly not generated student history.',
        interpretation='Diagnostic only. Exact oracle uses strip-only matching; human-oracle cases require direct judgment. Prior5/100 unchanged. No gradients, teacher, cloud or test-to-train admission.')
    ROOT.mkdir();publish(ROOT/'protocol.json',protocol)
    publish(ROOT/'freeze.json',dict(creator='Navneet Prabhakar',protocol_sha256=sha(ROOT/'protocol.json')))
    print(json.dumps(dict(status='frozen',cases=16,max_generations=32,max_generated_tokens=5120)),flush=True)


def checked():
    p=read(ROOT/'protocol.json');f=read(ROOT/'freeze.json')
    if sha(ROOT/'protocol.json') != f['protocol_sha256'] or sha(p['config_file']) != p['config_sha256']:
        raise ValueError('Frozen diagnostic/config changed')
    for name,want in p['source_sha256'].items():
        if sha(name) != want: raise ValueError('Frozen diagnostic implementation changed')
    if sha(SFT_ROOT/'conversation-assessment.json') != p['assessment_sha256']:
        raise ValueError('Prior assessment changed')
    return p


def append(stream,value):
    stream.write(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')
    stream.flush();os.fsync(stream.fileno())


def run():
    p=checked();binding=terminal_binding()
    if binding != p['terminal']: raise ValueError('Frozen terminal endpoint changed')
    config=read(p['config_file']);bpe=BPE.load(binding['tokenizer_path']);validate_cases(config,bpe)
    target=ROOT/'execution';target.mkdir() # Refuse restarts of partial or completed generation work.
    model=GreedyModel(binding['model_path'],binding['tokenizer_path'],'mlx','default',
        expected_tokenizer_hash=binding['tokenizer_manifest_sha256'],embedding_implementation=binding['embedding_implementation'])
    if model.identity['model_manifest_sha256'] != binding['model_manifest_sha256']: raise ValueError('Loaded endpoint differs')
    publish(target/'session.json',dict(creator='Navneet Prabhakar',student=model.identity,protocol_sha256=sha(ROOT/'protocol.json')))
    rows=[];references=[];reserved=0
    try:
        with (target/'reservations.jsonl').open('x') as journal,(target/'responses.jsonl').open('x') as output,(target/'references.jsonl').open('x') as refs:
            for case in config['cases']:
                reference=dict(case_id=case['id'],context_sha256=digest(case['messages']),metrics=forced(model,case))
                append(refs,reference);references.append(reference)
                pair=[]
                for budget in config['budgets']:
                    checked();reserved+=budget
                    if len(rows)>=32 or reserved>5120: raise ValueError('Generation ceiling exceeded')
                    append(journal,dict(sequence=len(rows)+1,case_id=case['id'],budget=budget,protocol_sha256=sha(ROOT/'protocol.json')))
                    response=model.generate(deepcopy(case['messages']),budget)
                    value=dict(case_id=case['id'],budget=budget,context_sha256=digest(case['messages']),response=response)
                    append(output,value);rows.append(value);pair.append(response)
                    validate_response(case,response,bpe,budget)
                    exact=response['text'].strip() in case['oracle'].get('accepted',[]) if case['oracle']['kind']=='exact' else None
                    print(json.dumps(dict(case_id=case['id'],budget=budget,text=response['text'],stop_reason=response['stop_reason'],exact_success=exact),ensure_ascii=False),flush=True)
                if pair[0]['token_ids'] != pair[1]['token_ids'][:len(pair[0]['token_ids'])]:
                    raise ValueError('Identical greedy budget-prefix diagnostic differs')
        checked()
        success={str(b):sum(row['response']['text'].strip() in c['oracle'].get('accepted',[])
            for c in config['cases'] if c['oracle']['kind']=='exact' for row in rows if row['case_id']==c['id'] and row['budget']==b) for b in config['budgets']}
        summary=dict(creator='Navneet Prabhakar',status='complete',protocol_sha256=sha(ROOT/'protocol.json'),
            student=model.identity,cases=len(references),generations=len(rows),reserved_max_tokens=reserved,
            actual_generated_tokens=sum(r['response']['generated_tokens'] for r in rows),
            exact_oracle_cases=sum(c['oracle']['kind']=='exact' for c in config['cases']),exact_success_by_budget=success,
            human_oracle_assessment_pending=True,prior_conversation_score=5,prior_score_changed=False,
            files_sha256={name:sha(target/name) for name in ('session.json','reservations.jsonl','responses.jsonl','references.jsonl')},
            scope='Fresh-session diagnostics only. Protected16scenarios/eightparameterizedfamilies, not population accuracy or evidence that training caused differences. Forced reference likelihood is separate from generation success.')
        publish(target/'summary.json',summary);print(json.dumps(dict(status='complete',exact_success_by_budget=success)),flush=True)
    except BaseException as error:
        publish(target/'failure.json',dict(creator='Navneet Prabhakar',complete=False,error_type=type(error).__name__,
            completed_generations=len(rows),reserved_max_tokens=reserved))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['freeze','run'])
    args=parser.parse_args()
    if args.action=='freeze':freeze()
    else:
        with (ROOT/'diagnostic.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);run()


if __name__=='__main__':main()
