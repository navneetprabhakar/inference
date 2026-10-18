"""Bounded typed assistant decisions and correlated tool-result messages."""
import json
import re

class InvalidDecision(ValueError):
    def __init__(self,message,raw=None):
        super().__init__(message);self.raw=raw


ID=re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}')


def bounded(value,depth=0):
    if depth>8:raise ValueError('JSON nesting limit exceeded')
    if value is None or type(value) is bool:return
    if type(value) is int:
        if abs(value)>2**53-1:raise ValueError('JSON integer exceeds portable exact range')
        return
    if isinstance(value,str):value.encode('utf-8');return
    if isinstance(value,list):
        if len(value)>256:raise ValueError('JSON array limit exceeded')
        for item in value:bounded(item,depth+1)
        return
    if isinstance(value,dict):
        if len(value)>64 or any(not isinstance(k,str) for k in value):raise ValueError('Bounded string-keyed object required')
        for k,v in value.items():bounded(k,depth+1);bounded(v,depth+1)
        return
    raise ValueError('Only exact JSON integers, strings, booleans, null, arrays and objects supported')


def canonical(value,limit=8192):
    bounded(value)
    text=json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    if len(text.encode('utf-8'))>limit:raise ValueError('JSON payload exceeds byte limit')
    return text


def parse(text,limit=8192):
    if not isinstance(text,str) or len(text.encode('utf-8'))>limit:raise ValueError('Bounded JSON string required')
    def pairs(items):
        obj={}
        for key,value in items:
            if key in obj:raise ValueError('Duplicate JSON key')
            obj[key]=value
        return obj
    def reject(value):raise ValueError('Floating/nonfinite JSON number refused')
    try:value=json.loads(text,object_pairs_hook=pairs,parse_float=reject,parse_constant=reject)
    except (json.JSONDecodeError,RecursionError) as exc:raise ValueError('Invalid bounded JSON') from exc
    canonical(value,limit);return value


def identifier(value):
    if not isinstance(value,str) or ID.fullmatch(value) is None:raise ValueError('Bounded tool/call identifier required')


def decision(value):
    canonical(value)
    if not isinstance(value,dict):raise ValueError('Typed decision object required')
    kind=value.get('kind')
    if kind=='call':
        if set(value)!={'kind','id','name','arguments'} or not isinstance(value['arguments'],dict):raise ValueError('One explicit tool call required')
        identifier(value['id']);identifier(value['name'])
    elif kind=='answer':
        if set(value)!={'kind','text','facts'} or not isinstance(value['facts'],dict) or not isinstance(value['text'],str) or not value['text'].strip():raise ValueError('Answer text and explicit fact object required')
    elif kind=='clarify':
        if (set(value)!={'kind','question','missing'} or not isinstance(value['question'],str) or not value['question'].strip()
            or not isinstance(value['missing'],list) or not 1<=len(value['missing'])<=16
            or any(not isinstance(v,str) or not v.strip() for v in value['missing']) or len(set(value['missing']))!=len(value['missing'])):
            raise ValueError('Clarification question and unique missing fields required')
    else:raise ValueError('Unknown decision kind')
    return value


def tool_result(value):
    canonical(value)
    if (not isinstance(value,dict) or set(value)!={'id','name','ok','data','error'} or type(value['ok']) is not bool):raise ValueError('Correlated tool result required')
    identifier(value['id']);identifier(value['name'])
    if value['ok']:
        if not isinstance(value['data'],dict) or value['error'] is not None:raise ValueError('Invalid successful result')
    elif (value['data'] is not None or not isinstance(value['error'],dict) or set(value['error'])!={'code','message'}
        or any(not isinstance(v,str) or not v for v in value['error'].values())):raise ValueError('Invalid error result')
    return value


def validate_messages(messages,complete=True):
    if not isinstance(messages,list) or not 1<=len(messages)<=64:raise ValueError('Bounded conversation required')
    state='user';pending=None;seen=set();parsed=[]
    for i,m in enumerate(messages):
        if not isinstance(m,dict) or set(m)!={'role','content'} or not isinstance(m['content'],str):raise ValueError('Plain role/content envelope required')
        if len(m['content'].encode('utf-8'))>16384:raise ValueError('Message byte limit exceeded')
        role=m['role'];body=None
        if role=='system' and i==0:parsed.append(None);continue
        if role!=state:raise ValueError('Invalid tool conversation role order')
        if role=='user':state='assistant'
        elif role=='assistant':
            body=decision(parse(m['content']))
            if body['kind']=='call':
                if body['id'] in seen:raise ValueError('Duplicate tool call ID')
                seen.add(body['id']);pending=body;state='tool'
            else:state='user'
        elif role=='tool':
            body=tool_result(parse(m['content']))
            if (body['id'],body['name'])!=(pending['id'],pending['name']):raise ValueError('Tool result/call correlation differs')
            pending=None;state='assistant'
        parsed.append(body)
    if pending is not None:raise ValueError('Unresolved tool call')
    if complete and (messages[-1]['role']!='assistant' or parsed[-1]['kind']=='call'):raise ValueError('Complete assistant decision required')
    if not complete and messages[-1]['role'] not in ('user','tool'):raise ValueError('Prompt must end with user/tool data')
    return parsed
