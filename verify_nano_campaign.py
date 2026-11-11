"""Retained allocation orchestration tests; no GCP, model loads or spend writes."""
import copy,hashlib,json,math,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from cloud_training import nano_campaign as C
from verify_nano_launch import LaunchTests

class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.c={'launch_kind':'retained','mode':'resume','resume_step':32,'max_runtime_seconds':115200,'campaign_sha256':'a'*64,'retained':{'reviewed':True,'allow_pilot_then_base':True,'review_receipt':'review-v1','expected_start_ce':C.EXPECTED_CE,'protected_finish_seconds':14400}}
    def val(self,ce):return {'complete':True,'expected_shards':1,'shards':[{'cross_entropy_nats':ce}]}
    def test_recovery_binds_status_campaign_and_authoritative_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'results').mkdir();(root/'data').mkdir()
            (root/'data/campaign.json').write_text('{}')
            status={'status':'failed_closed','step':5723,'reason':'milestone_quality_review','error':'timeout','stages':[{'status':'complete','end_step':5723}],'review_stages':[{}]}
            raw=json.dumps(status).encode();path=root/'results/campaign-status.json';path.write_bytes(raw)
            recovery={'step':5723,'status_sha256':hashlib.sha256(raw).hexdigest(),'manifest_sha256':hashlib.sha256(b'{}').hexdigest(),'next_review_number':2}
            config={**self.c,'campaign_sha256':hashlib.sha256(b'{}').hexdigest()}
            def restore(c,destination,deadline):
                self.assertEqual(c['resume_step'],5723)
                destination.mkdir();(destination/'manifest.json').write_text('{}');return destination
            with patch.object(C,'restore_resume',side_effect=restore):
                path.write_bytes(raw+b' ')
                with self.assertRaisesRegex(ValueError,'status changed'):C.recover_campaign(config,root,recovery,time.time()+10000)
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError,'skip failed'):C.recover_campaign(config,root,{**recovery,'next_review_number':1},time.time()+10000)
                campaign,resume,recovered=C.recover_campaign(config,root,recovery,time.time()+10000)
                self.assertNotIn('error',recovered)
                self.assertEqual((root/'results/failed-status-5723.json').read_bytes(),raw)
    def test_review_lifetime_and_protected_finish(self):
        C.validate_config(self.c)
        for key,value in [('reviewed',False),('expected_start_ce',5.8),('protected_finish_seconds',3600),('worker_seconds',21601),('review_wait_seconds',1000)]:
            c=copy.deepcopy(self.c);c['retained'][key]=value
            with self.assertRaises(ValueError):C.validate_config(c)
    def test_exact_pilot_and_improvement(self):
        r={'step':64,'status':'bounded_pilot_complete','reason':'pilot_update_limit','identity':{'x':1},'pilot_validation_start':self.val(C.EXPECTED_CE),'validation':self.val(5.7),'last_checkpoint':{'step':64}}
        self.assertTrue(C.check_pilot(r,{'x':1})['improved'])
        for key,value in [('step',63),('identity',{'x':2}),('pilot_validation_start',self.val(C.EXPECTED_CE+1e-12)),('validation',self.val(5.9)),('last_checkpoint',{'step':32})]:
            q=copy.deepcopy(r);q[key]=value
            with self.assertRaises(ValueError):C.check_pilot(q,{'x':1})
    def envelope(self,command):return {'command':command,'sha256':hashlib.sha256(json.dumps(command,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    def test_control_hash_generation_scope(self):
        c={'schema':1,'campaign_sha256':'a'*64,'expected_step':1908,'reviewed':True,'review_receipt':'rootreview','action':'continue_base'}
        self.assertEqual(C.validate_command(self.envelope(c),self.c,1908,2,1),c)
        with self.assertRaises(ValueError):C.validate_command(self.envelope(c),self.c,1908,1,1)
        with self.assertRaises(ValueError):C.validate_command(self.envelope(c),self.c,1909,2,1)
        e=self.envelope(c);e['command']['action']='stop'
        with self.assertRaises(ValueError):C.validate_command(e,self.c,1908,2,1)
    def test_review_stage_fixed_modules_and_output(self):
        c={'schema':1,'campaign_sha256':'a'*64,'expected_step':64,'reviewed':True,'review_receipt':'rootreview','action':'run_stage','stage':'quality','seconds':600,'args':['--allow-base']}
        C.validate_command(self.envelope(c),self.c,64,1,0)
        for key,value in [('stage','shell'),('seconds',601),('args',['--output=/tmp/overwrite'])]:
            q={**c,key:value}
            with self.assertRaises(ValueError):C.validate_command(self.envelope(q),self.c,64,1,0)
    def test_incomplete_quality_never_passes_but_zero_score_is_not_base_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'quality.json'
            for status in ('incomplete_timeout','incomplete_worker_error','incomplete_deadline'):
                p.write_text(json.dumps({'status':status}))
                with self.assertRaisesRegex(ValueError,'incomplete'):C.validate_quality_result(p)
            p.write_text(json.dumps({'status':'development_checks_complete','score':0}))
            self.assertFalse(C.validate_quality_result(p)['quality_pass_claimed'])
    def test_lazy_files_scoped_hashed_and_unique(self):
        item={'path':'sft/diagnostic/train.jsonl','uri':'gs://forge-ownbase-a100-20261110/sft/train','sha256':'a'*64,'bytes':100}
        self.assertEqual(C.validate_fetch_files([item]),[item])
        for path in ('nano_train.py','sft/../code.py','/sft/train','sft'):
            with self.assertRaises(ValueError):C.validate_fetch_files([{**item,'path':path}])
        with self.assertRaises(ValueError):C.validate_fetch_files([item,item])
        with self.assertRaises(ValueError):C.validate_fetch_files([{**item,'sha256':'bad'}])
    def test_milestone_boundaries(self):
        self.assertEqual(C.next_bound(64),math.ceil(1e9/C.BATCH))
        self.assertEqual(C.next_bound(math.ceil(1e9/C.BATCH)),math.ceil(3e9/C.BATCH))
    def test_retained_plan_does_not_double_reserve_finish_or_require10B(self):
        fixture=LaunchTests();fixture.setUp()
        fixture.c.update(self.c);fixture.c['max_updates']=32
        fixture.q.update(training_admitted=True,production_ready=False,tokens_per_second=50000)
        fixture.ledger['allocations']=[{'id':'closed','state':'closed','reserved_usd':8.98}]
        plan=fixture.plan()
        self.assertAlmostEqual(plan['retained_budget']['total_envelope_usd'],98.98)
        self.assertFalse(plan['projection']['fits_base_time_budget'])
        self.assertIn('--max-run-duration=115200s',plan['create_argv'])
        fixture.ledger['allocations'][0]['reserved_usd']=11
        with self.assertRaises(ValueError):fixture.plan()
    def test_controller_serial_pilot_then_base_and_quality_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);resume=root/'resume';resume.mkdir();identity={'own':'identity'}
            (resume/'metadata.json').write_text(json.dumps({'step':32,'identity':identity}))
            config={**self.c,'run_id':'forge-ownbase-test','backup_prefix':'gs://forge-ownbase-a100-20261110/campaign/checkpoints','checkpoint_seconds':900,'depth':16,'microbatch':4,'kernel_sha256':'b'*64,'deterministic':True,'deterministic_attention':True}
            # Stop after1B in test; default1B policy instead continues integrated raw probes.
            config['retained']={**config['retained'],'milestones':{'1000000000':{'action':'stop'}}}
            calls=[]
            def fake_process(argv,log,deadline):
                out=Path(argv[argv.index('--output')+1]);start=32 if not calls else 64;end=64 if not calls else C.next_bound(64)
                result={'step':end,'status':'bounded_pilot_complete','reason':'pilot_update_limit','identity':identity,'pilot_validation_start':self.val(C.EXPECTED_CE),'validation':self.val(5.7),'last_checkpoint':{'step':end},'base_probes':{'complete':True}}
                checkpoint=out/'step';checkpoint.mkdir();(checkpoint/'manifest.json').write_text('{}');result['last_checkpoint']['path']=str(checkpoint)
                (out/'result.json').write_text(json.dumps(result));calls.append((start,end,argv));return 0
            def restore(c,destination,deadline):
                destination.mkdir();(destination/'metadata.json').write_text(json.dumps({'step':c['resume_step'],'identity':identity}));return destination
            with patch.object(C,'stage',return_value=(root/'campaign.json',resume)),patch.object(C,'restore_resume',side_effect=restore),patch.object(C,'run_process',side_effect=fake_process),patch.object(C,'run_cloud',return_value=''),patch.object(C,'poll_command',return_value=(None,0)),patch.object(C,'execute_review_stage',return_value={'stage':'quality','complete':True}) as quality:
                self.assertEqual(C.run_campaign(config,root,time.time()+110000),0)
            self.assertEqual(quality.call_count,1);self.assertIn('--allow-base',quality.call_args.args[0]['args'])
            self.assertEqual(len(calls),2);self.assertNotEqual(calls[0][2][calls[0][2].index('--output')+1],calls[1][2][calls[1][2].index('--output')+1])
            self.assertEqual(json.loads((root/'results/campaign-status.json').read_text())['status'],'stopped')

if __name__=='__main__':unittest.main()
