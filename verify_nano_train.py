"""CPU-only manifest, finite multi-shard resume and schedule qualification."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
from types import SimpleNamespace

from cloud_training.nano_data import write_rows, sha256_file
from cloud_training.nano_train import CampaignRows, CloudJournal, read_campaign, crossed_milestones, deadline_timestamp, lease_stop_step, evaluate_entries, next_evaluation, numerical_identity, validate_lease_seconds
from cloud_training.nano_benchmark import schedule, BATCH, HORIZON


def fixture(root):
    root = Path(root)
    entries = []
    for i, split in enumerate(('train','train','validation')):
        directory = root / f'shard{i}'
        m = write_rows(directory, [[i+1]*2049 for _ in range(3)], sequence_length=2048,
                       vocab_size=32768, tokenizer_sha256='a'*64, split=split,
                       source_manifest_sha256='b'*64, packing='test-fixture',max_rows=3)
        m['training_admitted'] = True
        (directory/'manifest.json').write_text(json.dumps(m))
        entries.append({'directory':directory.name,'manifest_sha256':sha256_file(directory/'manifest.json')})
    receipt = {'training_admitted':True,'tokenizer_sha256':'a'*64,
               'shard_manifest_sha256':[e['manifest_sha256'] for e in entries]}
    (root/'receipt.json').write_text(json.dumps(receipt))
    campaign = {'schema':1,'training_admitted':True,'tokenizer_sha256':'a'*64,
                'sequence_length':2048,'vocab_size':32768,'train':entries[:2], 'validation':entries[2:],
                'admission':{'receipt':'receipt.json','sha256':sha256_file(root/'receipt.json')}}
    path = root/'campaign.json';path.write_text(json.dumps(campaign))
    return path


class TrainTests(unittest.TestCase):
    def test_lease_six_hour_boundary_and_checkpoint_reserve(self):
        for seconds in (301,10800,10801,21600):
            validate_lease_seconds(seconds,300)
        for seconds,reserve in ((300,300),(299,300),(-1,300),(21601,300),
                                (float('nan'),300),(float('inf'),300),(600,0)):
            with self.subTest(seconds=seconds,reserve=reserve):
                with self.assertRaises(ValueError):validate_lease_seconds(seconds,reserve)

    def test_interrupted_validation_is_due_after_resume(self):
        seen = []
        entries = ['dev-a', 'dev-b']
        def evaluate(entry):
            seen.append(entry)
            return {'loss': 2.0, 'entry': entry}
        partial = evaluate_entries(entries, evaluate, lambda: len(seen) == 1)
        self.assertFalse(partial['complete'])
        # A milestone can trigger before the regular interval is due.
        due = next_evaluation(250, 100, 250, partial)
        saved = json.loads(json.dumps({'next_eval': due}))
        self.assertLessEqual(saved['next_eval'], 100)
        complete = evaluate_entries(entries, evaluate, lambda: False)
        self.assertEqual([r['entry'] for r in complete['shards']], entries)
        self.assertTrue(complete['complete'])
        self.assertEqual(next_evaluation(saved['next_eval'],100,250,complete),250)
        empty = evaluate_entries(entries,evaluate,lambda: True)
        self.assertEqual(empty['shards'],[])
        self.assertEqual(next_evaluation(250,100,250,empty),100)

    def test_numerical_identity_binds_runtime_and_modes(self):
        cuda = SimpleNamespace(get_device_name=lambda:'A100',get_device_capability=lambda:(8,0))
        fake = SimpleNamespace(cuda=cuda,version=SimpleNamespace(cuda='12.9'),
            are_deterministic_algorithms_enabled=lambda:True,
            get_float32_matmul_precision=lambda:'highest',
            backends=SimpleNamespace(cudnn=SimpleNamespace(deterministic=True,benchmark=False,allow_tf32=True)))
        with patch.dict('os.environ',{'CUBLAS_WORKSPACE_CONFIG':':4096:8'}):
            initial = numerical_identity(fake,attention_deterministic=True)
            self.assertEqual(initial['sm'],[8,0])
            self.assertEqual(initial['cublas_workspace_config'],':4096:8')
            self.assertNotEqual(initial,numerical_identity(fake,attention_deterministic=False))
            cuda.get_device_name=lambda:'L4'
            self.assertNotEqual(initial,numerical_identity(fake,attention_deterministic=True))
            cuda.get_device_name=lambda:'A100'
            fake.version.cuda='12.8'
            self.assertNotEqual(initial,numerical_identity(fake,attention_deterministic=True))

    def test_cross_shard_exact_resume_and_no_wrap(self):
        with tempfile.TemporaryDirectory() as t:
            c = read_campaign(fixture(t));r=CampaignRows(c)
            r.read(2); state=r.state_dict()
            expected=r.read(3)
            self.assertEqual([row[0] for row in expected[0]],[1,2,2])
            restored=CampaignRows(c);restored.load_state_dict(state)
            self.assertEqual(restored.read(3),expected)
            self.assertEqual(restored.global_row,5)
            before=restored.state_dict()
            with self.assertRaises(StopIteration):restored.read(2)
            self.assertEqual(before,restored.state_dict())
            restored.read(1)
            self.assertEqual(restored.remaining,0)
            eof=restored.state_dict();r.load_state_dict(eof)
            with self.assertRaises(StopIteration):r.read(1)

    def test_changed_identity_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            c=read_campaign(fixture(t));r=CampaignRows(c)
            state=r.state_dict();state['global_row']=1
            with self.assertRaises(ValueError):r.load_state_dict(state)
            state=r.state_dict();state['campaign_sha256']='f'*64
            with self.assertRaises(ValueError):r.load_state_dict(state)

    def test_unadmitted_campaign_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=fixture(t);m=json.loads(p.read_text());m['training_admitted']=False;p.write_text(json.dumps(m))
            with self.assertRaises(ValueError):read_campaign(p)

    def test_receipt_must_bind_shards(self):
        with tempfile.TemporaryDirectory() as t:
            p=fixture(t);m=json.loads(p.read_text());m['train'].reverse();p.write_text(json.dumps(m))
            with self.assertRaises(ValueError):read_campaign(p)

    def test_bounded_pilot_preserves_global_horizon(self):
        self.assertEqual(lease_stop_step(100,3),103)
        self.assertEqual(lease_stop_step(HORIZON-2,5),HORIZON)
        self.assertEqual(lease_stop_step(100),HORIZON)
        with self.assertRaises(ValueError):lease_stop_step(100,0)
        self.assertEqual(schedule(100)[0],1.0)

    def test_milestones_and_schedule_do_not_restart(self):
        self.assertEqual(crossed_milestones(999_817_216,1_000_341_504),[1_000_000_000])
        self.assertEqual(crossed_milestones(1_000_341_504,1_000_865_792),[])
        self.assertEqual(HORIZON*BATCH,10_000_269_312)
        self.assertEqual(schedule(1908)[0],1.0)
        self.assertNotEqual(schedule(1908),schedule(0))
        with self.assertRaises(ValueError):deadline_timestamp('2026-11-10T01:00:00')
        self.assertEqual(deadline_timestamp('2026-11-10T01:00:00Z'),deadline_timestamp('2026-11-10T06:30:00+05:30'))


class JournalTests(unittest.TestCase):
    prefix = 'gs://test-bucket/campaign/checkpoints'
    identity = {'campaign': 'fixture'}

    def cloud(self, remote):
        def command(obj, args):
            if args[:2] == ['objects','describe']:
                if 'raw' not in remote:
                    raise subprocess.CalledProcessError(1, args)
                return json.dumps({'generation':str(remote['generation'])})
            if args[0] == 'cat':
                return remote['raw']
            if args[0] == 'cp':
                expected = args[-1].split('=')[1]
                actual = str(remote.get('generation',0))
                if expected != actual:
                    raise subprocess.CalledProcessError(1,args)
                remote['raw'] = Path(args[1]).read_text()
                remote['generation'] = remote.get('generation',0)+1
                return ''
            raise AssertionError(args)
        return command

    def valid_journal(self, phase='ready'):
        receipt = {'status':'gcs_bundle_uploaded','remote_prefix':self.prefix+'/checkpoint-'+'a'*32,
                   'publication_order':['payload.pt','metadata.json','manifest.json','COMMITTED'],
                   'step':4,'identity':self.identity,
                   'manifest':{'version':1,'step':4,'files':{
                       k:{'sha256':'b'*64,'bytes':1} for k in ('payload.pt','metadata.json')}}}
        return {'schema':1,'campaign_prefix':self.prefix,'identity':self.identity,
                'lease_phase':phase,'entries':[{'receipt':receipt,'state':'committed','pins':[]}]}

    def test_resume_requires_remote_journal_even_with_local_file(self):
        with tempfile.TemporaryDirectory() as t, patch.object(CloudJournal,'command',self.cloud({})):
            p=Path(t)/'journal.json';p.write_text(json.dumps(self.valid_journal()))
            with self.assertRaises(subprocess.CalledProcessError):
                CloudJournal(p,campaign_prefix=self.prefix,identity=self.identity,resume_step=4)

    def test_resume_requires_committed_step_and_ready_phase(self):
        for phase, step in [('checkpoint_upload_in_progress',4),('retention_in_progress',4),('ready',5)]:
            remote={'generation':1,'raw':json.dumps(self.valid_journal(phase))}
            with tempfile.TemporaryDirectory() as t, patch.object(CloudJournal,'command',self.cloud(remote)):
                with self.assertRaises(ValueError):
                    CloudJournal(Path(t)/'journal.json',campaign_prefix=self.prefix,
                                 identity=self.identity,resume_step=step)

    def test_generation_cas_and_authoritative_resume(self):
        remote={}
        with tempfile.TemporaryDirectory() as t, patch.object(CloudJournal,'command',self.cloud(remote)):
            journal=CloudJournal(Path(t)/'fresh.json',campaign_prefix=self.prefix,identity=self.identity)
            self.assertEqual(remote['generation'],1)
            remote['generation']=2
            with self.assertRaises(subprocess.CalledProcessError):journal.set_phase('ready')
            remote={'generation':7,'raw':json.dumps(self.valid_journal())}
            with patch.object(CloudJournal,'command',self.cloud(remote)):
                resumed=CloudJournal(Path(t)/'resume.json',campaign_prefix=self.prefix,
                                     identity=self.identity,resume_step=4)
                self.assertEqual(resumed.generation,'7')

    def test_prune_intent_persisted_before_deletion_failure(self):
        remote={'generation':1,'raw':json.dumps(self.valid_journal())}
        with tempfile.TemporaryDirectory() as t, patch.object(CloudJournal,'command',self.cloud(remote)):
            j=CloudJournal(Path(t)/'journal.json',campaign_prefix=self.prefix,identity=self.identity,resume_step=4)
            def apply(*args,execute=False,**kwargs):
                if execute:
                    self.assertEqual(json.loads(remote['raw'])['lease_phase'],'retention_in_progress')
                    raise RuntimeError('interrupted deletion')
                return {'candidates':['fixture']}
            with patch('cloud_training.nano_retention.apply_retention',side_effect=apply):
                with self.assertRaises(RuntimeError):j.prune()
            self.assertEqual(json.loads(remote['raw'])['lease_phase'],'retention_in_progress')


if __name__=='__main__':unittest.main()
