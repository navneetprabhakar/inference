"""Finite reviewed-domain checks, with no renderer/author interpreter imports.

This is not arbitrary-language entailment. Human review binds all complete
surface/program pairs; independent extraction and state execution then check
every instantiated copy of those pairs.
"""
from copy import deepcopy
import re
import string


def fill(value,slots):
    if isinstance(value,str):
        pieces=[]
        for literal,key,fmt,conversion in string.Formatter().parse(value):
            if fmt or conversion:raise ValueError('unreviewed format conversion')
            pieces.append(literal)
            if key is not None:pieces.append(slots[key])
        return ''.join(pieces)
    if isinstance(value,list):return [fill(v,slots) for v in value]
    if isinstance(value,dict):return {k:fill(v,slots) for k,v in value.items()}
    if value is None or type(value)==bool:return value
    raise ValueError('unreviewed semantic value type')


def extract(template,text):
    """Capture each dynamic claim; repeated mentions must bind identically."""
    pattern=[];seen=set()
    for literal,key,fmt,conversion in string.Formatter().parse(template):
        if fmt or conversion:raise ValueError('unreviewed prose conversion')
        pattern.append(re.escape(literal))
        if key is not None:
            if not re.fullmatch('[a-z]+',key):raise ValueError('unreviewed slot name')
            pattern.append('(?P='+key+')' if key in seen else '(?P<'+key+'>.+?)')
            seen.add(key)
    matched=re.fullmatch(''.join(pattern),text,flags=re.DOTALL)
    if not matched:raise ValueError('wording differs from manually reviewed surface')
    return matched.groupdict()


def interpret(program):
    """Separate deterministic facts/event/query executor with fail-closed types."""
    if set(program)!={'initial_facts','turn_events','queries','formats'}:raise ValueError('program schema')
    facts=deepcopy(program['initial_facts']);snapshots=[]
    if len(program['turn_events'])!=2 or len(program['queries'])!=2 or len(program['formats'])!=2:raise ValueError('two-turn program required')
    for index in range(2):
        event=program['turn_events'][index]
        if set(event)-{'set','remove','append','swap'}:raise ValueError('unknown state operation')
        targets=[]
        for operation in ('set','remove','append'):
            changes=event.get(operation,{})
            if not isinstance(changes,dict):raise ValueError('event fields')
            for key,value in changes.items():
                if key not in facts or key in targets:raise ValueError('invalid/conflicting state mutation')
                targets.append(key)
                if operation=='set':facts[key]=deepcopy(value)
                else:
                    if not isinstance(facts[key],list):raise ValueError('list mutation on scalar')
                    if operation=='remove':
                        if facts[key].count(value)!=1:raise ValueError('removal must identify exactly one existing member')
                        facts[key]=[v for v in facts[key] if v!=value]
                    else:
                        if value in facts[key]:raise ValueError('duplicate append')
                        facts[key]=facts[key]+[deepcopy(value)]
        if 'swap' in event:
            keys=event['swap']
            if len(keys)!=2 or keys[0]==keys[1] or any(k not in facts or k in targets for k in keys):raise ValueError('invalid swap')
            old=deepcopy(facts);facts[keys[0]]=old[keys[1]];facts[keys[1]]=old[keys[0]]
        answer={}
        for selector in program['queries'][index]:
            match=re.fullmatch(r'([a-z_]+)(?:\[(\d+)\])?',selector)
            if not match or match[1] not in facts:raise ValueError('unknown fact query')
            value=facts[match[1]]
            if match[2] is not None:
                if not isinstance(value,list):raise ValueError('indexed non-list query')
                offset=int(match[2])
                if offset>=len(value):raise ValueError('query index outside fact list')
                value=value[offset]
            answer[selector]=deepcopy(value)
        snapshots.append(dict(facts=deepcopy(facts),queried_values=answer))
    return snapshots


def validate_task(task,surface,reviewed_program):
    slots=task['state']
    expected_keys={'person','other','thirdperson','place','alternate','third','item','thing','n','m','code'}
    if set(slots)!=expected_keys or any(not isinstance(v,str) or not v for v in slots.values()):raise ValueError('typed slots mismatch')
    for keys in (('person','other','thirdperson'),('place','alternate','third'),('item','thing'),('n','m')):
        if len({slots[k] for k in keys})!=len(keys):raise ValueError('non-distinct semantic entities')
    for key in ('n','m'):
        if not slots[key].isdigit():raise ValueError('nonnumeric identifier')
        value=int(slots[key]);bounds=(10001,299999) if task['split']=='train' else (700001,999999)
        if not bounds[0]<=value<=bounds[1]:raise ValueError('identifier split range mismatch')
    if len(task['history'])!=4:raise ValueError('complete two-turn history required')
    for i,message in enumerate(task['history']):
        role='user' if i%2==0 else 'assistant'
        if set(message)!={'role','text'} or message['role']!=role:raise ValueError('unexpected role/frame')
        template=(surface['first_user_forms'][task['first_user_form']] if i==0 else surface['turns'][i//2][role])
        for key,value in extract(template,message['text']).items():
            if value!=slots[key]:raise ValueError('rendered claim has incorrect entity/value binding')
    program=fill(reviewed_program,slots)
    if task['semantic_state']['program']!=program:raise ValueError('author program differs from reviewed semantics')
    if task['semantic_state']['snapshots']!=interpret(program):raise ValueError('state/event/query interpretation mismatch')
    return True
