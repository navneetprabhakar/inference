"""Bounded visible whole-review chunks; coverage acknowledged only after inspection."""
from pathlib import Path
import json,hashlib,argparse
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
ASSIGN=json.loads((HERE/'assignment.json').read_text());OUT=Path(json.loads((BASE/'pressbooks-development30-capture-preparation-v1/profile.json').read_text())['output'])
p=argparse.ArgumentParser();p.add_argument('action',choices=['plan','read','ack']);p.add_argument('--source',type=int);p.add_argument('--ordinal',type=int);p.add_argument('--chunks',type=int,nargs='*');a=p.parse_args()
items=[]
for item in ASSIGN['units']:
 r=item['source_binding'];path=OUT/f"source-{r['source_id']}-row-{r['ordinal']:06d}.text.utf8";raw=path.read_bytes();assert len(raw)==r['text_UTF8_bytes'] and hashlib.sha256(raw).hexdigest()==r['text_SHA256'];s=raw.decode('utf8');offset=0;chunks=[]
 for charpos in range(0,len(s),10000):
  text=s[charpos:charpos+10000];b=text.encode();chunks.append({'chunk':len(chunks)+1,'byte_start':offset,'byte_end':offset+len(b),'SHA256':hashlib.sha256(b).hexdigest(),'characters':len(text)});offset+=len(b)
 assert offset==len(raw);items.append({'source_id':r['source_id'],'ordinal':r['ordinal'],'source_SHA256':r['text_SHA256'],'source_bytes':len(raw),'chunks':chunks})
if a.action=='plan':
 (HERE/'chunk-plan.json').write_text(json.dumps(items,indent=2)+'\n');print(json.dumps([{k:(len(v) if k=='chunks' else v) for k,v in item.items()} for item in items],indent=2))
else:
 item=next(x for x in items if x['source_id']==a.source and x['ordinal']==a.ordinal);chosen=[x for x in item['chunks'] if x['chunk'] in a.chunks];assert len(chosen)==len(set(a.chunks)) and len(chosen)<=3
 if a.action=='read':
  raw=(OUT/f'source-{a.source}-row-{a.ordinal:06d}.text.utf8').read_bytes()
  for c in chosen:
   print('BEGIN',json.dumps({'source':a.source,'ordinal':a.ordinal,**c}));print(raw[c['byte_start']:c['byte_end']].decode('utf8'));print('END_CHUNK',c['chunk'])
 else:
  ledger=HERE/'coverage.json';d=json.loads(ledger.read_text()) if ledger.exists() else []
  for c in chosen:
   rec={'source_id':a.source,'ordinal':a.ordinal,'source_SHA256':item['source_SHA256'],**c,'visible_output_inspected_without_truncation':True}
   if rec not in d:d.append(rec)
  ledger.write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'acknowledged':a.chunks,'source':a.source,'ordinal':a.ordinal,'total_acknowledged_chunks':len(d)}))
