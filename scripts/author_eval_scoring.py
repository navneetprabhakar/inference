"""GPU-free strict trace scoring used by the authored development decoder."""
import json

def exact_answer(a,b): return ' '.join(a.split()).casefold()==' '.join(b.split()).casefold()
def tool_trace(rec, emit, max_turns=6, parser=None, executor=None):
    if parser is None or executor is None:
        from sft_common import parse_call, execute
        parser = parser or parse_call; executor = executor or execute
    messages=list(rec['messages']); expected=rec['calls']; trace=[]; final=None; reason=None
    for turn in range(min(max_turns,rec.get('max_turns',max_turns))):
        generation=emit(messages); text=generation['output']; item={'turn':turn+1,'generation':generation,'raw_output':text}
        if not text.strip().startswith('<|tool_call|>'):
            item['kind']='final_answer'; trace.append(item); final=text; reason='final_answer'; break
        try: call=parser(text); item.update(kind='tool_call',call=call)
        except Exception as exc: item.update(kind='invalid_tool_call',rejected=True,error=type(exc).__name__); trace.append(item); reason='invalid_tool_call'; break
        index=sum(x.get('kind')=='tool_call' and x.get('executed') for x in trace)
        if index>=len(expected): item.update(rejected=True,rejection='extra_call'); trace.append(item); reason='extra_call'; break
        wanted=expected[index]
        if call['name']!=wanted['name'] or call['arguments']!=wanted['arguments']:
            item.update(rejected=True,rejection='wrong_call',expected=wanted); trace.append(item); reason='wrong_call'; break
        try:
            result=executor(call); item.update(executed=True,result=result); messages += [{'role':'assistant','content':text},{'role':'tool','content':json.dumps(result,separators=(',',':'))}]; trace.append(item)
        except Exception as exc: item.update(rejected=True,rejection='fixture_execution_error',error=type(exc).__name__); trace.append(item); reason='fixture_execution_error'; break
    else: reason='turn_limit'
    calls=[x for x in trace if x.get('kind')=='tool_call' and x.get('executed')]; early=final is not None and len(calls)<len(expected); exact=len(calls)==len(expected) and not any(x.get('rejected') for x in trace)
    return {'trace':trace,'final_answer':final,'terminal_reason':reason,'actual_call_count':len(calls),'expected_call_count':len(expected),'early_final':early,'extra_call':reason=='extra_call','wrong_call':reason=='wrong_call','calls_exact':exact,'final_answer_exact':exact_answer(final,rec['expected_answer']) if final is not None else False,'success':exact and final is not None and exact_answer(final,rec['expected_answer'])}
