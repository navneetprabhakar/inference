"""Prelaunch correctness checks on CPU/toy arrays; no student forwards."""
import io,sys,copy,time,unittest,tempfile,hashlib,random
import numpy as np
from common import *
from scorer import *
from state_checks import exact
from samplers import BroadStream,mix
from evaluate import fixtures
sys.path.insert(0,str(UPSTREAM))
from tokenizer import Tokenizer

class Tests(unittest.TestCase):
 def test_suffix_shift(self):
  p=np.array([[.9,.05,.05],[.1,.2,.7],[.1,.8,.1]])
  self.assertAlmostEqual(suffix_score(np.log(p),[0,1,2,1],2),math.log(.7)+math.log(.8))
  p[0]=[.01,.01,.98];self.assertAlmostEqual(suffix_score(np.log(p),[0,1,2,1],2),math.log(.7)+math.log(.8))
 def test_causal(self):
  mask=causal_mask(4);weights=np.exp(mask);weights/=weights.sum(axis=-1,keepdims=True)
  np.testing.assert_array_equal((weights@np.array([2,4,6,8]))[:3],(weights@np.array([2,4,6,800]))[:3]);assert np.isneginf(mask[0,1:]).all()
 def test_clocks_and_caps(self):
  for phase,cap in [('R0',4500),('D0',9000),('R1',7200),('R2',9000)]:
   c=dict(schema_version=1,phase=phase,started_epoch=10,deadline_epoch=10+cap,wall_seconds_cap=cap,shutdown_reserve_seconds=300);check_clock(c,phase,now=11)
   with self.assertRaises(TimeoutError):check_clock(c,phase,now=10+cap-300)
   with self.assertRaises(AssertionError):check_clock(c,'bad',now=11)
  import common
  previous=common.ROOT
  with tempfile.TemporaryDirectory() as d:
   common.ROOT=Path(d);(common.ROOT/'R0').mkdir();t=time.time();save(common.ROOT/'R0/clock.json',dict(schema_version=1,phase='R0',started_epoch=t,deadline_epoch=t+4500,wall_seconds_cap=4500,shutdown_reserve_seconds=300))
   try:
    m=Meter('R0');m.reserve(4000000,'toy-accounting')
    with self.assertRaises(RuntimeError):m.reserve(1,'must-refuse')
    assert m.total()==4000000;m.db.close()
   finally:common.ROOT=previous
 def test_mix_cursor(self):
  native=np.arange(512*257,dtype=np.int32).reshape(512,257);blocks=np.arange(1000*257,dtype=np.int32).reshape(1000,257)
  b=BroadStream(blocks);b.batch(400);state=b.state();c=BroadStream(blocks,state)
  np.testing.assert_array_equal(b.batch(256),c.batch(256));exact(b.state(),c.state())
  a,ha=mix(native);bb,hb=mix(native,b.batch(256));assert ha==hb and a.shape==bb.shape==(512,257)
  for i in range(0,512,32):np.testing.assert_array_equal(a[i:i+16],bb[i:i+16])
  z=BroadStream(blocks[:2]);z.batch(6)
  with self.assertRaises(AssertionError):z.batch(1)
  with self.assertRaises(AssertionError):BroadStream(blocks,{'schema_version':7,'n_blocks':1000})
 def test_actual_spans(self):
  tok=Tokenizer(str(UPSTREAM/'tokenizer.model'));rows=fixtures();old=0
  for c in rows:
   lens=[]
   for option in c['options']:
    ids,n=continuation(tok,c['prefix'],option);assert n>0 and n<len(ids)<=256;lens.append(len(ids)-n)
    if c['suite'].startswith('legacy') and c['variant']=='intact':old+=1
   assert len(set(lens))==1
  assert old==600
  # SentencePiece intentionally strips one leading space; exact supplied probe roundtrips verified.
  for bank in ['calibration','development']:
   for c in read(ROOT/'cases.json')[bank]:assert tok.decode(tok.encode(c['prefix'],bos=False,eos=False))==c['prefix']
  assert (tok.bos_id,tok.eos_id)==(1,2)
 def test_exact_full_reload_toy(self):
  import torch
  a={'tensor':torch.tensor([1.,2.]),'array':np.array([7],np.uint32),'nested':{'rng':random.Random(42).getstate(),'cursor':4,'LR':.00005}}
  f=io.BytesIO();torch.save(a,f);f.seek(0);b=torch.load(f,weights_only=False);exact(a,b)
  b['nested']['cursor']=5
  with self.assertRaises(AssertionError):exact(a,b)

def main():
 check('R0');result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));assert result.wasSuccessful()
 import torch
 receipts=[]
 for c in read(ROOT/'plan.json')['source_candidates']:
  path=PROJECT/c['path'];assert sha(path)==c['sha256'];s=torch.load(path,map_location='cpu',weights_only=False)
  assert s['optimizer_step']==c['step'] and s['completed_targets']==c['retained_targets']
  assert s['data_cursor']['completed_microbatches']*16==c['step']*512 and s['data_cursor']['upstream_seed']==42
  assert sum(v.numel() for k,v in s['model'].items() if k!='output.weight')==15191712
  assert torch.equal(s['model']['tok_embeddings.weight'],s['model']['output.weight'])
  assert 'mlx_rng_state' in s and s['mlx_rng_state'][0].shape==(2,)
  for v in s['model'].values():assert v.dtype==torch.float32 and torch.isfinite(v).all()
  for v in s['optimizer']['state'].values():
   assert int(v['step'])==c['step']
   for k in ['exp_avg','exp_avg_sq']:assert v[k].dtype==torch.float32 and torch.isfinite(v[k]).all()
  # Exact full source serialization/reload; temporary in memory, source immutable.
  f=io.BytesIO();torch.save(s,f);f.seek(0);loaded=torch.load(f,map_location='cpu',weights_only=False);exact(s,loaded)
  receipts.append(dict(id=c['id'],sha256=c['sha256'],exact_CPU_fullstate_reload=True,source_rng_cursor_valid=True));del s,loaded,f
 for name,digest in read(ROOT/'reference-snapshot.json')['files'].items():assert sha(PROJECT/name)==digest
 assert sha(OLD/'validation.npy')=='1446abdadd9fab46ef5eb61932f268466bb69dddec729bc5ed322e649b7d9249'
 assert sha(UPSTREAM/'tokenizer.model')=='9e556afd44213b6bd1be2b850ebbbd98f5481437a8021afaf58ee7fb1818d347'
 assignments={}
 sources=[c['id'] for c in read(ROOT/'plan.json')['source_candidates']]
 cal=read(ROOT/'cases.json')['calibration'];dev=read(ROOT/'cases.json')['development']
 assignments['R0']=[[dict(group=s,path=f'{s}/stories.json',id=c['id']) for c in cal[i:i+4] for s in sources] for i in range(0,20,4)]
 assignments['R1']=[[dict(group=s,path=f'{s}/stories.json',id=c['id']) for c in dev[i:i+4] for s in ['source','A','B']] for i in range(0,24,4)]
 # Three dev pairs and three sealed pairs per R2 packet, all future identifiers fixed now.
 sealed_ids=[f'seal-n{i}' for i in range(12)]+[f'seal-b{i}' for i in range(12)]
 assignments['R2']=[[dict(group=f'{s}-{bank}',path=f'{s}/{bank}-stories.json',id=id_) for bank,ids in [('development',[c['id'] for c in dev]),('sealed',sealed_ids)] for id_ in ids[i:i+3] for s in ['R1B','R2']] for i in range(0,24,3)]
 assert all(len(p)==12 for ps in assignments.values() for p in ps)
 save(ROOT/'packet-assignments.json',assignments)
 save(ROOT/'R0/cpu-preflight.json',dict(status='PASS',tests=result.testsRun,source_receipts=receipts,student_forwards=0,updates=0,teacher_requests=0,epoch=time.time()))
 save(ROOT/'english-gap-matrix.json',dict(research_only=True,rows=[{'area':'tokenizer','status':'roundtrip/control IDs checked; broader corpus coverage unmeasured'},{'area':'heldout coverage','status':'fresh research bank; formal 200-case requirement not met'},{'area':'independent human custody','status':'not satisfied; primary assistant is not a human adjudicator'},{'area':'formal computational gate','status':'not rerun or certified by CPU toy checks'}]))
 print('PASS: CPU preflight; no student forwards/updates/teacher requests')
if __name__=='__main__':main()
