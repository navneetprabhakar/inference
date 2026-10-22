"""Focused synthetic controls only; actual4vs29 matching requires parent dispatch."""
import json,pathlib,tempfile,types,time,signal
from unittest.mock import patch
import delta
p=json.loads((delta.HERE/'profile.json').read_text());core=delta.load_core(p);checks=[]
def check(name,yes):assert yes,name;checks.append(name)
def refuse(f):
 try:f()
 except (ValueError,TimeoutError):return
 raise AssertionError('refusal_expected')
w=['w'+str(i) for i in range(24)];idx=core.Index([' '.join(w)]);check('synthetic_self_exact',idx.compare(' '.join(w))[0]['normalized_exact']);check('boundary_point8_retained',idx.compare(' '.join(w+['x'+str(i) for i in range(5)]))[0]['fivegram_Jaccard_gte_0p8']['jaccard']==.8);check('above_point8_cardinality_rejects_Jaccard','fivegram_Jaccard_gte_0p8' not in idx.compare(' '.join(w+['x'+str(i) for i in range(6)])).get(0,{}))
long=['z'+str(i) for i in range(64)];idx=core.Index([' '.join(long)]);check('full_containment_after_early_prefix',0 in idx.compare(' '.join(['q'+str(i) for i in range(300)]+long)))
check('protected_disposition_not_overridden',core.disposition(True,True)=='PROTECTED_FAMILY_HOLD')
ds=[{'document_key':str(i),'kind':'main' if i<19 else 'external_note','UTF8_bytes':0} for i in range(29)];ds[0]['UTF8_bytes']=607322;delta.validate_docs(ds);checks.append('main19_notes10_separate_denominator')
refuse(lambda:delta.validate_docs(ds[:-1]));checks.append('missing_required_doc_refused');bad=[dict(x) for x in ds];bad[-1]['document_key']='0';refuse(lambda:delta.validate_docs(bad));checks.append('duplicate_identity_refused')
with tempfile.TemporaryDirectory() as td:
 out=pathlib.Path(td)/'out';real=signal.setitimer
 def timer(which,seconds):return real(which,min(.05,seconds) if seconds else 0)
 with patch.object(delta,'OUT',out),patch.object(delta,'verify',side_effect=lambda *a:time.sleep(.5)),patch.object(signal,'setitimer',side_effect=timer):refuse(lambda:delta.main(types.SimpleNamespace(code_pins_sha256='x',profile_sha256='y')))
 check('blocked_preflight_deadline_before_output',not out.exists());out.mkdir();f=out/'keep';f.write_bytes(b'frozen')
 with patch.object(delta,'OUT',out),patch.object(delta,'verify',side_effect=ValueError('pin')):refuse(lambda:delta.main(types.SimpleNamespace(code_pins_sha256='x',profile_sha256='y')))
 check('existing_output_not_mutated',list(out.iterdir())==[f] and f.read_bytes()==b'frozen')
 check('no_stale_alarm',signal.getitimer(signal.ITIMER_REAL)[0]==0)
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY_NO_ACTUAL29_MATCH','count':len(checks),'checks':checks}))
