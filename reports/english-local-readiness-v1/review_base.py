"""Record Codex's full raw-output review of the fixed base fit baseline."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from cloud_training.nano_fit_readiness import score_fit
P=Path(__file__).parent;path=P/'base10b-fit.json';report=json.loads(path.read_text());suite=json.loads((P/'fit-suite.json').read_text())
notes=['Does not deliver the apology; repeats prompt and unrelated offer.','Repeats inability to understand instead of a sign.','Invents unrelated tool-generation task for missing document.','Repeats tool-policy words instead of kinder rewrite.','Repeats unrelated dog concern; no two items.','Invents network problem and repeats it.','Invents coding context and repeats shortening request.','Repeats unrelated childcare uncertainty.','Initially relevant backup definition then repeats; violates one sentence and never ends.','Invents an unlabeled customer testimonial and repeats request.','Repetitive kite identity rather than completed title.','Overlong and circular software explanation; not one sentence.','Copies and repeats supplied note without ending.','Repeats definition of shape, no three-shape list.','Repeats question, no grounded uncertainty answer.','Repeats uncertainty about delayed; no corrected update.','Invents server-selection advice without designs.','Invents student/software-engineer biography and repeats.','Repeats locker prompt rather than answer.','Adds unsupported date/time, then contradicts class existence.','Repeats prompt with unrelated Jason text.','Initially correct recipient then repeats prompt without ending.','Confuses presenting with taking notes and repeats.','Repeats state prompt without resolving current state.']
review=[];index=0
for r in report['records']:
 result=r['result'];error=result.get('error_code')
 if error=='session_blocked':reason='Blocked after previous invalid frame; retained as failure. No answer generated.'
 else:
  if error!='invalid_model_action':raise ValueError('Unexpected result; review again')
  reason=notes[index];index+=1
 review.append({'session':r['session'],'turn':r['turn'],'pass':False,'reason':reason})
if index!=24:raise ValueError('Incomplete review')
output={'reviewer':'Codex full raw-output review; not independent human evaluation','report_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'suite_sha256':hashlib.sha256((P/'fit-suite.json').read_bytes()).hexdigest(),'records':review,'score':score_fit(suite,report,review)}
(P/'base10b-review.json').write_text(json.dumps(output,indent=2)+'\n');print(output['score'])
