"""Persist explicit parent decisions; does not infer semantic correctness."""
import copy,hashlib,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def save(batch,evidence,repairs=None,exclusions=None):
 repairs=repairs or {};exclusions=exclusions or set()
 source=ROOT/f'data/eight-hour-teacher-expansion-v2/batch-{batch:03d}.jsonl'
 out=ROOT/'data/eight-hour-teacher-expansion-reviewed-v2';out.mkdir(exist_ok=True)
 target=out/source.name;review=out/f'batch-{batch:03d}.parent-review.json'
 assert not target.exists() and not review.exists()
 rows=[json.loads(s) for s in source.read_text().splitlines()];assert len(rows)==len(evidence)==25
 kept=[];decisions=[]
 for n,(row,note) in enumerate(zip(rows,evidence),1):
  original=copy.deepcopy(row);decision='exclude' if n in exclusions else 'repair' if n in repairs else 'keep'
  for index,text in repairs.get(n,{}).items():row['messages'][index]['content']=text
  decisions.append({'id':row['id'],'decision':decision,'specific_evidence':note,'original_record':original if decision!='keep' else None})
  if decision!='exclude':
   row['provenance']['parent_review_status']=decision;row['provenance']['parent_review_note']=note;row['provenance']['admission']='PENDING_CONTEXT_LEAKAGE_CORPUS_GATES';kept.append(row)
 target.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in kept))
 review.write_text(json.dumps({'source':str(source.relative_to(ROOT)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'reviewed_file':str(target.relative_to(ROOT)),'reviewed_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'reviewed_unix':time.time(),'reviewer':'parent assistant; not independent human review','admission':'PENDING_CONTEXT_LEAKAGE_AND_CORPUS_GATES','cases':decisions},indent=2)+'\n')
 print(json.dumps({'batch':batch,'keep':sum(c['decision']=='keep' for c in decisions),'repair':len(repairs),'exclude':len(exclusions)}))
