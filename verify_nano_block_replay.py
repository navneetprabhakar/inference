"""Real frozen block packing and CPU optimizer recovery; not CUDA qualification."""
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
import torch
from cloud_training.nano_block_replay import BlockReplay
from cloud_training.nano_sft import JsonlConversations,backward_weighted,evaluate_fixed,sft_schedule
from cloud_training.nano_checkpoint import save_bundle,load_bundle,capture_rng,restore_rng_state
from cloud_training.nano_benchmark import digest_state
from cloud_training.nano_quality_gate import ValidationGuard,release_decision
from verify_nano_sft import TinyLM,FakeDataset
ROOT=Path(__file__).resolve().parent
P=ROOT/'reports/ganesh-conversation-pilot-v1'
sys.path.insert(0,str(ROOT/'runs/nanochat-source'))
from nanochat.tokenizer import RustBPETokenizer
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

class BlockTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  torch.set_num_threads(1)
  cls.tok=RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
  cls.data={arm:JsonlConversations(P/f,cls.tok,sha(P/f)) for arm,f in [('broad','train.jsonl'),('control','control.jsonl')]}
 def pack(self,arm='broad'):return BlockReplay(self.data[arm],P/'exposure-plan.json',arm)
 def test_all_blocks_match_frozen_tensors_and_exposures(self):
  proof=json.loads((P/'block-checks.json').read_text())
  for arm in self.data:
   pack=self.pack(arm);counts=[]
   for record in proof['records'][arm]:
    batches,count=pack.next_update();rows=[(x[0],y[0]) for x,y in batches]
    self.assertEqual(sha_list(rows),record['tensor_lists_sha256']);counts.append(count)
   self.assertEqual(sum(counts),9144);self.assertEqual(pack.next_update(),([],0))
 def test_wrong_arm_plan_dataset_and_cursor_rejected(self):
  p=self.pack();p.next_update();s=p.state_dict()
  for key,value in [('arm','control'),('block_identity','a'*64),('next_block',True),('next_block',41),('consumed',999),('rows',8)]:
   with self.assertRaises(ValueError):self.pack().load_state_dict(dict(s,**{key:value}))
  with self.assertRaises(ValueError):self.pack('control').load_state_dict(s)
  with tempfile.TemporaryDirectory() as d:
   f=Path(d)/'plan';f.write_text((P/'exposure-plan.json').read_text()+' ')
   with self.assertRaises(ValueError):BlockReplay(self.data['broad'],f,'broad')
 def mapped(self,batches):
  return [([[v%8 for v in row] for row in x],[[v%8 if v!=-1 else -1 for v in row] for row in y]) for x,y in batches]
 def test_real_checkpoint_optimizer_restart_and_interrupted_accumulation(self):
  p=self.pack();torch.manual_seed(103);m=TinyLM();opt=torch.optim.AdamW(m.parameters(),lr=.01)
  guard=ValidationGuard({'relative_tolerance':.05,'patience':2});guard.observe(0,3.)
  def update(step):
   batches,n=p.next_update();lr,_=sft_schedule(step/40,step);opt.param_groups[0]['lr']=.01*lr
   loss=backward_weighted(m,self.mapped(batches),n,device='cpu');opt.step();opt.zero_grad(set_to_none=True);guard.observe(step+1,3.2)
   return loss
  update(0)
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'checkpoint';identity={'phase':'block_cpu_test','arm':'broad','plan':p.sha}
   save_bundle(path,model=m,optimizer=opt,metadata={'step':1,'identity':identity,'loop':{'guard':guard.state}},data_state={'exact':True,'next_batch':1,'packing':p.state_dict()})
   expected=update(1);state=digest_state(m,opt);end=p.state_dict();guard_end=dict(guard.state)
   restored=load_bundle(path,model=m,optimizer=opt,expected_identity=identity);p.load_state_dict(restored['data_state']['packing'])
   guard=ValidationGuard(guard.policy,restored['metadata']['loop']['guard'])
   self.assertEqual(update(1),expected);self.assertEqual(state,digest_state(m,opt));self.assertEqual(end,p.state_dict());self.assertEqual(guard.state,guard_end);self.assertTrue(guard.state['stopped'])
   restored=load_bundle(path,model=m,optimizer=opt,expected_identity=identity);p.load_state_dict(restored['data_state']['packing'])
   before=digest_state(m,opt);cursor=p.state_dict();rng=capture_rng();batches,n=p.next_update();calls=[]
   def stop():calls.append(1);return len(calls)==2
   with self.assertRaises(InterruptedError):backward_weighted(m,self.mapped(batches),n,device='cpu',stop_check=stop)
   m.zero_grad(set_to_none=True);p.load_state_dict(cursor);restore_rng_state(rng)
   self.assertEqual(before,digest_state(m,opt));self.assertEqual(cursor,p.state_dict())
 def test_end_improvement_cannot_hide_content_regression(self):
  data=FakeDataset([3]);data.context=2048
  data.tokenizer=type('Tok',(),{'get_bos_token_id':lambda self:0,'encode_special':lambda self,s:7})()
  data.get=lambda i:([0,1,7],[0,1,1])
  class Loss(torch.nn.Module):
   def __init__(self,c,e):super().__init__();self.c=c;self.e=e
   def forward(self,x,y,loss_reduction):return (y.eq(1).sum()*self.c+y.eq(7).sum()*self.e).double()
  a=evaluate_fixed(Loss(2,20),data,rows=128,microbatch=1,device='cpu',separate_end=True)
  b=evaluate_fixed(Loss(4,1),data,rows=128,microbatch=1,device='cpu',separate_end=True)
  self.assertLess(b['cross_entropy_nats'],a['cross_entropy_nats']);self.assertGreater(b['content_cross_entropy_nats'],a['content_cross_entropy_nats'])
  g=ValidationGuard({'relative_tolerance':.05,'patience':2});g.observe(0,a['content_cross_entropy_nats']);g.observe(5,b['content_cross_entropy_nats'])
  g=ValidationGuard(g.policy,g.state);self.assertTrue(g.observe(10,b['content_cross_entropy_nats']))
 def test_pilot_never_release_eligible(self):
  for contract,identity in [({'objective':'controlled_conversation_pilot'},{}),({}, {'controlled_pilot_only':True})]:
   result=release_decision(raw={},raw_sha256='',suite={},suite_sha256='',review={},contract=contract,checkpoint_identity=identity)
   self.assertFalse(result['quality_accepted'])

def sha_list(value):return hashlib.sha256(json.dumps(value).encode()).hexdigest()
if __name__=='__main__':unittest.main()
