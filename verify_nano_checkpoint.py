"""Meaningful CPU recovery and incomplete-publication checks (no cloud/GPU use)."""
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

from cloud_training.nano_checkpoint import save_bundle, load_bundle, validate_bundle


def make():
    model = torch.nn.Sequential(torch.nn.Linear(4, 7), torch.nn.Dropout(.2), torch.nn.Linear(7, 2))
    opt = torch.optim.AdamW(model.parameters(), lr=.003)
    sched = torch.optim.lr_scheduler.StepLR(opt, 2, gamma=.8)
    return model, opt, sched


def step(model, opt, sched, generator):
    x = torch.randn(5, 4, generator=generator)
    y = torch.randn(5, 2, generator=generator)
    opt.zero_grad(set_to_none=True)
    loss = torch.nn.functional.mse_loss(model(x), y)
    loss.backward()
    opt.step()
    sched.step()
    opt.zero_grad(set_to_none=True)
    return loss.detach().clone(), x, y


def equal_tree(a, b):
    if isinstance(a, torch.Tensor):
        return torch.equal(a, b)
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(equal_tree(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(equal_tree(x, y) for x, y in zip(a, b))
    return a == b


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'step1'
        self.model, self.opt, self.sched = make()
        self.generator = torch.Generator().manual_seed(984)
        self.identity = {'code': 'unit-test', 'model': 'tiny', 'data': 'generator-v1'}
        self.meta = {'step': 1, 'identity': self.identity}
        step(self.model, self.opt, self.sched, self.generator)

    def test_verified_receipt_and_rng_restore(self):
        self.save()
        random.random();torch.rand(3);np.random.random()
        model,opt,sched=make()
        result=load_bundle(self.path,model=model,optimizer=opt,scheduler=sched)
        self.assertTrue(result['verification']['exact_state_verified'])
        self.assertTrue(result['verification']['rng'])
        self.assertTrue(result['verification']['scheduler'])

    def test_silent_optimizer_cast_rejected(self):
        self.save()
        model,opt,sched=make()
        original=opt.load_state_dict
        def altered(state):
            original(state)
            first=next(iter(opt.state.values()))
            first['exp_avg']=first['exp_avg'].to(torch.float64)
        with patch.object(opt,'load_state_dict',side_effect=altered):
            with self.assertRaisesRegex(ValueError,'verification failed: optimizer'):
                load_bundle(self.path,model=model,optimizer=opt,scheduler=sched)

    def test_inplace_payload_alias_mutation_rejected(self):
        self.save()
        model,opt,sched=make()
        original=opt.load_state_dict
        def altered(state):
            original(state)
            # On CPU this also mutates the input payload through shared storage.
            first=next(iter(opt.state.values()))
            first['exp_avg'].add_(1)
        with patch.object(opt,'load_state_dict',side_effect=altered):
            with self.assertRaisesRegex(ValueError,'verification failed: optimizer'):
                load_bundle(self.path,model=model,optimizer=opt,scheduler=sched)

    def test_broken_rng_restore_rejected(self):
        self.save()
        model,opt,sched=make()
        with patch('cloud_training.nano_checkpoint.restore_rng_state',return_value=None):
            with self.assertRaisesRegex(ValueError,'verification failed: rng'):
                load_bundle(self.path,model=model,optimizer=opt,scheduler=sched)

    def test_exact_fingerprint_distinguishes_dtype_signed_zero_metadata(self):
        from cloud_training.nano_checkpoint import _exact_fingerprint as fp
        self.assertNotEqual(fp(torch.tensor([0.])),fp(torch.tensor([-0.])))
        self.assertNotEqual(fp(torch.tensor([1.])),fp(torch.tensor([1.],dtype=torch.float64)))
        self.assertNotEqual(fp({'step':1}),fp({'step':True}))
        self.assertNotEqual(fp(0.),fp(-0.))
        self.assertEqual(fp(torch.tensor(3.,dtype=torch.bfloat16)),fp(torch.tensor(3.,dtype=torch.bfloat16)))

    def save(self):
        return save_bundle(self.path, model=self.model, optimizer=self.opt, scheduler=self.sched,
                           metadata=self.meta, data_state={'exact': True, 'next_batch': 1,
                                                          'generator': self.generator.get_state()})

    def test_stochastic_next_update_exact(self):
        self.save()
        next_expected = step(self.model, self.opt, self.sched, self.generator)
        expected_model = copy.deepcopy(self.model.state_dict())
        expected_opt = copy.deepcopy(self.opt.state_dict())
        expected_scheduler = copy.deepcopy(self.sched.state_dict())
        expected_random = (random.random(), np.random.random(), torch.rand(3))
        model, opt, sched = make()
        result = load_bundle(self.path, model=model, optimizer=opt, scheduler=sched,
                             expected_identity=self.identity)
        gen = torch.Generator()
        gen.set_state(result['data_state']['generator'])
        next_actual = step(model, opt, sched, gen)
        self.assertTrue(equal_tree(next_expected, next_actual))
        self.assertTrue(equal_tree(expected_model, model.state_dict()))
        self.assertTrue(equal_tree(expected_opt, opt.state_dict()))
        self.assertTrue(equal_tree(expected_scheduler, sched.state_dict()))
        self.assertTrue(equal_tree(expected_random, (random.random(), np.random.random(), torch.rand(3))))
        self.assertEqual(result['data_state']['next_batch'], 1)

    def test_immutable_destination(self):
        self.save()
        with self.assertRaises(FileExistsError): self.save()
        validate_bundle(self.path)

    def test_missing_commit_rejected(self):
        self.save()
        (self.path / 'COMMITTED').unlink()
        with self.assertRaises(ValueError): validate_bundle(self.path)

    def test_truncated_upload_rejected(self):
        self.save()
        with (self.path / 'payload.pt').open('r+b') as f: f.truncate(20)
        original = copy.deepcopy(self.model.state_dict())
        with self.assertRaises(ValueError):
            load_bundle(self.path, model=self.model, optimizer=self.opt, scheduler=self.sched)
        self.assertTrue(equal_tree(original, self.model.state_dict()))

    def test_same_size_corruption_rejected(self):
        self.save()
        f = self.path / 'payload.pt'
        data = bytearray(f.read_bytes()); data[64] ^= 1; f.write_bytes(data)
        with self.assertRaises(ValueError): validate_bundle(self.path)

    def test_manifest_corruption_rejected(self):
        self.save()
        (self.path / 'manifest.json').write_text('{}')
        with self.assertRaises(ValueError): validate_bundle(self.path)

    def test_identity_mismatch_rejected(self):
        self.save()
        with self.assertRaises(ValueError):
            load_bundle(self.path, model=self.model, optimizer=self.opt, scheduler=self.sched,
                        expected_identity={'code': 'different'})

    def test_scheduler_mismatch_rejected(self):
        self.save()
        with self.assertRaises(ValueError): load_bundle(self.path, model=self.model, optimizer=self.opt)

    def test_interrupted_save_does_not_publish(self):
        with patch('cloud_training.nano_checkpoint.torch.save', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.save()
        self.assertFalse(self.path.exists())
        self.assertEqual(list(Path(self.tmp.name).glob('*.partial-*')), [])

    def test_approximate_cursor_refused(self):
        for state in ({'next_batch': 1}, {'exact': True, 'row_group': 0}):
            with self.assertRaises(ValueError):
                save_bundle(self.path, model=self.model, optimizer=self.opt, metadata=self.meta,
                            data_state=state)
        self.assertFalse(self.path.exists())

    def test_gcs_roundtrip_order_and_integrity(self):
        from cloud_training.l4_recovery_check import roundtrip_bundle
        self.save()
        store, calls = {}, []
        def fake(command, **kwargs):
            src, dst = command[3:5]
            calls.append((src, dst))
            if dst.startswith('gs://'):
                store[dst] = Path(src).read_bytes()
            else:
                Path(dst).write_bytes(store[src])
        with patch('cloud_training.l4_recovery_check.subprocess.run', side_effect=fake):
            receipt = roundtrip_bundle(self.path, remote_prefix='gs://test-bucket/project/run',
                                       destination=self.path.parent / 'download')
        self.assertEqual(len(calls), 8)
        self.assertTrue(calls[3][1].endswith('/COMMITTED'))
        self.assertEqual(receipt['identity'], self.identity)
        self.assertEqual(receipt['status'], 'gcs_bundle_integrity_passed')

    def test_upload_only_receipt_does_not_claim_readback(self):
        from cloud_training.l4_recovery_check import upload_bundle
        self.save()
        calls = []
        with patch('cloud_training.l4_recovery_check.subprocess.run', side_effect=lambda cmd, **kw: calls.append(cmd)):
            receipt = upload_bundle(self.path, remote_prefix='gs://test-bucket/project/run')
        self.assertEqual(len(calls), 4)
        self.assertTrue(calls[-1][4].endswith('/COMMITTED'))
        self.assertFalse(receipt['independent_sha256_readback'])
        self.assertEqual(receipt['status'], 'gcs_bundle_uploaded')

    def test_gcs_partial_upload_never_commits(self):
        from cloud_training.l4_recovery_check import roundtrip_bundle
        self.save()
        calls = []
        def fake(command, **kwargs):
            calls.append(command)
            if len(calls) == 2:
                raise OSError('upload interrupted')
        with patch('cloud_training.l4_recovery_check.subprocess.run', side_effect=fake):
            with self.assertRaises(OSError):
                roundtrip_bundle(self.path, remote_prefix='gs://test-bucket/project/run',
                                 destination=self.path.parent / 'partial-download')
        self.assertFalse(any(command[4].endswith('/COMMITTED') for command in calls))

    def test_symlink_refused(self):
        self.save()
        src = self.path / 'metadata.json'
        backup = self.path.parent / 'metadata-outside.json'
        src.rename(backup); src.symlink_to(backup)
        with self.assertRaises(ValueError): validate_bundle(self.path)


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
