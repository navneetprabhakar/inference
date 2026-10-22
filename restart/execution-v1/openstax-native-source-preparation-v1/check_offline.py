import copy,io,json,ssl,tempfile
from pathlib import Path
from unittest.mock import patch
import acquire as a
cases=[]
def refuse(f):
 try:f()
 except (ValueError,TimeoutError):return
 raise AssertionError('expected refusal')
policy=json.loads(a.POLICY.read_text());a.verify_policy(policy);cases.append('frozen162_paths_bytes_and165_shared_appearances')
for mutation in ['drop','duplicate','extra_byte','wrong_URL','lost_appearance']:
 x=copy.deepcopy(policy)
 if mutation=='drop':x['items'].pop()
 elif mutation=='duplicate':x['items'][-1]=x['items'][0]
 elif mutation=='extra_byte':x['items'][0]['body_cap']+=1
 elif mutation=='wrong_URL':x['items'][0]['url']='https://example.com/module'
 else:x['items'][0]['collection_appearances'].append({})
 refuse(lambda:a.verify_policy(x));cases.append('frame_tamper_'+mutation+'_refused')
raw=b'<document>exact source</document>';item={'url':'https://example.invalid/pinned','expected_bytes':len(raw),'body_cap':len(raw)+1,'expected_Git_blob_SHA1':a.git_blob(raw)}
class Fake:
 status=200
 def __init__(self,body=raw,url=item['url'],length=None,encoding='identity'):
  self.f=io.BytesIO(body);self.url=url;self.headers={'Content-Encoding':encoding}
  if length is not None:self.headers['Content-Length']=str(length)
 def geturl(self):return self.url
 def read(self,n):return self.f.read(n)
with tempfile.TemporaryDirectory() as t:
 p=Path(t)
 def read(fake):
  with (p/'buffer').open('wb') as f:return a.read_response(fake,item,f,lambda n:None)
 assert read(Fake(length=len(raw)))==raw and a.verify_body(raw,item)['body_SHA256']==a.sha(raw);cases.append('exact_native_bytes_EOF_and_Gitblob_verified')
 refuse(lambda:read(Fake(body=raw+b'x')));cases.append('sizeplusone_bound_no_extra_EOF_probe')
 short=read(Fake(body=raw[:-1]));refuse(lambda:a.verify_body(short,item));cases.append('short_native_length_refused')
 same=raw[:-1]+b'X';refuse(lambda:a.verify_body(same,item));cases.append('same_length_Gitblob_tamper_refused')
 for why,fake in [('redirect',Fake(url='https://elsewhere.invalid/')),('declared_length',Fake(length=len(raw)+1)),('gzip',Fake(encoding='gzip'))]:
  refuse(lambda:read(fake));cases.append(why+'_refused')
 def expired(n):raise TimeoutError('fixture worker deadline')
 with (p/'deadline').open('wb') as f:refuse(lambda:a.read_response(Fake(),item,f,expired))
 cases.append('response_checks_deadline_before_each_read')
 with patch.object(a,'DEST',p):
  a.terminal('worker-result.json',{'status':'RUNNING'});n=a.output_size();a.terminal('worker-result.json',{'status':'FAILED'});assert a.output_size()==n;cases.append('fixed_terminal_slot_no_growth')
  refuse(lambda:a.save('too_big',b'x'*a.CAP));assert not(p/'too_big').exists();cases.append('aggregate_output_prewrite_bound')
a.check_spacing(None,0);a.check_spacing(1,2);refuse(lambda:a.check_spacing(1,1.99));refuse(lambda:a.check_spacing(1,.5));cases.append('one_second_spacing_and_clock_regression_refused')
c=a.strict_TLS();assert c.check_hostname and c.verify_mode==ssl.CERT_REQUIRED and c.minimum_version>=ssl.TLSVersion.TLSv1_2;cases.append('strict_TLS_certificate_hostname_TLS12')
refuse(lambda:a.NoRedirect().redirect_request(None,None,None,None,None));cases.append('redirect_handler_fails_without_followup')
assert a.clock()>0 and a.EXTERNAL_SECONDS==600 and a.WORKER_SECONDS==570;cases.append('systemwide_shared_clock_and_external_limits')
result={'status':'PASS_OFFLINE_ONLY_NO_DOWNLOAD','case_count':len(cases),'cases':cases,'ledger_writes':0,'network_requests':0,'new_admitted_documents':0,'new_admitted_tokens':0}
(a.HERE/'offline-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
