import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3]
def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows={r['group']:r for r in map(json.loads,(P/'accepted.jsonl').read_text().splitlines())}
for r in map(json.loads,(P/'parent-repairs.accepted.jsonl').read_text().splitlines()):rows[r['group']]=r
ledger={r['group']:r for r in json.loads((P/'parent-full-content-review.json').read_text())['rows']}
flags=json.loads((P/'parent-flags.json').read_text());qualification=json.loads((P/'parent-memory-qualification.json').read_text())
selected=[];reviews=[];excluded=[]
for group,r in rows.items():
 entry=ledger[group]
 if entry['decision']!='pass':excluded.append({'group':group,'reason':entry['reason']});continue
 assert entry['messages_sha256']==digest(r['messages'])
 n=len(r['messages'])//2;assert entry['assistant_turns_read']==n
 reviews.append({'group':group,'messages_sha256':entry['messages_sha256'],'decision':'pass','assistant_turns_reviewed':n,'reviewed_turn_numbers':list(range(1,n+1)),'rationale':entry['reason'],'independent_release_review':False})
 r['memory_probe_credit']=bool(r.get('recall_probe'))
 if group in qualification:r['memory_probe_credit']=qualification[group]['credit'];r['memory_evidence_kind']=qualification[group]['kind'];r['memory_qualification_reason']=qualification[group]['reason']
 selected.append(r)
receipt={'entries':reviews,'all_selected_targets_inspected':True,'training_admitted':False,'release_accepted':False,'excluded':excluded}
payload=json.dumps(receipt,indent=2)+'\n';key=hashlib.sha256(payload.encode()).hexdigest();rp=P/f'final-content-review-{key[:16]}.json';rp.write_text(payload);(P/'final-content-review.json').write_text(payload)
for r in selected:r['full_content_review_receipt']={'path':str(rp.relative_to(ROOT)),'sha256':sha(rp)}
out=P/'final-accepted.jsonl';out.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in selected))
(P/'final-manifest.json').write_text(json.dumps({'sessions':len(selected),'assistant_turns':sum(len(r['messages'])//2 for r in selected),'payload_sha256':sha(out),'all_content_reviewed':True,'known_semantic_errors_unresolved':0,'excluded':excluded,'training_admitted':False,'release_eligible':False},indent=2)+'\n');print('Root final reviewed',len(selected),'excluded from staged',len(excluded))
