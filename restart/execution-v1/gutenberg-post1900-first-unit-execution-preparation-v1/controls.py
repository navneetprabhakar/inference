"""Focused synthetic refusal/coverage controls; no source unit copy or scoring."""
import hashlib,json,pathlib,tempfile,time,subprocess,sys
from unittest.mock import patch
import run
checks=[]
def check(name,f):f();checks.append(name)
def refuse(f):
 try:f()
 except (ValueError,TimeoutError):return
 raise AssertionError('expected refusal')
raw=b'Heading\r\nEnglish text\r\n';r={'source_start_byte':0,'source_end_byte':len(raw),'UTF8_bytes':len(raw),'SHA256':hashlib.sha256(raw).hexdigest()}
check('literal_CRLF_inverse',lambda:run.exact(raw,r)==raw or (_ for _ in ()).throw(AssertionError()))
check('wrong_interval_hash',lambda:refuse(lambda:run.exact(raw,dict(r,SHA256='0'*64))))
check('unit262144_boundary',lambda:run.exact(b'x'*262144,dict(r,source_end_byte=262144,UTF8_bytes=262144,SHA256=hashlib.sha256(b'x'*262144).hexdigest())))
check('unit262145_refused',lambda:refuse(lambda:run.exact(b'x'*262145,dict(r,source_end_byte=262145,UTF8_bytes=262145,SHA256=hashlib.sha256(b'x'*262145).hexdigest()))))
p=json.loads((run.HERE/'profile.json').read_text());rules,t=run.runtime(p)
check('missing_prediction_refused',lambda:refuse(lambda:run.assign_predictions(rules,[{}],[])))
check('extra_prediction_refused',lambda:refuse(lambda:run.assign_predictions(rules,[],['__label__en .99'])))
a={};run.assign_predictions(rules,[a],['__label__en .79']);assert not a['policy_pass'];checks.append('threshold_not_relaxed')
w=list(rules.windows('a'*1024+'b'*40));assert len(w)==3 and w[-1][0]['scored'];checks.append('eligible_short_tail_retained')
w=list(rules.windows('a'*1024+'b'*39));assert not w[-1][0]['scored'] and w[-1][0]['skip_reason'];checks.append('ineligible_tail_explicit')
rows=json.loads(run.PROP.read_text())['records'];chosen=run.selected(rows);assert len(chosen)==19 and all(r['ebook_ID']!=26107 for r in chosen) and sum(len(r['external_note_dependencies']) for r in chosen)==10;checks.append('exact19_main10_notes26107held')
check('missing_main_refused',lambda:refuse(lambda:run.selected(rows[:-1])))
# Actual supervisor function, blocked preflight with accelerated timer; no worker/output.
class A:code_pins_sha256='x';profile_sha256='y'
with tempfile.TemporaryDirectory() as td:
 out=pathlib.Path(td)/'out'
 real=run.signal.setitimer
 def timer(which,seconds):return real(which,min(seconds,.08) if seconds else 0)
 with patch.object(run,'OUT',out),patch.object(run,'verify',side_effect=lambda *a:time.sleep(.5)),patch.object(run.signal,'setitimer',side_effect=timer):
  refuse(lambda:run.main(A()))
 assert not out.exists();checks.append('blocked_preflight_alarm_no_output')
 out.mkdir();marker=out/'frozen';marker.write_bytes(b'unchanged')
 with patch.object(run,'OUT',out),patch.object(run,'verify',side_effect=ValueError('badpin')):
  refuse(lambda:run.main(A()))
 assert marker.read_bytes()==b'unchanged' and list(out.iterdir())==[marker];checks.append('existing_output_unchanged_preflight_refusal')
result={'status':'PASS_SYNTHETIC_CONTROLS_NO_SOURCE_PASS','checks':checks,'count':len(checks),'main19_diagnostic_pass_executed':False}
(run.HERE/'controls-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
