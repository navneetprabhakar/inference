"""Shared bounded SFT format, local fixtures, generation and objective."""
import json,hashlib,math
from pathlib import Path
import numpy as np
import mlx.core as mx
import mlx.nn as nn
ROOT=Path(__file__).resolve().parents[1]
ROLES={'system':'<|system|>','user':'<|user|>','assistant':'<|assistant|>','tool':'<|tool_result|>'}
EOS='<|endoftext|>';CALL='<|tool_call|>'
SCHEMAS={'calculate':{'op':'add|subtract|multiply|divide','a':'number','b':'number'},'convert':{'value':'number','from_unit':'m|km|cm','to_unit':'m|km|cm'},'get_weather':{'city':'string'},'lookup_item':{'item_id':'string'},'search_notes':{'query':'string'}}
def system(names=None):
    return 'Answer briefly in English. Use tools only when needed. Ask for missing arguments. Never invent tool results. Tools: '+json.dumps({k:SCHEMAS[k] for k in (names or SCHEMAS)},separators=(',',':'))+'. To call a tool output '+CALL+' followed by JSON with name and arguments.'
def render(messages,assistant_prompt=False):
    out=''
    for m in messages:
        out+=ROLES[m['role']]+m['content']+(EOS if m['role']=='assistant' else '\n')
    return out+(ROLES['assistant'] if assistant_prompt else '')
def encode_episode(tok,messages):
    ids=[];weights=[]
    for m in messages:
        prefix=tok.encode(ROLES[m['role']]).ids;body=tok.encode(m['content']+(EOS if m['role']=='assistant' else '\n')).ids
        ids+=prefix+body;weights += [0]*len(prefix)+[int(m['role']=='assistant')]*len(body)
    if len(ids)>513 or not any(weights[1:]):return None
    n=len(ids);ids+=[1]*(513-n);weights+=[0]*(513-n)
    return np.array(ids,np.int32),np.array(weights[1:],np.float32),n

def masked_loss(model,tokens,mask):
    values=nn.losses.cross_entropy(model(tokens[:,:-1]).astype(mx.float32),tokens[:,1:],reduction='none')
    return (values*mask).sum()/mx.maximum(mask.sum(),1)

def execute(call):
    if not isinstance(call,dict) or set(call)!={'name','arguments'}:raise ValueError('Expected name and arguments')
    name=call['name'];a=call['arguments']
    if name not in SCHEMAS or not isinstance(a,dict) or set(a)!=set(SCHEMAS[name]):raise ValueError('Unknown tool or arguments')
    if name=='calculate':
        if any(type(a[k]) not in (int,float) or not math.isfinite(a[k]) for k in ['a','b']):raise ValueError('Numeric inputs required')
        x,y=a['a'],a['b'];op=a['op']
        if op=='divide' and y==0:return {'error':'division by zero'}
        if op not in ['add','subtract','multiply','divide']:raise ValueError('Unknown operation')
        return {'result':round({'add':lambda:x+y,'subtract':lambda:x-y,'multiply':lambda:x*y,'divide':lambda:x/y}[op](),6)}
    if name=='convert':
        scales={'m':1,'km':1000,'cm':.01}
        if type(a['value']) not in (int,float) or not math.isfinite(a['value']) or a['from_unit'] not in scales or a['to_unit'] not in scales:raise ValueError('Invalid conversion')
        return {'result':round(a['value']*scales[a['from_unit']]/scales[a['to_unit']],6),'unit':a['to_unit']}
    if not all(isinstance(v,str) and v.strip() for v in a.values()):raise ValueError('Nonempty strings required')
    key=next(iter(a.values()));h=int(hashlib.sha256(key.casefold().encode()).hexdigest()[:8],16)
    if name=='get_weather':return {'city':key,'temperature_c':10+h%25,'condition':['sunny','cloudy','rainy'][h%3],'fixture':True}
    if name=='lookup_item':return {'item_id':key,'price':10+h%200,'stock':h%30,'fixture':True}
    return {'query':key,'note':'The '+key+' meeting is on '+['Monday','Tuesday','Wednesday','Thursday','Friday'][h%5]+'.','fixture':True}

def result_answer(call,result):
    if 'error' in result:return 'The calculation failed: division by zero. Please use a nonzero divisor.'
    n=call['name']
    if n=='calculate':return 'The result is '+str(result['result'])+'.'
    if n=='convert':return str(result['result'])+' '+result['unit']+'.'
    if n=='get_weather':return 'The test weather for '+result['city']+' is '+str(result['temperature_c'])+' degrees Celsius and '+result['condition']+'.'
    if n=='lookup_item':return 'The test price is '+str(result['price'])+' and '+str(result['stock'])+' units are in stock.'
    return result['note']

def call_text(call):return CALL+json.dumps(call,separators=(',',':'),ensure_ascii=False)
def parse_call(text):
    text=text.strip()
    if text.startswith(CALL):text=text[len(CALL):].strip()
    a=json.loads(text)
    if not isinstance(a,dict) or set(a)!={'name','arguments'}:raise ValueError('Invalid call shape')
    return a

def generate(model,tok,messages,penalty=1.2,mode='greedy',seed=100,cap=96,raw_prompt=None):
    ids=tok.encode(raw_prompt if raw_prompt is not None else render(messages,True)).ids
    if len(ids)>496:return {'output':'','stop':'context_overflow','generated_tokens':0,'repeated_4gram_fraction':0}
    cap=min(cap,512-len(ids))
    mx.random.seed(seed);output=[];stop='length';boundary={tok.token_to_id(x) for x in ROLES.values()};role_stop=False
    for _ in range(cap):
        logits=model(mx.array([ids]))[0,-1].astype(mx.float32)
        if output and penalty!=1:
            ix=mx.array(sorted(set(output)));v=logits[ix];logits=logits.at[ix].add(mx.where(v<0,v*penalty,v/penalty)-v)
        if mode=='greedy':n=int(mx.argmax(logits))
        else:
            order=mx.argsort(-logits);v=logits[order]/.7;probs=mx.softmax(v);keep=mx.cumsum(probs)-probs<.9;v=mx.where(keep,v,-float('inf'));n=int(order[mx.random.categorical(v)])
        if n==1:stop='eos';break
        if n in boundary:stop='role_boundary';role_stop=True;break
        output.append(n);ids.append(n)
    grams=[tuple(output[i:i+4]) for i in range(max(0,len(output)-3))]
    return {'output':tok.decode(output,skip_special_tokens=False),'stop':stop,'role_boundary_intervention':role_stop,'generated_tokens':len(output),'repeated_4gram_fraction':1-len(set(grams))/len(grams) if grams else 0}
