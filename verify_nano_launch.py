"""Offline launch safety tests: no GCP calls, weight allocation, or ledger writes."""
import copy, datetime as dt, hashlib, io, json, tempfile, tarfile, unittest
from pathlib import Path
from unittest.mock import patch
from cloud_training import nano_launch as L
from cloud_training.nano_package import extract_verified, relative, REVISION, TOKENIZER_SHA

class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,11,10,tzinfo=dt.timezone.utc)
        self.c={'schema':1,'campaign_sha256':'a'*64,'backup_prefix':L.BUCKET+'campaign-v1/checkpoints','bundle_uri':L.BUCKET+'code.tar.gz','config_uri':L.BUCKET+'config.json','index_uri':L.BUCKET+'index.json','bundle_sha256':'b'*64,'config_sha256':'c'*64,'index_sha256':'d'*64,'kernel_sha256':'e'*64,'run_id':'forge-ownbase-pilot1','zone':'us-central1-a','max_runtime_seconds':10800,'resume_step':0,'mode':'fresh','max_updates':3,'depth':16,'microbatch':4,'deterministic':True,'deterministic_attention':True,'overhead_fraction':.1,'remaining_setup_hours':.1}
        self.q={'production_ready':True,'restart_verified':True,'campaign_sha256':'a'*64,'depth':16,'microbatch':4,'deterministic':True,'deterministic_attention':True,'tokens_per_second':103000}
        self.p={'checked_utc':self.now.isoformat(),'usd_per_hour':2,'machine_type':'a2-highgpu-1g','provisioning_model':'FLEX_START','source':'reviewed GCP price'}
        self.i={'schema':1,'campaign_path':'campaign.json','campaign_sha256':'a'*64,'tokenizer_sha256':TOKENIZER_SHA,'files':[{'path':'campaign.json','uri':L.BUCKET+'campaign.json','sha256':'a'*64,'bytes':100}]}
        self.ledger={'cap_usd':100,'ancillary_reserve_usd':10,'allocations':[]}
    def plan(self): return L.build_plan(self.c,self.ledger,self.q,self.p,self.i,now=self.now)
    def test_pure_plan_bounded_provider(self):
        with patch.object(L.subprocess,'check_output',side_effect=AssertionError('No cloud allowed')):
            result=self.plan()
        self.assertIn('--max-run-duration=10800s',result['create_argv'])
        self.assertIn('--instance-termination-action=DELETE',result['create_argv'])
        self.assertIn('--no-address',result['create_argv'])
        self.assertEqual(self.ledger['allocations'],[])
    def test_whole_campaign_not_pilot_budget(self):
        self.q['tokens_per_second']=50000
        with self.assertRaisesRegex(ValueError,'Whole campaign'): self.plan()
    def test_restart_gate(self):
        self.q['restart_verified']=False
        with self.assertRaisesRegex(ValueError,'restart'): self.plan()
    def test_pending_allocation(self):
        self.ledger['allocations']=[{'state':'reserved_before_provisioning','reserved_usd':1}]
        with self.assertRaisesRegex(ValueError,'outstanding'): self.plan()
    def test_runtime_price_modes(self):
        for key,value in [('max_runtime_seconds',21601),('max_updates',0),('deterministic',False),('mode','guess')]:
            with self.subTest(key=key):
                c=copy.deepcopy(self.c); self.c[key]=value
                with self.assertRaises(ValueError): self.plan()
                self.c=c
        self.p['checked_utc']='2026-11-08T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'Fresh price'): self.plan()
    def test_inventory_paths_duplicates_tokenizer(self):
        for path in ('../x','/tmp/x','x/../y','x//y'):
            with self.assertRaises(ValueError): relative(path)
        self.i['files'].append(copy.deepcopy(self.i['files'][0]))
        with self.assertRaisesRegex(ValueError,'Duplicate'): L.data_index(self.i)
        with self.assertRaises(ValueError): L.uri('gs://other-bucket/data')
    def test_authoritative_journal_phase_and_step(self):
        identity={'phase':'base','initialization':'own_random','tokenizer_sha256':TOKENIZER_SHA,'campaign_sha256':'a'*64}
        receipt={'status':'gcs_bundle_uploaded','remote_prefix':self.c['backup_prefix']+'/checkpoint-'+'1'*32,'publication_order':['payload.pt','metadata.json','manifest.json','COMMITTED'],'step':3,'identity':identity,'manifest':{'version':1,'step':3,'files':{n:{'sha256':'a'*64,'bytes':1} for n in ('payload.pt','metadata.json')}}}
        j={'schema':1,'campaign_prefix':self.c['backup_prefix'],'lease_phase':'ready','identity':identity,'entries':[{'state':'committed','receipt':receipt}]}
        self.c['resume_step']=3
        self.assertEqual(L.select_resume(j,self.c),receipt)
        j['lease_phase']='upload_in_progress'
        with self.assertRaisesRegex(ValueError,'not ready'): L.select_resume(j,self.c)
        j['lease_phase']='ready'; self.c['resume_step']=2
        with self.assertRaisesRegex(ValueError,'changed'): L.select_resume(j,self.c)
    def test_corrupt_fetch_not_published(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d).resolve()/'file'
            def cloud(args,deadline): Path(args[2]).write_bytes(b'bad')
            with patch.object(L,'run_cloud',side_effect=cloud):
                with self.assertRaisesRegex(ValueError,'integrity'): L.fetch(L.BUCKET+'file',target,'a'*64,1)
            self.assertFalse(target.exists())
    def test_archive_traversal_and_link_rejected(self):
        for name,typ in [('../escape',tarfile.REGTYPE),('link',tarfile.SYMTYPE)]:
            with tempfile.TemporaryDirectory() as d:
                p=Path(d).resolve()/'a.tar.gz'
                with tarfile.open(p,'w:gz') as t:
                    m=tarfile.TarInfo(name); m.type=typ; t.addfile(m)
                with self.assertRaises(ValueError): extract_verified(p,Path(d).resolve()/'out')
    def test_six_hour_production_three_hour_pilot(self):
        self.c['max_runtime_seconds']=21600
        plan=self.plan()
        self.assertEqual(plan['lease_hours'],6)
        self.assertIn('--max-run-duration=21600s',plan['create_argv'])
        self.assertIn('--instance-termination-action=DELETE',plan['create_argv'])
        self.assertEqual(plan['projection']['rate_envelope_usd_per_hour'],2.5)
        self.c['launch_kind']='pilot'; self.q['training_admitted']=True
        with self.assertRaisesRegex(ValueError,'3h for pilot'): self.plan()
        self.c['max_runtime_seconds']=10800
        self.plan()
    def test_checkpoint_cadence_defaults_and_propagates(self):
        import time
        for expected in (900,1800):
            if expected==1800: self.c['checkpoint_seconds']=expected
            with patch.object(L,'stage',return_value=(Path('/data/campaign.json'),None)), patch.object(L.subprocess,'call',return_value=0) as call:
                L.worker(self.c,'/workspace',time.time()+1000)
            args=call.call_args.args[0]
            self.assertEqual(args[args.index('--checkpoint-seconds')+1],str(expected))
        for invalid in (0,600,1801,True,900.0):
            self.c['checkpoint_seconds']=invalid
            with self.assertRaisesRegex(ValueError,'cadence'): self.plan()
    def test_inventory_four_workers_same_deadline(self):
        import threading,time
        index=copy.deepcopy(self.i)
        index['files'] += [{'path':str(n),'uri':L.BUCKET+str(n),'sha256':'a'*64,'bytes':1} for n in range(9)]
        lock=threading.Lock(); active=0; peak=0; seen=[]
        def fake(source,target,expected,deadline,size):
            nonlocal active,peak
            with lock: active+=1; peak=max(peak,active); seen.append((str(target),deadline))
            time.sleep(.01)
            with lock: active-=1
        with patch.object(L,'fetch',side_effect=fake): L.fetch_inventory(index,'/data',123)
        self.assertEqual(peak,4); self.assertEqual(len(seen),10)
        self.assertEqual({x[1] for x in seen},{123})
        self.assertEqual(len({x[0] for x in seen}),10)
    def test_pilot_avoids_production_gate_circularity(self):
        self.c['launch_kind']='pilot'; self.q['production_ready']=False; self.q['training_admitted']=True
        self.assertEqual(self.plan()['status'],'review_only_not_reserved')
        self.c['max_updates']=33
        with self.assertRaisesRegex(ValueError,'bounded updates'): self.plan()
        self.c['max_updates']=3; self.q['restart_verified']=False
        with self.assertRaisesRegex(ValueError,'restart'): self.plan()
    def test_queued_request_async_still_single_reservation(self):
        self.c['request_valid_seconds']=1800
        args=self.plan()['create_argv']
        self.assertIn('--request-valid-for-duration=1800s',args); self.assertIn('--async',args)
        self.ledger['allocations']=[{'state':'queued','reserved_usd':7.5}]
        with self.assertRaisesRegex(ValueError,'outstanding'): self.plan()
    def test_worker_propagates_pilot_modes_without_cloud(self):
        import time
        with patch.object(L,'stage',return_value=(Path('/data/campaign.json'),Path('/resume'))), patch.object(L.subprocess,'call',return_value=0) as call:
            self.assertEqual(L.worker(self.c,'/workspace',time.time()+1000),0)
        args=call.call_args.args[0]
        for flag in ('--resume','--max-updates','--deterministic','--deterministic-attention','--deadline-utc'): self.assertIn(flag,args)
    def test_nonfinite_finances_fail_closed(self):
        self.ledger['ancillary_reserve_usd']=float('nan')
        with self.assertRaisesRegex(ValueError,'financial'): self.plan()
    def test_archive_manifest_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d).resolve()/'a.tar.gz'; data=b'contents'
            manifest={'revision':REVISION,'tokenizer_sha256':TOKENIZER_SHA,'files':{'x':{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}}}
            with tarfile.open(p,'w:gz') as t:
                for name,content in [('x',data),('package-manifest.json',json.dumps(manifest).encode())]:
                    m=tarfile.TarInfo(name);m.size=len(content);t.addfile(m,io.BytesIO(content))
            self.assertEqual(extract_verified(p,Path(d).resolve()/'out'),manifest)

if __name__=='__main__': unittest.main()
