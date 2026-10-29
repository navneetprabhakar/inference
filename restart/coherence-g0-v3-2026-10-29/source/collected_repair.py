"""One root-authorized conservative quarantine after collected semantic findings."""
import collections,json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
def read(n):return json.loads((P/n).read_text())
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not (P/'collected-repair-result.json').exists()
 for n,h in read('freeze.json').items():assert sha(P/n)==h
 reviewed=read('semantic-review.json');assert reviewed['major_defects']==6 and reviewed['whole_text_reviewed']==10
 bad=reviewed['reviews'][8]['h'];assert reviewed['reviews'][8]['verdict']=='MAJOR'
 original=read('private/combined-manifest.json');held=[];remaining=[]
 for r in original:
  reason='legacy_everyday_stratum_insufficiently_validated' if r['domain']=='everyday' and r.get('source')!='new_primary' else 'primary_answer_depends_on_missing_concussion_context' if r['h']==bad else None
  if reason:held.append({**r,'hold_reason':reason})
  else:remaining.append(r)
 counts={s:{d:sum(r['tokens'] for r in remaining if r['split']==s and r['domain']==d) for d in ['everyday','procedural','educational']} for s in ['train','development','reserve']}
 supply=sum(counts['train'].values())>=4000000 and all(n>=1000000 for n in counts['train'].values());assert not supply
 policy=dict(authorization='Root /root explicitly collected and authorized this single prelaunch broad repair batch after source and benchmark issues, 2026-10-29.',action='Quarantine entire legacy Pressbooks everyday stratum as inadequately validated after repeated domain/extraction failures, without asserting every record defective. Quarantine fresh primary draw9 whose answer depends on missing concussion context. No relabeling, new acquisition, second repair, or fresh semantic sample.',frozen_sample_retained=True,admitted_tokens=0)
 save('collected-repair-policy.json',policy);save('private/collected-repair-holds.json',held);save('private/repaired-manifest.json',remaining)
 legacytrain=sum(r['tokens'] for r in held if r['hold_reason']=='legacy_everyday_stratum_insufficiently_validated' and r['split']=='train')
 result=dict(status='STOP_DATA_ADMISSION',repair_batches_used=1,supply_pass=False,token_counts=counts,total_training_tokens=sum(counts['train'].values()),new_primary_training_tokens_before_semantic_hold=counts['train']['everyday']+424,new_primary_training_tokens_after_semantic_hold=counts['train']['everyday'],legacy_everyday_training_tokens_quarantined=legacytrain,primary_semantic_hold_tokens=424,held_documents=len(held),holds=dict(collections.Counter(r['hold_reason'] for r in held)),everyday_shortfall=1000000-counts['train']['everyday'],admitted_tokens=0,fresh_recheck_run=False,reason='Remaining everyday training supply below fixed1M floor; quantity gate stops admission before recheck. Other retained records remain candidates, not admitted.')
 save('collected-repair-result.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
