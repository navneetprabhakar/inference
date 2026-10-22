import json,ssl,tempfile
from pathlib import Path
from unittest.mock import patch
import capture_metadata as c
cases=[]
context=c.strict_TLS();assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED and context.minimum_version>=ssl.TLSVersion.TLSv1_2;cases.append('strict_certificate_hostname_TLS12plus')
try:c.NoRedirect().redirect_request(None,None,None,None,None)
except ValueError:pass
else:raise AssertionError('redirect accepted')
cases.append('redirect_no_retry_handler_refuses')
with tempfile.TemporaryDirectory() as t:
 with patch.object(c,'DEST',Path(t)):
  c.terminal('worker-result.json',{'status':'RUNNING'});n=c.size();c.terminal('worker-result.json',{'status':'FAILED'});assert c.size()==n
  assert json.loads((Path(t)/'worker-result.json').read_text())['status']=='FAILED';cases.append('fixed_terminal_slot_no_growth')
  try:c.save('too-big',b'x'*c.CAP)
  except ValueError:pass
  else:raise AssertionError('aggregate cap bypass')
  assert not(Path(t)/'too-big').exists();cases.append('aggregate_output_rejected_before_write')
  c.save('exact',b'raw');assert (Path(t)/'exact').read_bytes()==b'raw';cases.append('raw_body_write_preserves_bytes')
p=json.loads(c.PROPOSAL.read_text());assert len(p['items'])==5 and sum(x['body_cap'] for x in p['items'])==c.BODY_CAP and c.sha(c.PROPOSAL.read_bytes())==c.PROPOSAL_SHA;cases.append('exact_five_authorized_URLs_and_total_caps')
r={'status':'PASS_OFFLINE_ONLY','cases':cases,'count':len(cases),'network_requests':0,'ledger_writes':0}
(c.HERE/'capture-offline-checks.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
