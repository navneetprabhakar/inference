import json
from pathlib import Path
P=Path(__file__).resolve().parent
S=Path('/Users/navneetprabhakar/.codex/sessions')
ROOT_ID='01a16cc7-a2b6-70b3-ae2d-b523756e4ac2'
BASE_ROOT=86449575
OLD={'/root/g0_training_author':2444225,'/root/g0_final_custodian':5118807,'/root/g0_benchmarks':7332698}
rows=[]
for f in S.rglob('*.jsonl'):
 try:
  with f.open() as h:first=json.loads(next(h))['payload']
 except:continue
 src=first.get('source');role=src.get('subagent',{}).get('thread_spawn',{}).get('agent_path') if isinstance(src,dict) else None
 parent=src.get('subagent',{}).get('thread_spawn',{}).get('parent_thread_id') if isinstance(src,dict) else None
 if first.get('id')!=ROOT_ID and not(parent==ROOT_ID and (role in OLD or role.startswith('/root/g0v3_'))):continue
 last=0
 for line in f.open():
  try:r=json.loads(line)
  except:continue
  q=r.get('payload',{})
  if r.get('type')=='event_msg' and q.get('type')=='token_count' and q.get('info'):last=q['info']['total_token_usage']['total_tokens']
 baseline=BASE_ROOT if first.get('id')==ROOT_ID else OLD.get(role,0)
 rows.append(dict(role=role or '/root',path=str(f),baseline=baseline,total=last,new=max(0,last-baseline)))
used=sum(r['new'] for r in rows)
result=dict(authorized_additional_tokens=4000000,used_observed=used,remaining_observed=4000000-used,prior_G0_tokens_reconciled=27024614,includes_cached_input=True,root_approval_baseline=BASE_ROOT,authorization='User approved additional4M preparation review tokens; no training',rows=rows,warning='Counters can lag active calls; reserve before dispatch. Stop if remaining minus reservation negative.')
(P/'budget-status.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
