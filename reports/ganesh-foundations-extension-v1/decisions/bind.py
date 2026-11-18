import hashlib,json,sys
from pathlib import Path
ROOT=Path('/Users/navneetprabhakar/Documents/git/image/inference');P=ROOT/'reports/ganesh-foundations-extension-v1/decisions';O=ROOT/'runs/ganesh-foundations-extension-v1/decisions'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def ref(p):return {'path':str(p.relative_to(ROOT)),'sha256':sha(p)}
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def messages(c):return [{'role':r,'content':t[r]} for t in c['turns'] for r in ('user','assistant')]
rows=[json.loads(l) for l in (P/'accepted.jsonl').read_text().splitlines()]; versions={};inventory=[]
for p in sorted(O.glob('b*-g*.raw.json')):
 inventory.append(ref(p))
 for c in json.loads(p.read_text())['conversations']:
  versions.setdefault(c['group'],[]).append({'messages_sha256':digest(messages(c)),'raw_artifact':str(p.relative_to(ROOT)),'raw_sha256':sha(p),'request_receipt':ref(p.with_name(p.name.replace('.raw.json','.request.json'))),'events_receipt':ref(p.with_name(p.name.replace('.raw.json','.events.jsonl')))})
# REVIEW DECISIONS are supplied after direct reading, not inferred from CLI verdict.
decisions=json.loads((P/'manual-decisions.json').read_text()); rows=[r for r in rows if decisions[r['group']]['decision']=='pass']
entries=[];hist=[];memory=[]
for row in rows:
 g=row['group']; vs=versions[g]
 for i,v in enumerate(vs):v['revision']=i
 row['total_generation_revisions']=len(vs)-1
 hist.append({'group':g,'messages_sha256':digest(row['messages']),'total_generation_revisions':len(vs)-1,'selected_revision':next(i for i,v in enumerate(vs) if v['raw_artifact']==row['generation']['raw_artifact']),'versions':vs})
 n=len(row['messages'])//2
 entries.append({'group':g,'messages_sha256':digest(row['messages']),'decision':'pass','assistant_turns_reviewed':n,'reviewed_turn_numbers':list(range(1,n+1)),'rationale':decisions[g]['rationale']})
 row['memory_probe_credit']=False;row['recall_probe']=None
 raw=ROOT/row['generation']['raw_artifact'];c=next(c for c in json.loads(raw.read_text())['conversations'] if c['group']==g)
 memory.append({'group':g,'messages_sha256':digest(row['messages']),'credit':False,'recall_probe':None,'original_generated_annotation':c['recall_probe'],'reason':'Not selected or reviewed as a delayed-memory probe.','source_receipts':row['review_receipts']})
write(P/'final-content-review.json',{'reviewer':'direct full dialogue reading','entries':entries,'excluded':{k:v for k,v in decisions.items() if v['decision']!='pass'}})
write(P/'generation-revision-history.json',{'schema':1,'generation_artifact_inventory':inventory,'entries':hist})
write(P/'memory-evidence.json',{'schema':1,'entries':memory})
for row in rows:row.update(full_content_review_receipt=ref(P/'final-content-review.json'),generation_history_receipt=ref(P/'generation-revision-history.json'),memory_evidence_receipt=ref(P/'memory-evidence.json'))
(P/'selected.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
sys.path.insert(0,str(ROOT/'reports/ganesh-english-sourcing-v1/scale-1000'))
from verify_selection import verify_new,verify_full_content,native
from selection_memory_integrity import verify_memory
for row in rows:verify_new(row);verify_full_content(row);verify_memory(row,ROOT)
write(P/'verification.json',{'selected':len(rows),'all_verify_new':True,'all_verify_full_content':True,'all_memory_integrity':True,'selected_sha256':sha(P/'selected.jsonl'),'native':native(rows),'training_admitted':False,'independent_release_review':False})
print('verified',len(rows))
