"""Durable bounded local candidate production; never admits data or trains weights."""
import argparse,fcntl,json,os,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone


def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--qualification',required=True);p.add_argument('--target-dialogues',type=int,default=10000);p.add_argument('--target-tokens',type=int,default=2000000);p.add_argument('--hours',type=float,default=12);a=p.parse_args()
 if not 1<=a.target_dialogues<=10000 or not 200<=a.target_tokens<=5000000 or not 0<a.hours<=12:raise ValueError('Bounded generation limits required')
 root=Path(a.root).resolve();root.mkdir(exist_ok=True,parents=True);deadline=time.time()+a.hours*3600
 with (root/'.generation.lock').open('a+b') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  state={'status':'awaiting_qualification','model':'gpt-6.1-terra','target_dialogues':a.target_dialogues,'target_assistant_targets':a.target_tokens,'generated_verified_candidates':0,'generated_assistant_targets':0,'training_admitted':False,'deadline_epoch':deadline,'cohorts':[]}
  def save():
   state['updated_utc']=datetime.now(timezone.utc).isoformat();temp=root/'state.partial';temp.write_text(json.dumps(state,indent=2)+'\n');os.replace(temp,root/'state.json')
  save()
  # A root-reviewed qualification receipt is mandatory before unattended scale.
  receipt=Path(a.qualification)
  while not receipt.exists() and time.time()<deadline:time.sleep(min(30,deadline-time.time()))
  if not receipt.exists():state['status']='stopped_no_qualification';save();return 2
  qualification=json.loads(receipt.read_text())
  if qualification.get('allow_candidate_generation') is not True:state['status']='blocked_qualification';save();return 2
  state['qualification']=str(receipt);state['status']='running';save()
  for n in range(220):
   if state['generated_verified_candidates']>=a.target_dialogues and state['generated_assistant_targets']>=a.target_tokens:state['status']='generation_target_reached_semantic_review_pending';save();return 0
   if deadline-time.time()<900:state['status']='stopped_generation_time_limit_partial';save();return 0
   cohort=root/f'cohort-{n:03d}'
   if cohort.exists():raise ValueError('Existing cohort refuses overwrite; reconcile before restart')
   args=[sys.executable,'-u','-m','cloud_training.generate_teacher_context','--output',str(cohort),'--seed',str(70103+n*1301)]
   try:
    with (root/f'cohort-{n:03d}.log').open('x') as log:result=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,timeout=min(2600,deadline-time.time()))
    summary=json.loads((cohort/'progress.json').read_text());counts=sum(b['candidates'] for b in summary['batches']);targets=sum(b['assistant_targets'] for b in summary['batches']);state['cohorts'].append({'number':n,'directory':str(cohort),'status':summary['status'],'candidates':counts,'assistant_targets':targets});state['generated_verified_candidates']+=counts;state['generated_assistant_targets']+=targets
    if result.returncode or summary['status']!='complete_pending_semantic_review':state.update(status='blocked_worker_quota_auth_or_quality',failed_cohort=n);save();return 2
    save()
   except Exception as error:state.update(status='blocked_generation_exception',error=str(error));save();return 2
  state['status']='stopped_cohort_limit_partial';save();return 0

if __name__=='__main__':raise SystemExit(main())
