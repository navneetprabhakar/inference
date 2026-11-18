import copy,datetime as dt,json,tempfile,unittest
from pathlib import Path
from cloud_training.nano_conversation_controller import validate_request,normal_stop_allowed
from cloud_training.nano_block_replay import PLAN_SHA
from cloud_training.nano_data import sha256_file

class ControllerTests(unittest.TestCase):
 def fixture(self,root):
  now=1800000000.;stamp=lambda t:dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat()
  request={'schema':1,'experiment':'ganesh-conversation-execution-v1','machine':'a2-highgpu-1g','resource_count':1,'provider_action':'STOP','disk_auto_delete':False,'automatic_retry':False,'release_eligible':False,'files':{},'authorization':'auth.json','lease_start_utc':stamp(now),'provider_stop_utc':stamp(now+195*60),'hourly_compute_disk_usd':3.7008,'storage_network_recovery_reserve_usd':7,'prior_attempt_upper_usd':0,'block_plan_sha256':PLAN_SHA,'backup_reserve_seconds':1500,'runtime_sha256':'a'*64,'instance':'test','receipts':{}}
  def write(name,data):
   (root/name).write_text(json.dumps(data));h=sha256_file(root/name);request['files'][name]=h;return h
  write('auth.json',{'approved':True,'approved_usd':25,'machine':'a2-highgpu-1g'})
  for name in ('local_tests','input_readback','provider_readback','cuda_changed_path','measured_forecast'):
   data={'status':'pass','check':name,'runtime_sha256':'a'*64,'instance':'test','stop_utc':request['provider_stop_utc'],'auto_delete':False,'remaining_seconds':8000,'measured_utc':stamp(now)}
   h=write(name+'.json',data);request['receipts'][name]={'path':name+'.json','sha256':h}
  return request,now
 def test_bound_lease_budget_and_receipts(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);r,now=self.fixture(root);self.assertEqual(validate_request(r,root,now=now),[])
   for key,bad in [('resource_count',2),('machine','a2-ultragpu-1g'),('disk_auto_delete',True),('provider_action','DELETE'),('automatic_retry',True),('release_eligible',True),('hourly_compute_disk_usd',float('nan')),('prior_attempt_upper_usd',5),('backup_reserve_seconds',0),('block_plan_sha256','b'*64),('provider_stop_utc',r['lease_start_utc'])]:
    with self.subTest(key=key):self.assertTrue(validate_request(dict(r,**{key:bad}),root,now=now))
   self.assertTrue(validate_request(r,root,now=now+196*60))
   for name in r['receipts']:
    wrong=copy.deepcopy(r);del wrong['receipts'][name];self.assertTrue(validate_request(wrong,root,now=now))
   (root/'cuda_changed_path.json').write_text('{}');self.assertTrue(validate_request(r,root,now=now))
 def test_backup_failure_never_allows_normal_stop(self):
  self.assertFalse(normal_stop_allowed(writers_joined=True,required=['best','last','raw'],verified={'best':True,'last':False,'raw':True}))
  self.assertFalse(normal_stop_allowed(writers_joined=False,required=['best'],verified={'best':True}))
  self.assertFalse(normal_stop_allowed(writers_joined=True,required=[],verified={}))
  self.assertTrue(normal_stop_allowed(writers_joined=True,required=['best','last','raw'],verified={'best':True,'last':True,'raw':True}))
if __name__=='__main__':unittest.main()
