import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def pin(name,data):
 payload=json.dumps(data,indent=2)+'\n';h=hashlib.sha256(payload.encode()).hexdigest();p=P/f'{name}-{h[:16]}.json';p.write_text(payload);return {'path':str(p.relative_to(ROOT)),'sha256':h}
rows=[json.loads(l) for l in (P/'final-accepted.jsonl').read_text().splitlines()];rawdir=ROOT/'runs/ganesh-english-sourcing-v1/scale-1000/root';versions={};inventory=[]
for p in sorted(rawdir.glob('*.raw.json'),key=lambda p:p.stat().st_mtime_ns):
 data=json.loads(p.read_text())
 if 'conversations' not in data:continue
 inventory.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)})
 for c in data['conversations']:
  ms=[{'role':role,'content':t[role]} for t in c['turns'] for role in ('user','assistant')]
  request=p.with_name(p.name.replace('.raw.json','.request.json'));events=p.with_name(p.name.replace('.raw.json','.events.jsonl'))
  versions.setdefault(c['group'],[]).append({'revision':len(versions.get(c['group'],[])),'messages_sha256':digest(ms),'raw_artifact':str(p.relative_to(ROOT)),'raw_sha256':sha(p),'request_receipt':{'path':str(request.relative_to(ROOT)),'sha256':sha(request)},'events_receipt':{'path':str(events.relative_to(ROOT)),'sha256':sha(events)}})
history=[];memory=[]
for row in rows:
 group=row['group'];vv=versions[group];count=len(vv)-1;assert 0<=count<=2
 chosen=next(i for i,x in enumerate(vv) if x['raw_artifact']==row['generation']['raw_artifact']);row['total_generation_revisions']=count
 history.append({'group':group,'messages_sha256':digest(row['messages']),'total_generation_revisions':count,'selected_revision':chosen,'versions':vv})
 raw=ROOT/row['generation']['raw_artifact'];c=next(c for c in json.loads(raw.read_text())['conversations'] if c['group']==group)
 credit=row['memory_probe_credit'];q=row.get('recall_probe') if credit else None;row['recall_probe']=q
 reason=row.get('memory_qualification_reason','Exact generated focused probe passed fresh CLI memory review and full content inspection.' if credit else 'No credited delayed-memory probe in this conversation.')
 refs=list(row['review_receipts'])+[row['full_content_review_receipt']]
 if 'memory_qualification_reason' in row:refs.append({'path':str((P/'parent-memory-qualification.json').relative_to(ROOT)),'sha256':sha(P/'parent-memory-qualification.json')})
 memory.append({'group':group,'messages_sha256':digest(row['messages']),'credit':credit,'recall_probe':q,'original_generated_annotation':c['recall_probe'],'reason':reason,'source_receipts':refs})
href=pin('generation-revision-history',{'schema':1,'generation_artifact_inventory':inventory,'entries':history});mref=pin('final-memory-evidence',{'schema':1,'entries':memory})
for row in rows:row['generation_history_receipt']=href;row['memory_evidence_receipt']=mref
p=P/'final-accepted.jsonl';p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows));manifest=json.loads((P/'final-manifest.json').read_text());manifest.update(payload_sha256=sha(p),generation_history_receipt=href,memory_evidence_receipt=mref);(P/'final-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Bound',len(rows),'rows; credited',sum(r['memory_probe_credit'] for r in rows))
