"""Check actual worker argv against real retention and restart contracts."""
import ast,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from cloud_training.nano_retention import _prefix
from cloud_training.nano_qualification_schedule import restart_branches,validate_restart_branches
P=Path(__file__).parent
class Captured(Exception):pass
def capture(argv,*args):calls.append(argv);raise Captured()
def check(path):
 tree=ast.parse(path.read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sft')
 scope={'sys':sys,'restart_branches':restart_branches,'ROOT':Path('/opt/english-repair'),'BASE':Path('/opt/english-repair/base'),'PACKET':Path('/opt/english-repair/packet'),'OUT':Path('/opt/english-repair/results'),'REMOTE':'gs://forge-ownbase-a100-20261110/english-a100-v1/check','config':{'base_manifest_sha256':'0'*64,'tokenizer_sha256':'1'*64,'worker_deadline_utc':'2026-11-14T09:42:08Z'},'run':capture}
 exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),scope)
 for branch in restart_branches():
  try:scope['sft'](branch,resume=Path('/restore') if branch=='split_resume' else None)
  except Captured:pass
 return list(calls)
calls=[]
old=check(P.parent/'gpu_qualify.py');reproduced=0
for a in old:
 try:_prefix(a[a.index('--backup-prefix')+1])
 except ValueError:reproduced+=1
assert reproduced==3
calls=[];new=check(P/'gpu_qualify.py');validate_restart_branches(restart_branches())
for a in new:
 _prefix(a[a.index('--backup-prefix')+1]);assert a[a.index('--eval-every-updates')+1]=='1'
assert new[1][new[1].index('--backup-prefix')+1]==new[2][new[2].index('--backup-prefix')+1]
assert '--resume' in new[2] and '--resume' not in new[0] and '--resume' not in new[1]
(P/'wiring-check.json').write_text(json.dumps({'old_failure_reproduced_all_branches':True,'corrected_prefixes_valid':True,'split_campaign_shared':True,'cadence_aligned':True,'argv':new},indent=2)+'\n');print('Worker wiring passed; old failure reproduced')
