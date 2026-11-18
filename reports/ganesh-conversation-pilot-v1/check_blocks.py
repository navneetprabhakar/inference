"""Pure local block-packing proof; does NOT qualify optimizer/GPU/controller resume."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'runs/nanochat-source')]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_sft import JsonlConversations,BestFitConversations,validate_parent_chain
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
T='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'
tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
plan=json.loads((P/'exposure-plan.json').read_text());ph=sha(P/'exposure-plan.json');ds=JsonlConversations(P/'train.jsonl',tok,sha(P/'train.jsonl'));ids={json.loads(l)['id']:i for i,l in enumerate((P/'train.jsonl').read_text().splitlines())}
class View:
 def __init__(self,order):
  self.order=order;self.lengths=[ds.lengths[i] for i in order];self.context=2048;self.tokenizer=tok;self.sha=hashlib.sha256(json.dumps(order).encode()).hexdigest()
 def __len__(self):return len(self.order)
 def get(self,i):return ds.get(self.order[i])
class Blocks:
 def __init__(self,arm):self.arm=arm;self.next_block=0
 def state(self):return {'arm':self.arm,'plan':ph,'dataset':ds.sha,'next_block':self.next_block}
 def restore(self,s):
  if s.get('arm')!=self.arm or s.get('plan')!=ph or s.get('dataset')!=ds.sha or type(s.get('next_block'))!=int or not 0<=s['next_block']<=40:raise ValueError('Changed block identity/cursor')
  self.next_block=s['next_block']
 def step(self):
  block=plan['blocks'][self.next_block];v=View([ids[i] for i in block[self.arm]]);pack=BestFitConversations(v,buffer_size=1);rows=[]
  while True:
   try:rows.append(pack.next_row())
   except StopIteration:break
  active=len(rows);assert active<=4
  while len(rows)<4:rows.append(([tok.get_bos_token_id()]*2048,[-1]*2048))
  actual=sum(y!=-1 for x,ys in rows for y in ys);assert actual==block['assistant_targets_each_arm'];assert all(len(x)==len(y)==2048 for x,y in rows)
  self.next_block+=1
  return {'update':self.next_block,'actual_targets':actual,'active_rows':active,'total_rows':4,'tensor_lists_sha256':hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
results={}
for arm in ['broad','control']:
 a=Blocks(arm);continuous=[a.step() for _ in range(40)];b=Blocks(arm);first=b.step();s=b.state();c=Blocks(arm);c.restore(s);resumed=[first]+[c.step() for _ in range(39)];assert continuous==resumed
 for key,bad in [('plan','0'*64),('dataset','0'*64),('arm','wrong'),('next_block',41),('next_block',True)]:
  try:Blocks(arm).restore(dict(s,**{key:bad}))
  except ValueError:pass
  else:raise AssertionError('Unsafe restore accepted')
 assert sum(x['actual_targets'] for x in continuous)==9144
 results[arm]=continuous
validate_parent_chain(ROOT/'runs/ganesh-a100-cap40-v1/local-fit/step-00000030',plan['parent_manifest_sha256'],T,stage='targeted',ancestors=[ROOT/'runs/local-readiness-v1/base10b'])
(P/'block-checks.json').write_text(json.dumps({'passed':True,'scope':'Pure schedule packing/masking/cursor simulation and checkpoint ancestry integrity, NOT optimizer or CUDA restart','updates_per_arm':40,'targets_per_arm':9144,'positions_per_update':8192,'padding':'All additional row labels are -1; no supervised padding or truncated assistant ends. Required future runner must skip or safely handle all-ignore microbatches using global target denominator.','tests':['full plan packing','exact targets each update','continuous versus1+restore+39 row equality','wrong arm/hash/cursor rejected','own Fit30 to random-base ancestry verified'],'records':results},indent=2)+'\n');print('PASS: exact40 blocks/9144 targets each; 8192 positions/update; plan-cursor restart; local parent integrity. GPU/runner still unqualified.')
