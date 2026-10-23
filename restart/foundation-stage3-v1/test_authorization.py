"""Metadata-only fault tests: never import model runtimes or allocate weights."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from authorization import validate_authorization
ROOT=Path(__file__).resolve().parent

def save(p,x):p.write_text(json.dumps(x))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class ApprovalTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.r=Path(self.tmp.name)
  self.c=json.loads((ROOT/'contract.json').read_text());self.c['current_stage_training_authorized']=True
  save(self.r/'contract.json',self.c);save(self.r/'source-pins.json',{})
  save(self.r/'proposal.json',dict(reference=self.c['reference'],source_pins_sha256=sha(self.r/'source-pins.json')))
  save(self.r/'approval.json',dict(approved=True,owner_message='Explicit successor approval fixture',proposal_sha256=sha(self.r/'proposal.json'),approved_epoch=1000))
  save(self.r/'clock.json',dict(start_epoch=1000,authorized_stage_deadline_epoch=19000))
 def tearDown(self):self.tmp.cleanup()
 def test_valid_bounded_receipt(self):self.assertTrue(validate_authorization(self.r,1001))
 def test_actual_prepared_run_refused(self):
  with self.assertRaises(PermissionError):validate_authorization(ROOT)
 def test_missing_receipt(self):
  (self.r/'approval.json').unlink()
  with self.assertRaises(PermissionError):validate_authorization(self.r,1001)
 def test_scope_mutations_refused(self):
  for key,value in [('current_stage_training_authorized',False),('next_stage_authorized',True),('conversation_training_authorized',True),('full_training_authorized',True),('model_parameters',100000001),('additional_retained_updates_max',1145),('additional_retained_targets_max',149946369),('aggregate_positions_cap',166153464),('prior_new_run_positions_charged',0),('wall_seconds_max',18001),('teacher_model','gpt-6-luna'),('reference',{'checkpoint_sha256':'wrong'})]:
   with self.subTest(key=key):
    c=copy.deepcopy(self.c);c[key]=value;save(self.r/'contract.json',c)
    with self.assertRaises(PermissionError):validate_authorization(self.r,1001)
  save(self.r/'contract.json',self.c)
 def test_clock_and_expiry_refused(self):
  for clock,now in [(dict(start_epoch=1000,authorized_stage_deadline_epoch=19001),1001),(dict(start_epoch=1001,authorized_stage_deadline_epoch=19001),1002),(dict(start_epoch=1000,authorized_stage_deadline_epoch=19000),18700),(dict(start_epoch=None,authorized_stage_deadline_epoch=None),1001)]:
   with self.subTest(clock=clock):
    save(self.r/'clock.json',clock)
    with self.assertRaises(PermissionError):validate_authorization(self.r,now)
 def test_changed_proposal_refused(self):
  (self.r/'proposal.json').write_text((self.r/'proposal.json').read_text()+' ')
  with self.assertRaises(PermissionError):validate_authorization(self.r,1001)
 def test_changed_source_manifest_refused(self):
  save(self.r/'source-pins.json',{'worker.py':'changed'})
  with self.assertRaises(PermissionError):validate_authorization(self.r,1001)
 def test_changed_source_refused(self):
  (self.r/'worker.py').write_text('original')
  save(self.r/'source-pins.json',{'worker.py':sha(self.r/'worker.py')});proposal=json.loads((self.r/'proposal.json').read_text());proposal['source_pins_sha256']=sha(self.r/'source-pins.json');save(self.r/'proposal.json',proposal)
  approval=json.loads((self.r/'approval.json').read_text());approval['proposal_sha256']=sha(self.r/'proposal.json');save(self.r/'approval.json',approval);(self.r/'worker.py').write_text('changed')
  with self.assertRaises(PermissionError):validate_authorization(self.r,1001)
if __name__=='__main__':unittest.main(verbosity=2)
