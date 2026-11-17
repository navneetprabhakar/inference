"""Record same-agent reviews after reading complete raw replies and blocked turns."""
import datetime,hashlib,json
from pathlib import Path
D=Path(__file__).resolve().parent
for name in ['exposed_fit-00000016','exposed_fit-00000020','exposed_fit-00000030','development-00000000','development-00000020']:
 p=D/'raw'/f'{name}.json';j=json.loads(p.read_text());records=[]
 for r in j['records']:
  err=r['result'].get('error_code'); passed=False
  if err=='session_blocked':
   assert not r['decoded_actions'];reason='No follow-up generated after the failed opening action; failure remains in the full denominator.'
  elif err=='invalid_model_action':
   reason='Reviewed complete raw reply: fails clean termination and continues into repetition, unrelated text or illegal controls; useful initial words do not constitute a completed answer.'
  else:
   assert name=='exposed_fit-00000030' and r['result']['status']=='complete'
   passed=not (r['session']=='topic_switch' and r['turn'] in (0,2))
   reason=('Relevant complete answer; follows the supplied facts and current request, including actual prior replies.' if passed else 'Invents an unsupported claim that the proposed title is a classic children’s book; the return-to-topic turn repeats that unsupported claim instead of just the requested title.')
  records.append({'session':r['session'],'turn':r['turn'],'pass':passed,'reason':reason})
 out={'reviewer':'Codex; full same-agent per-turn review, not independent release review','reviewed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'raw_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'checkpoint_manifest_sha256':j['checkpoint_manifest_sha256'],'records':records}
 (D/'reviews'/f'{name}.review.json').write_text(json.dumps(out,indent=2)+'\n')
 print(name,sum(r['pass'] for r in records),len(records))
