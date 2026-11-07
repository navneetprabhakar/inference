"""Materialize reviewed substantive groups; no automatic semantic labels or splits."""
import os,resource,shutil,signal,time
import argparse,hashlib,json,pathlib,sqlite3,sys
H=pathlib.Path(__file__).resolve().parent;R=H.parents[1];sys.path.insert(0,str(H))
from grouping_draft import propose,fingerprint

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def main(registry,expected,custody,csha):
 start=time.monotonic();os.nice(10);dest=R/'data/everyday-grouped-candidates-v1'
 def deadline(*a):raise TimeoutError('grouping600second bound')
 signal.signal(signal.SIGALRM,deadline);signal.alarm(600)
 def check():
  assert not any(p.exists() for p in (R/'runs/STOP',H/'STOP',dest/'STOP')),'STOP'
  assert time.monotonic()-start<600 and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<512*1024**2,'time/RSS'
  assert shutil.disk_usage(R).free>=20*1024**3,'disk'
  if dest.exists():assert sum(p.stat().st_size for p in dest.iterdir() if p.is_file())<50*1024**2,'output'
 check();D=R/'data/everyday-source-review-v1';receipt=json.loads((D/'receipt.json').read_text());assert receipt['state']=='full_history_review_queue_not_admitted' and receipt['failure'] is None;assert sha(D/'review.sqlite')==receipt['database_sha256']
 registry=pathlib.Path(registry);custody=pathlib.Path(custody);assert sha(registry)==expected and sha(custody)==csha
 review=json.loads(registry.read_text());clearance=json.loads(custody.read_text());assert review['state']=='independently_reviewed_full_history_registry' and review['database_sha256']==receipt['database_sha256'] and review['queue_sha256']==receipt['queue_sha256']
 assert clearance['state']=='screened_not_admitted' and clearance['database_sha256']==receipt['database_sha256'] and clearance['training_admitted'] is False
 reviewed={r['doc_id']:r for r in review['records']};assert len(reviewed)==len(review['records'])==1130;denied=set(clearance['excluded_doc_ids']);assert denied<=reviewed.keys();records=[]
 db=sqlite3.connect(f'file:{D}/review.sqlite?mode=ro',uri=True);db.row_factory=sqlite3.Row
 for row in db.execute('select * from histories order by doc_id'):
  check();r=reviewed[row['doc_id']];assert r['history_sha256']==row['history_sha256'] and r['quality_decision'] in ('retain','review','hold') and r['reason'] and r['task_key'] and r['requested_operation'] and r['fact_schema'] is not None
  messages=json.loads(row['messages_json']);indices=r['substantive_user_turn_indices'];assert indices and len(set(indices))==len(indices) and all(type(i)is int and 0<=i<len(messages) and messages[i]['role']=='user' for i in indices)
  # Entire message content/order retained. Greeting handling belongs to human-reviewed
  # semantic keys, never regex deletion or first-user-family hashing.
  history=[dict(role=m['role'],text=m['content']) for m in messages]
  status=row['status'];assert status in ('old_train','excluded','unknown')
  if r['quality_decision']!='retain' or row['doc_id'] in denied:status='excluded'
  records.append(dict(doc_id=row['doc_id'],status=status,history=history,history_sha256=fingerprint(history),task_key=r['task_key'],semantic_review_sha256=expected,raw_history_sha256=row['history_sha256']))
 db.close();groups=propose(records,salt='everyday-repair-train-only-v1',check=check);assert all(g['proposed_split'] in ('train','quarantine') for g in groups),'no fresh dev exists'
 dest=R/'data/everyday-grouped-candidates-v1';dest.mkdir(exist_ok=False)
 with (dest/'groups.json').open('x') as f:json.dump(groups,f,indent=2)
 selected={did for g in groups if g['proposed_split']=='train' for did in g['doc_ids']};assert all(r['status']=='old_train' for r in records if r['doc_id'] in selected)
 with (dest/'candidates.jsonl').open('x') as f:
  for r in records:
   check()
   if r['doc_id'] in selected:f.write(canon(dict(r,split='train',state='full_history_pending_framing_not_admitted'))+'\n')
 with (dest/'receipt.json').open('x') as f:json.dump(dict(state='grouped_train_candidates_pending_independent_framing',training_admitted=False,database_sha256=receipt['database_sha256'],registry_sha256=expected,custody_sha256=csha,groups_sha256=sha(dest/'groups.json'),candidates_sha256=sha(dest/'candidates.jsonl'),train_histories=len(selected),validation_histories=0,quarantined_histories=1130-len(selected),limitations='No oldTRAIN toDEV, no unknown319 promotion, full histories only. Later whole-history host-policy/framing verification may reject; never shorten to fit.'),f,indent=2)
 check();signal.alarm(0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--registry',required=True);p.add_argument('--registry-sha256',required=True);p.add_argument('--custody',required=True);p.add_argument('--custody-sha256',required=True);a=p.parse_args();main(a.registry,a.registry_sha256,a.custody,a.custody_sha256)
