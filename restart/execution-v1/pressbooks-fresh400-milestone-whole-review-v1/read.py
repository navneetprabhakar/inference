from pathlib import Path
import json,hashlib,sys
B=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;C=B/'m2-intake/pressbooks-fresh400-whole-original-capture-v1';protocol=B/'pressbooks-fresh400-semantic-review-protocol-v1/protocol.json';proof=B/'pressbooks-fresh400-capture-terminal-parent-verification-v2/verification.json';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(protocol)=='fc7ef67532bfe14a57c1914a6f674c2ac2e9d7d973befeb16df05b7e502d7490';assert sha(proof)=='5b312e92fd851ed7e4d92eedbc9ce5259ae1042f21deba2b5c5c6116ed81061d';items=sorted(json.loads(protocol.read_text())['assignments']['milestone_audit']['records'],key=lambda x:x['text_UTF8_bytes'])
for index in map(int,sys.argv[1:]):
 item=items[index];stem=f"source-{item['source_id']}-row-{item['ordinal']:06d}";p=C/(stem+'.text.utf8');raw=p.read_bytes();assert len(raw)==item['text_UTF8_bytes'] and sha(p)==item['text_SHA256'];s=raw.decode();obj=json.loads((C/(stem+'.source.json')).read_text());assert obj['text']==s;print('=== ASSIGNMENT_SHORT_RANK',index,'SOURCE',stem,'CHARS',len(s),'BYTES',len(raw),'===');print('METADATA',json.dumps({k:v for k,v in obj.items() if k!='text'},ensure_ascii=False));print('WHOLE_CHUNK chars[0,'+str(len(s))+')' if len(s)<=10000 else 'NEEDS_EXPLICIT_CHUNKS');
 if len(s)>10000:raise ValueError('large whole print refused')
 print(s)
