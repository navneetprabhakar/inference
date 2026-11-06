"""Replay one supplied legacy lesson into current-turn own-base SFT rows.

No generators, dataset reads, model execution, answer synthesis or admission.
Broker identity is checked; arbitrary natural-language answer correctness is not.
"""
from copy import deepcopy
from dataclasses import asdict, is_dataclass
import hashlib
import json

from own_base_chat import policy_text, stable_tool_record
from own_base_sft_rows import last_turn_row
from tools import FixtureSession


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def legacy_projection(record):
    if record['ok']:
        return dict(name=record.get('name'), id=record['call_id'], result=record['data']['result'])
    return dict(id=record['call_id'], error=record['error'])


def adapt_lesson(lesson, tokenizer):
    """Return per-user current-turn rows plus full, separate replay audit.

    Exact raw strings are preserved. Whole lessons fail closed on any mismatch
    or context overflow; no partial result, answer repair or truncation occurs.
    """
    original=deepcopy(asdict(lesson) if is_dataclass(lesson) else lesson)
    if type(original)!=dict or set(original)!={'family','history','observations','policy'}:
        raise ValueError('legacy lesson fields mismatch')
    if not isinstance(original['family'],str) or not original['family']:
        raise ValueError('family required')
    for key in ('history','observations','policy'):
        if type(original[key])!=list:raise ValueError('legacy lists required')
    identity=hashlib.sha256(canonical(original).encode()).hexdigest()
    session=FixtureSession();history=[];rows=[];observed=0;turn=-1;closed=True;current_policy=None

    def finish_turn():
        if turn<0:return
        if not closed:raise ValueError('unresolved teacher turn')
        framed=[dict(role='system',text=policy_text(current_policy['permit_calls'],current_policy.get('allowed_names')))]+deepcopy(history)
        row=last_turn_row(tokenizer,framed,reply_budget=256,context=1024)
        rows.append(dict(turn_index=turn,history=framed,row=row,policy=deepcopy(current_policy)))

    messages=original['history'];i=0
    while i<len(messages):
        message=messages[i]
        if type(message)!=dict:raise ValueError('history message must be object')
        role=message.get('role')
        if role=='user':
            if set(message)!={'role','text'} or not isinstance(message['text'],str) or not message['text'].strip():raise ValueError('user frame mismatch')
            finish_turn();turn+=1
            if turn>=len(original['policy']):raise ValueError('missing user policy')
            current_policy=original['policy'][turn]
            if type(current_policy)!=dict or not {'permit_calls','fixture_for','fixture'}<=set(current_policy) or set(current_policy)-{'permit_calls','fixture_for','fixture','allowed_names'}:raise ValueError('policy fields mismatch')
            # Validate exactly the host-policy interface used by current serving.
            policy_text(current_policy['permit_calls'],current_policy.get('allowed_names'))
            session.start_turn(**deepcopy(current_policy))
            history.append(deepcopy(message));closed=False;i+=1;continue
        if role!='assistant' or turn<0 or closed:raise ValueError('unexpected teacher role/order')
        if set(message)=={'role','text'}:
            if not isinstance(message['text'],str) or not message['text'].strip():raise ValueError('empty teacher answer')
            history.append(deepcopy(message));closed=True;i+=1;continue
        if set(message)!={'role','call'}:raise ValueError('legacy assistant fields mismatch')
        call=message['call']
        if type(call)!=dict or set(call)!={'name','arguments'}:raise ValueError('proposal fields mismatch')
        if i+1>=len(messages) or type(messages[i+1])!=dict or set(messages[i+1])!={'role','result'} or messages[i+1]['role']!='tool':raise ValueError('missing legacy tool result')
        if observed>=len(original['observations']):raise ValueError('missing recorded observation')
        replay=session.propose(canonical(call),assistant_call_boundary=True)
        stable=stable_tool_record(replay)
        old=original['observations'][observed]
        if canonical(stable_tool_record(old))!=canonical(stable):raise ValueError('recorded observation differs from broker replay')
        if canonical(messages[i+1]['result'])!=canonical(legacy_projection(stable)):raise ValueError('legacy result differs from broker observation')
        decision=session.decisions[-1]
        if not decision['dispatched']:raise ValueError('teacher proposal violates host policy or schema')
        history.extend((dict(role='assistant',call=deepcopy(call),call_id=replay['call_id']),dict(role='tool',record=stable)))
        observed+=1;i+=2
    finish_turn()
    if not rows or turn+1!=len(original['policy']) or observed!=len(original['observations']):raise ValueError('unused/missing policies or observations')
    return dict(family=original['family'],source_lesson_sha256=identity,turns=rows,
                audit=dict(original=original,replay_records=session.trace,decisions=session.decisions,
                           observation_sources=[r['source'] for r in session.trace],
                           answer_semantics='Teacher text preserved verbatim; arbitrary answer correctness requires independent quality review.'),
                admitted=False)
