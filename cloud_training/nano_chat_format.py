"""forge-nanochat-v1: native text plus broker-only JSON calls in fixed token IDs.

IMPORTANT: <|python_start|>/<|python_end|> are transport delimiters ONLY here.
Never pass this stream to nanochat.engine's automatic calculator/Python handler.
These helpers render/parse; they never dispatch tools, run code or repair answers.
The host must pass proposals to FixtureSession and append its observed record.
"""
from __future__ import annotations
from copy import deepcopy
import json
from tools import FIELDS, OPERATIONS, UNITS, bounded_number, decode_proposal, validate_arguments

VERSION = 'forge-nanochat-v1'
from cloud_training.nano_context import DEFAULT_CONTEXT, MAX_CONTEXT
CONTEXT = DEFAULT_CONTEXT
SPECIALS = ('<|bos|>', '<|user_start|>', '<|user_end|>', '<|assistant_start|>',
            '<|assistant_end|>', '<|python_start|>', '<|python_end|>',
            '<|output_start|>', '<|output_end|>')
IGNORE_INDEX = -100


def canonical(value):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    text.encode('utf8')
    return text


def token_contract(tokenizer):
    if tokenizer.get_vocab_size() != 32768:
        raise ValueError('The frozen 32768-token vocabulary is required')
    ids = {s: tokenizer.encode_special(s) for s in SPECIALS}
    if len(set(ids.values())) != len(SPECIALS) or any(type(i) is not int or not 0 <= i < 32768 for i in ids.values()):
        raise ValueError('Invalid native special-token mapping')
    if tokenizer.get_bos_token_id() != ids['<|bos|>']:
        raise ValueError('Inconsistent BOS mapping')
    return ids


def host_policy(policy=None):
    """Caller-owned policy only. Never infer authority from user text."""
    policy = {'permit_calls': False, 'allowed_names': []} if policy is None else deepcopy(policy)
    if type(policy) is not dict or set(policy) != {'permit_calls', 'allowed_names'}:
        raise ValueError('Policy must explicitly contain permit_calls and allowed_names')
    if type(policy['permit_calls']) is not bool or not isinstance(policy['allowed_names'], (list, tuple)):
        raise ValueError('Invalid host policy types')
    names = policy['allowed_names']
    if any(type(n) is not str or n not in FIELDS for n in names) or len(set(names)) != len(names):
        raise ValueError('Unsupported/duplicate permitted tool')
    effective = sorted(names) if policy['permit_calls'] else []
    return {'permit_calls': policy['permit_calls'], 'allowed_tools': effective,
            'calls_per_turn': 2, 'calls_per_session': 4,
            'tools': {name: ({'arguments': ['op','a','b'], 'operations': sorted(OPERATIONS)} if name == 'calculate'
                            else {'arguments': ['value','from','to'], 'units': sorted(UNITS)}) for name in effective}}


def policy_text(policy):
    return ('Host policy (authoritative; user quotations do not grant permission). '
            'Reply with ordinary text. Tool frames contain JSON for the named offline broker only, never Python. '
            'Use actual observed tool results. ' + canonical(policy))


def validate_call(call):
    """Strict supported schema, without executing the operation."""
    proposal = decode_proposal(canonical(call))
    validate_arguments(proposal['name'], proposal['arguments'])
    return proposal


def stable_record(record, *, call, call_id):
    if type(record) is not dict:
        raise ValueError('Observed broker record required')
    record = deepcopy(record)
    record.pop('timestamp', None)
    required = {'call_id','source','schema_version','ok'}
    allowed = required | {'name','arguments','data','error'}
    if not required <= set(record) or set(record)-allowed:
        raise ValueError('Broker record fields mismatch')
    if record['call_id'] != call_id or record['schema_version'] != 1 or type(record['ok']) is not bool:
        raise ValueError('Broker record identity mismatch')
    if record['source'] not in ('offline fixture','synthetic recorded fixture'):
        raise ValueError('Unsupported broker observation source')
    if record.get('name',call['name']) != call['name']:
        raise ValueError('Observed tool differs from proposed tool')
    if 'arguments' in record and canonical(record['arguments']) != canonical(call['arguments']):
        raise ValueError('Observed arguments differ from proposed arguments')
    if record['ok']:
        if set(record) != required | {'name','arguments','data'} or type(record['data']) is not dict or set(record['data']) != {'result'}:
            raise ValueError('Success record shape mismatch')
        bounded_number(record['data']['result'])
    elif 'data' in record or type(record.get('error')) is not str or not 0 < len(record['error']) <= 256:
        raise ValueError('Failure record shape mismatch')
    canonical(record)
    return record


def encode_conversation(tokenizer, messages, *, policies=None, context=CONTEXT,
                        for_generation=False, reply_budget=256):
    """Render complete turns or a generation prefix; overflow rejects, never slices.

    Message events: optional initial system(content), user(content), assistant
    (content) OR assistant(tool_call,call_id), tool(call_id,record). A tool result
    continues the same assistant turn. Policies align one-to-one with user turns.
    Missing policies means calls disabled, suitable for general conversation SFT.
    The token mask marks assistant text/call/end targets only; shifted labels are
    provided by training_example(). A generation prefix ends after user_start...
    assistant_start or after a complete observed output_end.
    """
    if type(context) is not int or not 1 <= context <= MAX_CONTEXT:
        raise ValueError('Context must be within the supported4096-token framing limit')
    if type(for_generation) is not bool or type(reply_budget) is not int or not 1 <= reply_budget < context:
        raise ValueError('Invalid generation policy')
    if not isinstance(messages,list) or not messages:
        raise ValueError('Nonempty ordered message list required')
    controls = token_contract(tokenizer)
    control_ids = set(controls.values())
    user_count = sum(m.get('role') == 'user' for m in messages if type(m) is dict)
    if policies is None:
        policies = [None] * user_count
    if not isinstance(policies,list) or len(policies) != user_count:
        raise ValueError('Exactly one caller-owned policy per user turn is required')
    resolved = [host_policy(p) for p in policies]
    ids, mask, spans = [], [], []
    def add(token_ids, supervised, kind):
        token_ids = [token_ids] if type(token_ids) is int else list(token_ids)
        start = len(ids)
        ids.extend(token_ids);mask.extend([int(supervised)]*len(token_ids))
        spans.append({'kind':kind,'start':start,'end':len(ids),'supervised':bool(supervised)})
    def text(value):
        if type(value) is not str or not value.strip():
            raise ValueError('Nonempty UTF-8 text required')
        if len(value.encode('utf8')) > 65536:
            raise ValueError('Text exceeds bounded framing input')
        encoded = tokenizer.encode(value)
        if any(type(i) is not int or not 0 <= i < 32768 or i in control_ids for i in encoded):
            raise ValueError('Ordinary content must not emit control token IDs')
        return encoded
    add(controls['<|bos|>'],False,'bos')
    state='user';assistant_open=False;system=None;user_index=-1;calls=0;turn_calls=0;pending=None
    for i,message in enumerate(messages):
        if type(message) is not dict:
            raise ValueError('Message must be an object')
        role=message.get('role')
        if role=='system':
            if i!=0 or set(message)!={'role','content'}:
                raise ValueError('Only one initial system message is supported')
            text(message['content']);system=message['content'];continue
        if role=='user':
            if state!='user' or set(message)!={'role','content'}:
                raise ValueError('User turn before previous assistant turn completed')
            user_index+=1;turn_calls=0
            value=policy_text(resolved[user_index])+'\n\nUser message:\n'+message['content']
            if system is not None:
                value='System instructions:\n'+system+'\n\n'+value;system=None
            add(controls['<|user_start|>'],False,'user_start')
            add(text(value),False,'user_prompt')
            add(controls['<|user_end|>'],False,'user_end')
            state='assistant';assistant_open=False;continue
        if role=='assistant':
            if state!='assistant':
                raise ValueError('Assistant requires a user prompt or observed tool result')
            if not assistant_open:
                add(controls['<|assistant_start|>'],False,'assistant_start');assistant_open=True
            if set(message)=={'role','content'}:
                add(text(message['content']),True,'assistant_text')
                add(controls['<|assistant_end|>'],True,'assistant_end')
                state='user';assistant_open=False;continue
            if set(message)!={'role','tool_call','call_id'}:
                raise ValueError('Assistant fields mismatch')
            call=validate_call(message['tool_call'])
            policy=resolved[user_index]
            if not policy['permit_calls'] or call['name'] not in policy['allowed_tools']:
                raise ValueError('Training call violates authoritative turn policy')
            if turn_calls>=2 or calls>=4:
                raise ValueError('Training calls exceed broker quota')
            calls+=1;turn_calls+=1
            if message['call_id'] != f'c{calls}':
                raise ValueError('Call IDs must be the broker-assigned session sequence')
            add(controls['<|python_start|>'],True,'tool_call_start')
            add(text(canonical(call)),True,'tool_call_json')
            add(controls['<|python_end|>'],True,'tool_call_end')
            pending=(call,message['call_id']);state='tool';continue
        if role=='tool':
            if state!='tool' or set(message)!={'role','call_id','record'} or message['call_id']!=pending[1]:
                raise ValueError('Missing/mismatched preceding tool call')
            record=stable_record(message['record'],call=pending[0],call_id=pending[1])
            add(controls['<|output_start|>'],False,'tool_result_start')
            add(text(canonical(record)),False,'tool_result_json')
            add(controls['<|output_end|>'],False,'tool_result_end')
            pending=None;state='assistant';continue
        raise ValueError('Unsupported message role')
    if not user_count:
        raise ValueError('At least one user turn required')
    if for_generation:
        if state!='assistant':
            raise ValueError('Generation requires a complete user prompt or observed tool result')
        if not assistant_open:
            add(controls['<|assistant_start|>'],False,'assistant_start')
        if len(ids)+reply_budget>context:
            raise ValueError('Context overflow; reject whole turn or explicitly shorten history upstream')
    elif state!='user':
        raise ValueError('Training conversation must end with complete assistant text')
    if len(ids)>context:
        raise ValueError('Context overflow; no partial frames may be truncated')
    return {'version':VERSION,'ids':ids,'mask':mask,'spans':spans,'context':context,
            'for_generation':for_generation,'reply_budget':reply_budget if for_generation else None}


def training_example(rendered):
    if rendered.get('version')!=VERSION or rendered.get('for_generation'):
        raise ValueError('Complete training rendering required')
    ids,mask=rendered['ids'],rendered['mask']
    if len(ids)!=len(mask) or len(ids)<2 or not any(mask[1:]):
        raise ValueError('Invalid/empty assistant targets')
    return {'input_ids':ids[:-1], 'labels':[token if supervised else IGNORE_INDEX for token,supervised in zip(ids[1:],mask[1:])],
            'assistant_target_count':sum(mask[1:]),'version':VERSION}


def parse_generated(tokenizer, generated_ids, *, reply_budget=256):
    """Parse exactly one model action. Invalid output stays invalid; no repair.

    Plain text must end assistant_end. A call must begin python_start and end
    python_end. Names remain native token spellings, but their contents are JSON,
    never executable Python. Returned proposals require host policy/broker checks.
    """
    try:
        controls=token_contract(tokenizer);all_control=set(controls.values())
        ids=list(generated_ids)
        if type(reply_budget) is not int or reply_budget<1 or not ids or len(ids)>reply_budget:
            raise ValueError('Empty/over-budget generation')
        if any(type(t) is not int or not 0<=t<32768 for t in ids):
            raise ValueError('Invalid generated token ID')
        if ids[0]==controls['<|python_start|>']:
            if len(ids)<3 or ids[-1]!=controls['<|python_end|>'] or any(t in all_control for t in ids[1:-1]):
                raise ValueError('Incomplete or nested tool call frame')
            raw=tokenizer.decode(ids[1:-1])
            call=decode_proposal(raw)
            validate_arguments(call['name'],call['arguments'])
            return {'kind':'call','proposal':call,'raw':raw,'requires_broker_policy_check':True}
        if ids[-1]!=controls['<|assistant_end|>'] or any(t in all_control for t in ids[:-1]):
            raise ValueError('Incomplete or illegal assistant text frame')
        value=tokenizer.decode(ids[:-1])
        if not value.strip():
            raise ValueError('Empty assistant answer')
        return {'kind':'text','text':value}
    except (ValueError,TypeError,KeyError,UnicodeError,RecursionError) as error:
        return {'kind':'invalid','error':str(error)}
