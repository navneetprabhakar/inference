"""Frozen-checkpoint development-only decode; confirmation is never opened.

Tool turns are model-driven: each emitted turn is parsed as either a final
answer or one exact permitted call.  Expected calls score the trace; they are
not fed back as a prescribed call count.
"""
import hashlib, json, re, time
from collections import Counter
from pathlib import Path
import mlx.core as mx
from tokenizers import Tokenizer
from benchmark_mlx import Model
from sft_common import ROOT, configure_memory, generate, parse_call, execute, memory_stats
from train_local import health as system_health
from inference_guard import violation, stop_requested
from author_eval_scoring import tool_trace, exact_answer

DEV=ROOT/'data/author-review-v3/development-cases.jsonl'
OUT=ROOT/'reports/author-review-v1/development-decoding-v2'
CHECKPOINT=ROOT/'runs/sft-v3/repair-lr3/milestones/2000000'
EXPECTED='93bb235b29c8bdff5efe4e14bac223b92b5bc70fecc3023a22d8ed2d9b6fd781'
CAP=96; MAX_TURNS=6
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def score_prose(text,rubric):
    s=' '.join(text.split()); low=s.casefold(); ok=True
    if 'exact' in rubric: ok &= s==rubric['exact']
    if 'regex' in rubric: ok &= bool(re.fullmatch(rubric['regex'],s))
    ok &= all(x.casefold() in low for x in rubric.get('must_contain_all',[]))
    values=rubric.get('must_contain_any',[]); ok &= not values or any(x.casefold() in low for x in values)
    ok &= not any(x.casefold() in low for x in rubric.get('must_not_contain',[]))
    ok &= len(re.findall(r'\S+',s))<=rubric.get('max_words',10**9)
    return bool(ok)

def legacy_tool_trace(rec, emit):
    """Pure scoring loop; `emit(messages)` returns actual model generation dict."""
    messages=list(rec['messages']); expected=rec['calls']; trace=[]; final=None; reason=None
    for turn in range(min(MAX_TURNS,rec.get('max_turns',MAX_TURNS))):
        generation=emit(messages); text=generation['output']; item={'turn':turn+1,'generation':generation,'raw_output':text}
        if not text.strip().startswith('<|tool_call|>'):
            item['kind']='final_answer'; trace.append(item); final=text; reason='final_answer'; break
        try: call=parse_call(text); item.update(kind='tool_call',call=call)
        except Exception as exc:
            item.update(kind='invalid_tool_call',rejected=True,error=type(exc).__name__); trace.append(item); reason='invalid_tool_call'; break
        index=sum(x.get('kind')=='tool_call' and x.get('executed') for x in trace)
        if index>=len(expected):
            item.update(rejected=True,rejection='extra_call'); trace.append(item); reason='extra_call'; break
        wanted=expected[index]
        if call['name']!=wanted['name'] or call['arguments']!=wanted['arguments']:
            item.update(rejected=True,rejection='wrong_call',expected=wanted); trace.append(item); reason='wrong_call'; break
        try:
            result=execute(call); item.update(executed=True,result=result)
            messages += [{'role':'assistant','content':text},{'role':'tool','content':json.dumps(result,separators=(',',':'))}]
            trace.append(item)
        except Exception as exc:
            item.update(rejected=True,rejection='fixture_execution_error',error=type(exc).__name__); trace.append(item); reason='fixture_execution_error'; break
    else: reason='turn_limit'
    exact_calls=[x for x in trace if x.get('kind')=='tool_call' and x.get('executed')]
    early_final=final is not None and len(exact_calls)<len(expected)
    calls_exact=(len(exact_calls)==len(expected) and not any(x.get('rejected') for x in trace))
    return {'trace':trace,'final_answer':final,'terminal_reason':reason,'actual_call_count':len(exact_calls),'expected_call_count':len(expected),'early_final':early_final,'extra_call':reason=='extra_call','wrong_call':reason=='wrong_call','calls_exact':calls_exact,'final_answer_exact':exact_answer(final,rec['expected_answer']) if final is not None else False,'success':calls_exact and final is not None and exact_answer(final,rec['expected_answer'])}

def run_case(model,tok,rec,prose_penalty):
    started=time.monotonic(); penalty=1.2 if rec['kind']=='tool' else prose_penalty
    def emit(messages): return generate(model,tok,messages,penalty=penalty,mode='greedy',seed=20261101,cap=CAP)
    if rec['kind']=='prose':
        g=emit(rec['messages']); return {'id':rec['id'],'kind':'prose','family':rec['family'],'penalty':penalty,'generation':g,'output':g['output'],'correct_by_diagnostic_rubric':score_prose(g['output'],rec['rubric']),'latency_seconds':time.monotonic()-started}
    result=tool_trace(rec,emit); result.update(id=rec['id'],kind='tool',family=rec['family'],penalty=1.2,latency_seconds=time.monotonic()-started); return result
def summary(rows):
    prose=[r for r in rows if r['kind']=='prose']; tools=[r for r in rows if r['kind']=='tool']; generations=[r['generation'] for r in prose]+[x['generation'] for r in tools for x in r['trace']]
    return {'prose':{'cases':len(prose),'diagnostic_rubric_passes':sum(r['correct_by_diagnostic_rubric'] for r in prose),'manual_review_required':True},'tools':{'cases':len(tools),'full_success':sum(r['success'] for r in tools),'exact_call_trace':sum(r['calls_exact'] for r in tools),'final_answer_exact':sum(r['final_answer_exact'] for r in tools),'early_final':sum(r['early_final'] for r in tools),'wrong_call':sum(r['wrong_call'] for r in tools),'extra_call':sum(r['extra_call'] for r in tools)},'decode':{'stop_counts':dict(Counter(g['stop'] for g in generations)),'cap_hits':sum(g['stop']=='length' and g['generated_tokens']>=CAP for g in generations),'mean_repeated_4gram_fraction':sum(g['repeated_4gram_fraction'] for g in generations)/max(1,len(generations)),'mean_case_latency_seconds':sum(r['latency_seconds'] for r in rows)/max(1,len(rows))}}
def guarded_health(baseline):
    health = {**system_health(), **memory_stats()}
    reason = 'stop_file' if stop_requested(ROOT) else violation(health, baseline)
    if reason: raise RuntimeError('inference_guard_' + reason)
    return health
def main():
    assert sha(CHECKPOINT/'model.safetensors')==EXPECTED
    records=[json.loads(x) for x in DEV.read_text().splitlines() if x]; assert all(r['split']=='development' for r in records)
    OUT.mkdir(parents=True,exist_ok=True); memory_policy=configure_memory(); baseline=guarded_health({**system_health(), **memory_stats()}); tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json')); model=Model(768,12,16384); model.load_weights(str(CHECKPOINT/'model.safetensors')); model.set_dtype(mx.bfloat16); mx.eval(model.parameters()); guarded_health(baseline)
    arms={}
    for name,penalty in [('baseline_all_1.2',1.2),('prose_only_1.3',1.3)]:
        rows=[]
        for r in records:
            guarded_health(baseline); rows.append(run_case(model,tok,r,penalty))
        arms[name]={'prose_penalty':penalty,'tool_penalty':1.2,'rows':rows,'summary':summary(rows)}; (OUT/(name+'.json')).write_text(json.dumps(arms[name],indent=2)+'\n')
    report={'kind':'bounded_frozen_checkpoint_development_only_decode_comparison','status':'completed_host_run','checkpoint':str(CHECKPOINT.relative_to(ROOT)),'model_sha256':EXPECTED,'development_cases_sha256':sha(DEV),'confirmation_opened':False,'memory_policy':memory_policy,'initial_health':baseline,'final_health':guarded_health(baseline),'arms':{k:{'prose_penalty':v['prose_penalty'],'tool_penalty':1.2,'summary':v['summary']} for k,v in arms.items()},'memory':memory_stats(),'new_training_tokens':0,'limitations':['Tool call count is never prescribed to the model. Wrong, malformed, and extra calls are rejected and retained in the trace.','Prose substring diagnostics are not semantic correctness; review actual outputs.','No reference longer than cap is supplied to decoding; output cap, EOS/role stop, and latency are recorded.']}
    (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n'); print(json.dumps(report,indent=2))
if __name__=='__main__': main()
