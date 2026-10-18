"""Typed tool-dialogue framing using the existing disjoint BPE/control namespace."""
from slm.common.tokenizer import STRUCTURAL,OFFSET
from slm.tools.protocol import validate_messages,canonical,parse,decision


def serialize(tokenizer,messages,objective='assistant',max_length=None,complete=True):
    if objective not in ('assistant','all'):raise ValueError('Unknown tool loss objective')
    bodies=validate_messages(messages,complete=complete);ids=[STRUCTURAL['bos']];mask=[0]
    for m,body in zip(messages,bodies):
        role=m['role'];supervised=int(role=='assistant');payload=[]
        if role=='assistant' and body['kind']=='call':payload=[STRUCTURAL['tool_call_start'],*tokenizer.encode(canonical(body)),STRUCTURAL['tool_call_end']]
        else:payload=tokenizer.encode(canonical(body) if body is not None else m['content'])
        ids.extend([STRUCTURAL[role],*payload,STRUCTURAL['message_end']]);mask.extend([0,*([supervised]*len(payload)),supervised])
    if complete:ids.append(STRUCTURAL['eos']);mask.append(int(messages[-1]['role']=='assistant'))
    if objective=='all':mask=[0]+[1]*(len(ids)-1)
    length=len(ids)-1
    if max_length is not None and (type(max_length) is not int or max_length<1 or length>max_length):raise ValueError('Tool dialogue exceeds context; refusing truncation')
    return ids[:-1],ids[1:],mask[1:]


def prompt_ids(tokenizer,messages):
    # Incomplete history has no EOS. Recover its entire sequence from aligned x/y.
    x,y,_=serialize(tokenizer,messages,complete=False)
    return [*x,y[-1],STRUCTURAL['assistant']]


def parse_generation(tokenizer,result):
    if result['stop_reason'] not in ('eos','message_end') or not result['token_ids']:raise ValueError('Complete terminated decision required')
    tokens=result['token_ids'];stop=1 if result['stop_reason']=='eos' else 3
    if tokens[-1]!=stop:raise ValueError('Stop token metadata differs')
    body=tokens[:-1];call=bool(body and body[0]==STRUCTURAL['tool_call_start'])
    if call:
        if len(body)<3 or body[-1]!=STRUCTURAL['tool_call_end']:raise ValueError('Incomplete tool call frame')
        body=body[1:-1]
    if not body or any(type(v) is not int or not OFFSET<=v<tokenizer.vocab_size for v in body):raise ValueError('Invalid decision content/control frame')
    text=tokenizer.decode(body)
    value=decision(parse(text))
    if (value['kind']=='call')!=call:raise ValueError('Decision kind and structural call frame differ')
    return value


def validate_batch(tokenizer,values):
    import numpy as np
    x,y,mask=(np.asarray(a)[0] for a in values)
    if not np.array_equal(x[1:],y[:-1]):raise ValueError('Tool next-token shift differs')
    ids=list(map(int,np.concatenate((x[:1],y))))
    if ids[0]!=0 or ids[-1]!=1:raise ValueError('Invalid tool SFT envelope')
    roles={4:'system',5:'user',6:'assistant',7:'tool'};messages=[];position=1
    while position<len(ids)-1:
        role=roles.get(ids[position]);start=position+1;end=start
        if role is None:raise ValueError('Invalid tool role marker')
        framed=role=='assistant' and ids[start]==8
        if framed:start+=1;end=start
        while end<len(ids) and ids[end]>=OFFSET:end+=1
        if framed:
            if end>=len(ids) or ids[end]!=9:raise ValueError('Invalid tool call boundary')
            boundary=end+1
        else:boundary=end
        if boundary>=len(ids) or ids[boundary]!=3:raise ValueError('Invalid tool message boundary')
        messages.append({'role':role,'content':tokenizer.decode(ids[start:end])});position=boundary+1
    expected=serialize(tokenizer,messages)
    for actual,wanted in zip((x,y,mask),expected):
        if not np.array_equal(actual,wanted):raise ValueError('Tool frame, canonical content or supervision differs')
