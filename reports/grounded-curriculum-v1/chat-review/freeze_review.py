"""Extract manually reviewed finite definitions as DATA, never execute builder."""
import ast,collections,hashlib,json,pathlib
HERE=pathlib.Path(__file__).resolve().parent;SOURCE=HERE.parent/'chat'

def value(node,env):
 if isinstance(node,ast.Name):return env[node.id]
 if isinstance(node,ast.Constant):return node.value
 if isinstance(node,(ast.List,ast.Tuple)):return [value(v,env) for v in node.elts]
 if isinstance(node,ast.Dict):return {value(k,env):value(v,env) for k,v in zip(node.keys,node.values)}
 if isinstance(node,ast.BinOp) and isinstance(node.op,ast.Mult):
  left,right=value(node.left,env),value(node.right,env)
  if not isinstance(left,list) or type(right)!=int or not 0<right<4:raise ValueError('unexpected expression')
  return left*right
 raise ValueError('unreviewed executable expression '+ast.dump(node))

def extract():
 surfaces=[];counts=collections.Counter();env={};merges=None;paraphrases=None
 for node in ast.parse((SOURCE/'surfaces.py').read_text()).body:
  if isinstance(node,ast.Assign):
   for target in node.targets:
    if isinstance(target,ast.Name) and target.id in ('G','MERGES','PARAPHRASES'):
     env[target.id]=value(node.value,env)
  if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='add':
   call=node.value;args=[value(a,env) for a in call.args];kwargs={k.arg:value(k.value,env) for k in call.keywords};g,slug,u1,a1,u2,a2=args
   surfaces.append(dict(id=g+'/'+slug,group=g,split='train' if counts[g]<8 else 'validation',turns=[dict(user=u1,assistant=a1),dict(user=u2,assistant=a2)],**kwargs));counts[g]+=1
 merges=env['MERGES'];paraphrases=env['PARAPHRASES']
 for surface in surfaces:
  surface['canonical_family']=next((k for k,m in merges.items() if surface['id'] in m),surface['id'])
  if surface['canonical_family'] in merges:surface['split']='train'
  surface['first_user_forms']=[surface['turns'][0]['user']]+([paraphrases[surface['id']]] if surface['id'] in paraphrases else [])
 programs={};env={}
 for node in ast.parse((SOURCE/'semantics.py').read_text()).body:
  if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='G' for t in node.targets):env['G']=value(node.value,env)
  if isinstance(node,ast.Expr) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id=='a':
   call=node.value;args=[value(a,env) for a in call.args];kw={k.arg:value(k.value,env) for k in call.keywords};g,slug,facts,queries=args[:4]
   programs[g+'/'+slug]=dict(initial_facts=facts,queries=queries,turn_events=args[4] if len(args)>4 and args[4] is not None else [{},{}],formats=kw.get('fmt',args[5] if len(args)>5 else ['sentence','sentence']))
 assert len(surfaces)==len(programs)==66 and len(paraphrases)==42
 assert set(programs)=={s['id'] for s in surfaces}
 groups={s['canonical_family'] for s in surfaces}
 assert len(groups)==49
 for group in groups:
  members=[s for s in surfaces if s['canonical_family']==group]
  assert len({s['split'] for s in members})==1
  assert len({form for s in members for form in s['first_user_forms']})>=2
 return dict(state='reviewed_finite_surfaces_not_candidate_verification',surfaces=surfaces,programs=programs,
             canonical_merges=merges,source_pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (SOURCE/'surfaces.py',SOURCE/'semantics.py')},
             reviewed_original_surfaces=66,reviewed_added_first_user_forms=42,canonical_counts={'train':37,'validation':12},
             limitations='Manual finite-template/program entailment review plus independent instance extraction/execution; not general natural-language entailment or custody.')

if __name__=='__main__':
 out=HERE/'reviewed-registry.json'
 with out.open('x') as f:json.dump(extract(),f,indent=2);f.write('\n')
 print(hashlib.sha256(out.read_bytes()).hexdigest())
