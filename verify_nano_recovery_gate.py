"""Fault-injection tests for offline recovery policy. No cloud calls."""
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from cloud_training.nano_recovery_gate import inspect, digest, QUALIFICATION

class RecoveryGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = dt.datetime(2030, 1, 1, 1, tzinfo=dt.timezone.utc)
        (self.root/'input').write_text('fixed input')
        self.r = dict(schema=1, scope='ganesh_english_recovery', path='exact_resume',
            machine='g2-standard-8', resource_count=1, provider_action='STOP', disk_auto_delete=False,
            automatic_retry=False, automatic_restart=False, http_enabled=False,
            files={'input':digest(self.root/'input')}, local_checks_passed=True, launcher_integrated=True,
            reserve_usd=4, maximum_incremental_cost_usd=10, lease_start_utc='2030-01-01T00:00:00Z',
            provider_stop_utc='2030-01-01T04:00:00Z', backup_reserve_seconds=900,
            fit_recipe={'max_updates':64,'max_epochs':64,'lr_multiplier':.25,'packing_buffer':1,'context_tokens':2048},
            production_parent='immutable_base10b',failed_learning_pilots=0,release_exposed=False,
            selected_candidate_sha256='a'*64)
        self.bind()
    def bind(self):
        r = self.r
        spec = {k:v for k,v in r.items() if k not in ('authorization','evidence')}
        h = hashlib.sha256(json.dumps(spec,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        r['authorization']={'spec_sha256':h,'explicit_user_approval':True,'approval_reference':'synthetic-test-only',
            'cap_usd':15,'expires_utc':'2030-01-01T04:00:00Z','no_resume_exception':True}
        r['evidence']={}
        for name in ('fresh_inventory','input_backups','price_quote',*QUALIFICATION,
                     'fit_semantic_review','production_admission','production_preflight',
                     'development_selection','independent_review_ready'):
            p=self.root/(name+'.json')
            p.write_text(json.dumps({'status':'pass','check':name,'spec_sha256':h,'checked_utc':self.now.isoformat()}))
            r['evidence'][name]={'path':p.name,'sha256':digest(p)}
    def result(self,stage='qualification',now=None):
        return inspect(self.root,self.r,stage,now=now or self.now)
    def test_complete_synthetic_chain(self):
        for s in ('qualification','fit','curriculum','release'):
            self.assertTrue(self.result(s)['allowed'],self.result(s))
    def test_no_approval(self):
        self.r['authorization']=None
        self.assertFalse(self.result()['allowed'])
    def test_unapproved_draft_has_null_dates(self):
        self.r['authorization']=None;self.r['lease_start_utc']=None;self.r['provider_stop_utc']=None
        self.assertFalse(self.result()['allowed'])
    def test_old_approval_cannot_bind_new_spec(self):
        self.r['reserve_usd']=5
        self.assertIn('Approval does not bind this specification', self.result()['blockers'])
    def test_missing_receipt(self):
        del self.r['evidence']['input_backups']
        self.assertFalse(self.result()['allowed'])
    def test_receipt_tampering(self):
        (self.root/'price_quote.json').write_text('{}')
        self.assertFalse(self.result()['allowed'])
    def test_foreign_receipt_even_with_updated_hash(self):
        p=self.root/'exact_restart.json';v=json.loads(p.read_text());v['spec_sha256']='f'*64;p.write_text(json.dumps(v))
        self.r['evidence']['exact_restart']['sha256']=digest(p)
        self.assertFalse(self.result('fit')['allowed'])
    def test_changed_payload(self):
        (self.root/'input').write_text('different')
        self.assertFalse(self.result()['allowed'])
    def test_path_escape(self):
        self.r['files']={'../outside':'a'*64};self.bind()
        self.assertFalse(self.result()['allowed'])
    def test_symlink(self):
        (self.root/'link').symlink_to(self.root/'input');self.r['files']={'link':digest(self.root/'input')};self.bind()
        self.assertFalse(self.result()['allowed'])
    def test_expired_after_restart(self):
        self.assertFalse(self.result(now=self.now+dt.timedelta(hours=4))['allowed'])
    def test_shutdown_reserve(self):
        self.assertIn('No time remaining outside backup reserve',self.result(now=self.now+dt.timedelta(hours=2,minutes=50))['blockers'])
    def test_stale_cloud_receipts(self):
        self.assertFalse(self.result(now=self.now+dt.timedelta(minutes=16))['allowed'])
    def test_nonfinite_cap(self):
        for x in (float('nan'),float('inf'),True,-1):
            self.r['authorization']['cap_usd']=x
            self.assertFalse(self.result()['allowed'])
    def test_no_resume_is_terminal_diagnostic(self):
        self.r['path']='no_resume_diagnostic';self.bind()
        del self.r['evidence']['exact_restart'];del self.r['evidence']['signal_recovery']
        self.assertTrue(self.result('fit')['allowed'])
        self.assertFalse(self.result('curriculum')['allowed'])
        self.assertFalse(self.result('release')['allowed'])
    def test_no_resume_requires_exception(self):
        self.r['path']='no_resume_diagnostic';self.bind();self.r['authorization']['no_resume_exception']=False
        self.assertFalse(self.result('fit')['allowed'])
    def test_no_resume_cannot_resume(self):
        self.r['path']='no_resume_diagnostic';self.r['resume_from']='checkpoint';self.bind()
        self.assertFalse(self.result('fit')['allowed'])
    def test_restart_failure_blocks_fit(self):
        p=self.root/'exact_restart.json';v=json.loads(p.read_text());v['status']='fail';p.write_text(json.dumps(v))
        self.r['evidence']['exact_restart']['sha256']=digest(p)
        self.assertFalse(self.result('fit')['allowed'])
    def test_fault_checks_cannot_be_omitted(self):
        for name in ('provider_stop','gcs_restore','upload_rejection'):
            old=self.r['evidence'].pop(name)
            self.assertFalse(self.result('fit')['allowed'])
            self.r['evidence'][name]=old
    def test_fit_cannot_authorize_curriculum(self):
        del self.r['evidence']['production_admission']
        self.assertFalse(self.result('curriculum')['allowed'])
    def test_recipe_and_parent_escalation(self):
        self.r['fit_recipe']['max_updates']=96;self.r['production_parent']='fit_checkpoint';self.bind()
        self.assertFalse(self.result('fit')['allowed']);self.assertFalse(self.result('curriculum')['allowed'])
    def test_two_failed_pilots(self):
        self.r['failed_learning_pilots']=2;self.bind()
        self.assertFalse(self.result('curriculum')['allowed'])
    def test_exposed_release(self):
        self.r['release_exposed']=True;self.bind()
        self.assertFalse(self.result('release')['allowed'])
    def test_unknown_stage(self):
        self.assertFalse(self.result('train_anyway')['allowed'])
    def test_invalid_failure_count(self):
        for count in (-1, True, '0', float('nan')):
            self.r['failed_learning_pilots']=count;self.bind()
            self.assertFalse(self.result('curriculum')['allowed'])
    def test_boolean_resource_count(self):
        self.r['resource_count']=True;self.bind()
        self.assertFalse(self.result()['allowed'])
    def test_nonhex_selection(self):
        self.r['selected_candidate_sha256']='z'*64;self.bind()
        self.assertFalse(self.result('release')['allowed'])
    def test_unsafe_resource_policy(self):
        for key,value in [('provider_action','DELETE'),('disk_auto_delete',True),('automatic_restart',True),
                          ('automatic_retry',True),('machine','a2-highgpu-1g'),('resource_count',2)]:
            original=copy.deepcopy(self.r);self.r[key]=value;self.bind()
            self.assertFalse(self.result()['allowed']);self.r=original;self.bind()

if __name__=='__main__':unittest.main()
