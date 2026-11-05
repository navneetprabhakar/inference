"""Explicit experimental readable-role serialization; default format is unchanged."""
import numpy as np
LABELS={'system':'System:','user':'User:','assistant':'Assistant:','tool':'Tool result:'}
EOS='<|endoftext|>'

def render(messages, assistant_prompt=False):
    return ''.join(LABELS[m['role']]+'\n'+m['content']+(EOS if m['role']=='assistant' else '')+'\n' for m in messages)+('Assistant:\n' if assistant_prompt else '')

def encode_episode(tok,messages):
    text='';spans=[]
    for m in messages:
        text+=LABELS[m['role']]+'\n';start=len(text)
        text+=m['content']+(EOS if m['role']=='assistant' else '')
        if m['role']=='assistant':spans.append((start,len(text)))
        text+='\n'
    encoded=tok.encode(text);n=len(encoded.ids)
    if n>513 or not spans:return None
    # The inference prompt must end at the same token boundary as training.
    for start,end in spans:
        prefix=tok.encode(text[:start]).ids
        if encoded.ids[:len(prefix)]!=prefix:raise ValueError('Plain-role prefix tokenization mismatch')
    weights=[int(any(a>=start and b<=end and b>a for start,end in spans)) for a,b in encoded.offsets]
    ids=np.full(513,1,np.int32);mask=np.zeros(512,np.float32)
    ids[:n]=encoded.ids;mask[:n-1]=weights[1:]
    if not mask.sum():raise ValueError('No assistant targets')
    return ids,mask,n
