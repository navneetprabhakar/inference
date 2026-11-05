import hashlib,json,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
import mlx.core as mx
import mlx.nn as nn
from mlx.utils import tree_flatten
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from token_weighted_gradients import add_weighted,mean_gradient
import train_eight_hour_token_weighted as trainer

class TinyModel(nn.Module):
    def __init__(self,*_):
        super().__init__();self.embedding=nn.Embedding(4,4);self.linear=nn.Linear(4,4)
    def __call__(self,x):return self.linear(self.embedding(x))

class TokenWeightedTests(unittest.TestCase):
    def setUp(self):
        self.previous=mx.default_device();mx.set_default_device(mx.cpu);self.addCleanup(mx.set_default_device,self.previous)
    def test_final_selection_closes_training_before_model_loading(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);goal=root/'runs/eight-hour-improvement-v1';goal.mkdir(parents=True)
            (goal/'training-closed.json').write_text('{}')
            cfg=root/'config.json';cfg.write_text(json.dumps({'run_dir':'runs/test','deadline_unix':time.time()+60}))
            with patch.object(trainer,'ROOT',root),patch.object(trainer,'Model',side_effect=AssertionError('Model must not load')):
                with self.assertRaisesRegex(RuntimeError,'Training permanently closed'):
                    trainer.main(SimpleNamespace(config=str(cfg),resume=False))
    def test_weighted_microgradients_equal_combined_batch(self):
        mx.random.seed(71);model=nn.Linear(3,2)
        x=mx.array(np.arange(24,dtype=np.float32).reshape(8,3)/10);y=mx.zeros((8,2));mask=mx.array([1.,0.,1.,1.,1.,0.,1.,1.])
        def loss(m,x,y,w):return (((m(x)-y)**2).mean(axis=-1)*w).sum()/w.sum()
        grad=nn.value_and_grad(model,loss);_,a=grad(model,x[:2],y[:2],mask[:2]);_,b=grad(model,x[2:],y[2:],mask[2:]);_,expected=grad(model,x,y,mask)
        actual=mean_gradient(add_weighted(add_weighted(None,a,1),b,5),6)
        for (_,got),(_,want) in zip(tree_flatten(actual),tree_flatten(expected)):
            np.testing.assert_allclose(np.array(got),np.array(want),rtol=1e-5,atol=1e-6)
        self.assertGreater(float(mx.max(mx.abs((a['weight']+b['weight'])/2-expected['weight']))),.01)
    def test_interrupted_accumulation_resumes_without_skipped_training(self):
        self._check_interruption(False)
    def test_full_dialogue_context_counters_and_resume(self):
        self._check_interruption(True)
    def _check_interruption(self,full_context):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);goal=root/'runs/eight-hour-improvement-v1';goal.mkdir(parents=True);base=root/'base';base.mkdir();data=root/'data';data.mkdir()
            mx.random.seed(17);model=TinyModel();mx.eval(model.parameters());model.save_weights(str(base/'model.safetensors'))
            ids=np.array([[0,1,2,3,1]]*8,np.int32);masks=np.array([[0,1,1,0]]*8,np.float32)
            extra={}
            if full_context:
                assistant_mask=np.zeros_like(masks);assistant_mask[::2,1]=1;extra['assistant_mask']=assistant_mask
            np.savez(data/'episodes.npz',ids=ids,mask=masks,length=np.array([5]*8),**extra);(data/'order.json').write_text(json.dumps({'order':list(range(8))}));(data/'records.jsonl').write_text(''.join(json.dumps({'id':str(i),'objective':'causal_lm' if i%2 else 'assistant_only'})+'\n' for i in range(8)))
            files={n:hashlib.sha256((data/n).read_bytes()).hexdigest() for n in ['episodes.npz','order.json','records.jsonl']};(data/'manifest.json').write_text(json.dumps({'files':files,'causal_replay_opt_in':True,'loss_objective':'full_dialogue' if full_context else 'assistant_only'}))
            cfg={'base_checkpoint':'base','data_dir':'data','deadline_unix':time.time()+120,'max_active_seconds':120,'max_nonpadding_input_tokens':100,'learning_rate':1e-3,'batch_size':2,'supervised_tokens_per_update':8,'seed':17,'checkpoint_every_steps':100,'min_free_disk_bytes':1,'max_mlx_allocator_bytes':10**12}
            if full_context:cfg.update(loss_objective='full_dialogue',accumulation_reference='assistant_targets')
            health={'free_disk_bytes':10**12,'mlx_allocator_bytes':0,'mlx_peak_bytes':0,'thermal_state':0,'swap_used_mb':0}
            full=root/'full.json';full.write_text(json.dumps({**cfg,'run_dir':'runs/full'}));interrupted=root/'interrupted.json';interrupted.write_text(json.dumps({**cfg,'run_dir':'runs/interrupted'}))
            original=nn.value_and_grad
            def interrupting(*args,**kwargs):
                fn=original(*args,**kwargs)
                def wrapped(*a,**kw):
                    result=fn(*a,**kw);trainer.STOP=True;return result
                return wrapped
            with patch.object(trainer,'ROOT',root),patch.object(trainer,'Model',TinyModel),patch.object(trainer,'health',return_value=health):
                trainer.STOP=False;trainer.main(SimpleNamespace(config=str(full),resume=False))
                with patch.object(trainer.nn,'value_and_grad',side_effect=interrupting):
                    trainer.STOP=False;trainer.main(SimpleNamespace(config=str(interrupted),resume=False))
                stopped=json.loads((root/'runs/interrupted/training/status.json').read_text())
                self.assertEqual((stopped['cursor'],stopped['steps'],stopped['nonpadding_input_tokens']),(0,0,0));self.assertEqual(stopped['discarded_uncommitted_input_tokens'],8)
                self.assertEqual((stopped['supervised_target_tokens'],stopped['supervised_assistant_tokens'],stopped['causal_replay_target_tokens']),(0,0,0))
                trainer.STOP=False;trainer.main(SimpleNamespace(config=str(interrupted),resume=True))
            states=[json.loads((root/f'runs/{name}/training/status.json').read_text()) for name in ['full','interrupted']]
            self.assertEqual([s['nonpadding_input_tokens'] for s in states],[32,32]);self.assertEqual([s['steps'] for s in states],[1,1] if full_context else [2,2]);self.assertEqual(states[0]['model_sha256'],states[1]['model_sha256'])
            for state in states:
                self.assertEqual((state['supervised_target_tokens'],state['supervised_assistant_tokens'],state['causal_replay_target_tokens']),(16,4,8) if full_context else (16,8,8))
                self.assertEqual(state['dialogue_context_target_tokens'],4 if full_context else 0)
    def tearDown(self):trainer.STOP=False

if __name__=='__main__':unittest.main()
