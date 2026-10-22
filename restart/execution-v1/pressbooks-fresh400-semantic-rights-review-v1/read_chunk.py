from pathlib import Path
import json,hashlib,sys
ROOT=Path('/Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1');CAP=ROOT/'m2-intake/pressbooks-fresh400-whole-original-capture-v1';P=ROOT/'pressbooks-fresh400-semantic-review-protocol-v1/protocol.json'
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(P.read_bytes())=='fc7ef67532bfe14a57c1914a6f674c2ac2e9d7d973befeb16df05b7e502d7490'
a=sorted(json.loads(P.read_text())['assignments']['rights_review']['records'],key=lambda x:x['text_UTF8_bytes']);idx=int(sys.argv[1]);start=int(sys.argv[2]) if len(sys.argv)>2 else 0
x=a[idx];prefix=f"source-{x['source_id']}-row-{x['ordinal']:06d}";raw=(CAP/(prefix+'.source.json')).read_bytes();o=json.loads(raw);b=(CAP/(prefix+'.text.utf8')).read_bytes();t=b.decode();assert o['text'].encode()==b and sha(b)==x['text_SHA256'] and len(b)==x['text_UTF8_bytes'];end=min(start+10000,len(t));v=t[start:end];assert 0<=start<end
print(json.dumps({'assignment_smallest_index':idx,'identity':x,'source_record_metadata':{k:z for k,z in o.items() if k!='text'},'source_JSON_SHA256':sha(raw),'whole_characters':len(t),'chunk_char_span':[start,end],'chunk_UTF8_span':[len(t[:start].encode()),len(t[:end].encode())],'chunk_SHA256':sha(v.encode())},ensure_ascii=False));print(v)
