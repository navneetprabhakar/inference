import ast,json,subprocess,sys,unittest
from pathlib import Path
from cloud_training.nano_fit_readiness import score_fit
class FitScoreTests(unittest.TestCase):
 def test_actual_training_loop_keeps_requested_generation_boundary(self):
  args={'updates':17,'losses':[3.0]*18,'cadence':5,'fit_eval_steps':[16]}
  r=json.loads(subprocess.check_output([sys.executable,'-m','nano_loop_harness',json.dumps(args)],text=True))
  self.assertIn(16,r['observed']);self.assertIn(16,r['checkpoint_steps'])
 def test_milestone_is_pinned_and_survives_local_pruning(self):
  tree=ast.parse(Path('cloud_training/nano_sft.py').read_text())
  fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='checkpoint')
  pins=next(n for n in ast.walk(fn) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='pins' for t in n.targets))
  scope={'step':16,'horizon':96,'best_step':5,'pinned_steps':{0,16,32,64}}
  exec(compile(ast.Module(body=[pins],type_ignores=[]),'actual_pin','exec'),scope);self.assertIn('fit-evaluation',scope['pins'])
  prune=next(n for n in ast.walk(fn) if isinstance(n,ast.If) and 'old.name' in ast.unparse(n.test))
  scope['old']=Path('step-00000016');self.assertFalse(eval(compile(ast.Expression(prune.test),'actual_prune','eval'),scope))
 def fixtures(self):
  suite={'purpose':'training_fit_exposed_never_release','sessions':[{'id':str(i),'turns':[{}, {}, {}]} for i in range(24)]}
  records=[{'session':str(i),'turn':j,'result':{'status':'complete','events':[],'broker_trace':[]}} for i in range(24) for j in range(3)]
  review=[{'session':r['session'],'turn':r['turn'],'pass':True,'reason':'Reviewed semantics'} for r in records]
  return suite,{'status':'fit_checks_complete_requires_review','records':records},review
 def test_full_fit_not_release(self):
  s,r,v=self.fixtures();o=score_fit(s,r,v);self.assertTrue(o['fit_go']);self.assertFalse(o['release_eligible'])
 def test_missing_blocked_or_tool_calls_cannot_be_hidden(self):
  for kind in ('missing','blocked','tool','unreviewed','timeout'):
   with self.subTest(kind=kind):
    s,r,v=self.fixtures()
    if kind=='missing':r['records'].pop()
    if kind=='blocked':r['records'][0]['result']['status']='error'
    if kind=='tool':r['records'][0]['result']['events']=[{'kind':'model_action','parsed':{'kind':'call'}}]
    if kind=='unreviewed':v.pop()
    if kind=='timeout':r['status']='incomplete_timeout'
    o=score_fit(s,r,v);self.assertFalse(o['fit_go']);self.assertEqual(o['expected_turns'],72)
 def test_semantic_miss_allows_only_one_session(self):
  s,r,v=self.fixtures();v[0]['pass']=False;self.assertTrue(score_fit(s,r,v)['fit_go']);v[3]['pass']=False;self.assertFalse(score_fit(s,r,v)['fit_go'])
 def test_duplicate_review_rejected(self):
  s,r,v=self.fixtures();v.append(v[0]);
  with self.assertRaises(ValueError):score_fit(s,r,v)
if __name__=='__main__':unittest.main()
