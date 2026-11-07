"""Synthetic negative controls for independent semantic/framing interpretation."""
from copy import deepcopy
import json
from pathlib import Path
from independent_semantics import fill,interpret,validate_task
from verify import slots_for,framing
from tokenizer import load


def main():
 registry=json.loads(Path(__file__).with_name('reviewed-registry.json').read_text());tok=load();checks=0
 for sid in ('corrections/destination-change','corrections/remove-member','corrections/add-member','corrections/swap-roles','corrections/selective-update','clarification/missing-destination','facts/membership','facts/route-order','recall/noted-limitation'):
  surface=next(s for s in registry['surfaces'] if s['id']==sid);slots=slots_for(surface,0);program=fill(registry['programs'][sid],slots)
  history=[]
  for turn in surface['turns']:history.extend([dict(role='user',text=fill(turn['user'],slots)),dict(role='assistant',text=fill(turn['assistant'],slots))])
  task=dict(state=slots,split=surface['split'],first_user_form=0,history=history,semantic_state=dict(program=program,snapshots=interpret(program)))
  assert validate_task(task,surface,registry['programs'][sid]);assert framing(tok,history)['target_tokens']>0
  bad=deepcopy(task);bad['history'][-1]['text']='Unsupported replacement.'
  try:validate_task(bad,surface,registry['programs'][sid])
  except ValueError:checks+=1
  else:raise AssertionError('renderer mutation accepted')
  bad=deepcopy(task);bad['semantic_state']['snapshots'][-1]['queried_values']={}
  try:validate_task(bad,surface,registry['programs'][sid])
  except ValueError:checks+=1
  else:raise AssertionError('semantic mutation accepted')
  bad=deepcopy(task);bad['state']['other']=bad['state']['person']
  try:validate_task(bad,surface,registry['programs'][sid])
  except ValueError:checks+=1
  else:raise AssertionError('entity collision accepted')
 for event in ({'set':{'missing':'x'}},{'append':{'x':'a'}},{'remove':{'list':'missing'}},{'swap':['x','x']}):
  program=dict(initial_facts={'x':'a','list':['b']},turn_events=[{},event],queries=[['x'],['x']],formats=['sentence']*2)
  try:interpret(program)
  except ValueError:checks+=1
  else:raise AssertionError('invalid event accepted')
 try:framing(tok,[dict(role='user',text='word '*1500),dict(role='assistant',text='Answer.'),dict(role='user',text='Again'),dict(role='assistant',text='Answer.')])
 except ValueError:checks+=1
 else:raise AssertionError('oversized history accepted')
 print(json.dumps(dict(state='PASS_synthetic_verifier_controls',refusals=checks,model_or_gpu=False,private_cases_read=False)))
if __name__=='__main__':main()
