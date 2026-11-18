"""Complete raw generation in one bounded process; derive both ungraded source views."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from cloud_training.nano_fit_probe import validate_inputs
from cloud_training.nano_quality import supervise,output_guard,atomic_report
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser()
 for n in ('checkpoint','output','repo','tokenizer','tokenizer-sha'):p.add_argument('--'+n,required=True)
 p.add_argument('--seconds',type=int,default=900);p.add_argument('--device',choices=['cuda','mps','cpu'],default='cuda');a=p.parse_args()
 if not 30<=a.seconds<=900:raise ValueError('Snapshot must be bounded30..900seconds')
 P=Path(__file__).resolve().parent;ROOT=P.parents[1];suite=P/'combined-development-suite.json';composition=json.loads((P/'evaluation-composition.json').read_text());out=Path(a.output).resolve()
 if sha(suite)!=composition['combined_sha256']:raise ValueError('Changed combined suite')
 for scope,path in [('development',ROOT/'reports/ganesh-conversation-pilot-v1/development-suite.json'),('protected',ROOT/'cloud_training/evaluation/conversation-tools-dev.json')]:
  original=json.loads(path.read_text());combined=json.loads(suite.read_text());selected=[s for s in combined['sessions'] if s['id'] in composition['sources'][scope]['sessions']]
  if sha(path)!=composition['sources'][scope]['original_suite_sha256']:raise ValueError('Changed source suite')
  import copy
  expected=copy.deepcopy(original['sessions'])
  for session in expected:
   for turn in session['turns']:turn.setdefault('reply_budget',96)
  if selected!=expected:raise ValueError('Derived evaluation changed prompts/policies/budgets')
 output_guard(Path(a.checkpoint),out)
 if out.exists():raise FileExistsError('No overwrite or retry of snapshot')
 out.mkdir(parents=True)
 rawpath=out/'combined.json';checkpoint_sha=sha(Path(a.checkpoint)/'manifest.json')
 validate_inputs(a.checkpoint,checkpoint_sha,suite,sha(suite),'development')
 command=[sys.executable,'-m','cloud_training.nano_fit_probe','--checkpoint',a.checkpoint,'--checkpoint-sha',checkpoint_sha,'--suite',str(suite),'--suite-sha',sha(suite),'--repo',a.repo,'--tokenizer',a.tokenizer,'--tokenizer-sha',a.tokenizer_sha,'--output',str(rawpath),'--scope','development','--device',a.device,'--timeout-seconds',str(a.seconds),'--allow-base']
 rc=subprocess.run(command,check=False).returncode
 raw=json.loads(rawpath.read_text())
 for scope,source in composition['sources'].items():
  records=[r for r in raw.get('records',[]) if r['session'] in source['sessions']]
  value={k:v for k,v in raw.items() if k not in ('records','automated_passed','automated_total','manual_review_turns')}
  value.update(records=records,suite_sha256=source['original_suite_sha256'],derived_from_combined_sha256=sha(rawpath),combined_suite_sha256=composition['combined_sha256'],evaluation_composition_sha256=sha(P/'evaluation-composition.json'),scope=scope,reply_budget=96)
  atomic_report(out/(scope+'.json'),value)
 return rc
if __name__=='__main__':raise SystemExit(main())
