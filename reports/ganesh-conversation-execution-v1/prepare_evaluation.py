"""One model load per snapshot, preserving both suites and declared96-token budgets."""
import copy,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
paths={'development':ROOT/'reports/ganesh-conversation-pilot-v1/development-suite.json','protected':ROOT/'cloud_training/evaluation/conversation-tools-dev.json'}
combined={'purpose':'development_only_never_train','schema':1,'required_context_tokens':2048,'sessions':[]};mapping={}
for scope,path in paths.items():
 suite=json.loads(path.read_text());sessions=copy.deepcopy(suite['sessions'])
 for session in sessions:
  for turn in session['turns']:
   if 'reply_budget' not in turn:turn['reply_budget']=96
   assert turn['reply_budget']==96
 combined['sessions']+=sessions
 mapping[scope]={'original_suite_sha256':sha(path),'sessions':[s['id'] for s in sessions]}
assert len({s['id'] for s in combined['sessions']})==len(combined['sessions'])
assert sum(len(s['turns']) for s in combined['sessions'])==117
out=P/'combined-development-suite.json'
assert not out.exists();out.write_text(json.dumps(combined,indent=2)+'\n')
(P/'evaluation-composition.json').write_text(json.dumps({'scope':'Exposed development only; not independent release','combined_sha256':sha(out),'sources':mapping,'reply_budget':96,'per_snapshot_timeout_seconds':900,'runner':'cloud_training.nano_fit_probe','reason':'Existing bounded fit probe supports full session evaluation beyond nano_quality CLI600second limit. Combined suite uses one model load; questions/policies/system prompts/turn order unchanged. Only omitted protected default budgets are made explicit96 as predeclared in cost plan.'},indent=2)+'\n')
print('117 turns; all questions/policies/system/ordering preserved; one load per snapshot.')
