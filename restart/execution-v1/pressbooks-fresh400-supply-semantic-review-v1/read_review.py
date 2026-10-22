from pathlib import Path
import json,hashlib,sys
B=Path(__file__).resolve().parent.parent;D=Path(__file__).resolve().parent;O=B/'m2-intake/pressbooks-fresh400-whole-original-capture-v1';h=lambda b:hashlib.sha256(b).hexdigest()
p=B/'pressbooks-fresh400-semantic-review-protocol-v1/protocol.json';raw=p.read_bytes();assert h(raw)=='fc7ef67532bfe14a57c1914a6f674c2ac2e9d7d973befeb16df05b7e502d7490';a=json.loads(raw)['assignments']['supply_investigation']['records'];a=sorted(a,key=lambda r:r['text_UTF8_bytes']);
for idx in map(int,sys.argv[1:]):
 r=a[idx];stem=f"source-{r['source_id']}-row-{r['ordinal']:06}";b=(O/(stem+'.text.utf8')).read_bytes();s=b.decode('utf8');q=(O/(stem+'.source.json')).read_bytes();j=json.loads(q);assert h(b)==r['text_SHA256'] and len(b)==r['text_UTF8_bytes'] and j['text']==s
 assert len(s)<=10000,'Use explicit chunk mode for long text'
 packet={'assignment_sorted_size_index':idx,'source':r,'rawJSON_SHA256':h(q),'metadata':{k:v for k,v in j.items() if k!='text'},'coverage':{'char_start':0,'char_end':len(s),'byte_start':0,'byte_end':len(b),'chunk_SHA256':h(b),'visible_not_yet_manually_confirmed':True}}
 print(json.dumps(packet,ensure_ascii=False));print('BEGIN_WHOLE_TEXT');print(s);print('END_WHOLE_TEXT')
 with (D/'emitted-coverage.jsonl').open('a') as f:f.write(json.dumps(packet,ensure_ascii=False)+'\n')
