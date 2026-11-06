"""CPU-only tiny fixtures; never load or generate from the live 124M model."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

import base_sample as sampler
from gpt2 import Config, GPT2
from tokenizer import ASSETS


class SamplerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        (self.run / '.checkpoint.lock').touch()
        self.identity = dict(model=asdict(Config()), tokenizer=ASSETS,
                             initialization=dict(mode='own_pretraining', path=str(sampler.PARENT_PATH),
                                                 sha256=sampler.PARENT_SHA,
                                                 random_lineage_root=sampler.PRE_SFT_REPORT_SHA256),
                             scheduler={'peak_lr': .00006},
                             protocol=dict(length=512, targets_per_update=8192,
                                           scheduler={'peak_lr': .00006},
                                           parent_checkpoint=dict(path=str(sampler.PARENT_PATH), sha256=sampler.PARENT_SHA)),
                             code={f: sampler.digest(sampler.ROOT / f) for f in ('gpt2.py', 'tokenizer.py')})

    def fixture(self, *, payload_changes=None, historical=False):
        spec = dict(identity=self.identity, token_limit=16384)
        tiny = GPT2(Config(vocabulary=19, width=12, heads=3, depth=1, context=512))
        payload = dict(identity=self.identity, campaign_id='test-campaign',
                       spec_sha256=hashlib.sha256(sampler.canonical(spec)).hexdigest(),
                       step=1, trained_tokens=8192, offset=8192, model=tiny.state_dict())
        payload.update(payload_changes or {})
        file = self.run / 'fixture.pt'
        torch.save(payload, file)
        digest = sampler.digest(file)
        name = f'step-{payload["step"]:06d}-{digest}.pt'
        file.rename(self.run / name)
        entry = dict(file=name, sha256=digest, bytes=(self.run / name).stat().st_size)
        ledger = dict(spec=spec, campaign_id='test-campaign', reserved_tokens=8192,
                      checkpoints=[] if historical else [entry])
        self.write('campaign-spec.json', spec)
        self.write('protected.json', [name])
        self.ledger(ledger)
        return name, ledger

    def write(self, name, obj):
        (self.run / name).write_text(json.dumps(obj))

    def ledger(self, value):
        self.write('campaign.json', dict(value, sha256=hashlib.sha256(sampler.canonical(value)).hexdigest()))

    def test_receipted_selection_and_size(self):
        name, _ = self.fixture()
        weights, receipt = sampler.verified_checkpoint(self.run, step=1)
        self.assertIn('tokens.weight', weights)
        self.assertEqual(receipt['file'], str((self.run / name).resolve()))
        self.assertTrue(receipt['separate_size_receipt'])
        self.assertEqual(receipt['trained_context'], 512)

    def test_historical_protected_digest_without_size_receipt(self):
        _, _ = self.fixture(historical=True)
        _, receipt = sampler.verified_checkpoint(self.run, protected_step=1)
        self.assertFalse(receipt['separate_size_receipt'])
        self.assertTrue(receipt['protected'])

    def test_zero_target_baseline_retains_parent_context(self):
        self.fixture(payload_changes={'step': 0, 'trained_tokens': 0, 'offset': 0})
        _, receipt = sampler.verified_checkpoint(self.run, protected_step=0)
        self.assertEqual(receipt['trained_context'], 256)
        sampler.validate_generation([1]*250, 6, 0., context=receipt['trained_context'])
        with self.assertRaisesRegex(ValueError, 'trained context 256'):
            sampler.validate_generation([1]*250, 7, 0., context=receipt['trained_context'])
        with self.assertRaisesRegex(ValueError, 'trained context 256'):
            sampler.complete(None, [1]*250, 7, context=receipt['trained_context'])

    def test_cli_honors_checkpoint_context_before_generation(self):
        tokenizer = SimpleNamespace(encode=lambda text: SimpleNamespace(ids=[1]*250))
        args = ['base_sample.py', str(self.run), '--protected-step', '0', '--prompt', 'text', '--max-new-tokens', '7']
        with patch.object(sampler.sys, 'argv', args), patch.object(sampler, 'load', return_value=tokenizer), \
                patch.object(sampler, 'load_model', return_value=(None, {'trained_context': 256})), \
                patch.object(sampler, 'complete') as generate:
            with self.assertRaisesRegex(ValueError, 'trained context 256'):
                sampler.main()
            generate.assert_not_called()

    def test_corrupted_ledger(self):
        self.fixture()
        ledger = json.loads((self.run / 'campaign.json').read_text())
        ledger['reserved_tokens'] += 1
        self.write('campaign.json', ledger)
        with self.assertRaisesRegex(ValueError, 'ledger checksum'):
            sampler.verified_checkpoint(self.run, step=1)

    def test_size_receipt(self):
        _, ledger = self.fixture()
        ledger['checkpoints'][0]['bytes'] += 1
        self.ledger(ledger)
        with self.assertRaisesRegex(ValueError, 'byte size'):
            sampler.verified_checkpoint(self.run, step=1)

    def test_corrupt_bytes_same_size(self):
        name, _ = self.fixture()
        file = self.run / name
        data = bytearray(file.read_bytes())
        data[-1] ^= 1
        file.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            sampler.verified_checkpoint(self.run, step=1)

    def test_wrong_parent_even_with_recomputed_ledger(self):
        self.identity['initialization']['sha256'] = '0' * 64
        self.fixture()
        with self.assertRaisesRegex(ValueError, 'parent lineage'):
            sampler.verified_checkpoint(self.run, step=1)

    def test_frozen_spec_mismatch(self):
        self.fixture()
        spec = json.loads((self.run / 'campaign-spec.json').read_text())
        spec['token_limit'] += 8192
        self.write('campaign-spec.json', spec)
        with self.assertRaisesRegex(ValueError, 'frozen specification'):
            sampler.verified_checkpoint(self.run, step=1)

    def test_busy_checkpoint_writer_refused(self):
        self.fixture()
        with (self.run / '.checkpoint.lock').open('rb') as stream:
            sampler.fcntl.flock(stream, sampler.fcntl.LOCK_EX | sampler.fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, 'publication is active'):
                sampler.verified_checkpoint(self.run, step=1)

    def test_ambiguous_step_requires_basename(self):
        first, _ = self.fixture()
        second, _ = self.fixture(payload_changes={'extra': 'distinct save'})
        self.write('protected.json', [first, second])
        with self.assertRaisesRegex(ValueError, 'missing or ambiguous'):
            sampler.verified_checkpoint(self.run, protected_step=1)
        _, receipt = sampler.verified_checkpoint(self.run, filename=first)
        self.assertEqual(Path(receipt['file']).name, first)

    def test_wrong_context(self):
        self.identity['protocol']['length'] = 1024
        self.fixture()
        with self.assertRaisesRegex(ValueError, '512-token context'):
            sampler.verified_checkpoint(self.run, step=1)

    def test_wrong_architecture(self):
        self.identity['model']['depth'] = 2
        self.fixture()
        with self.assertRaisesRegex(ValueError, '124M'):
            sampler.verified_checkpoint(self.run, step=1)

    def test_payload_outside_campaign(self):
        self.fixture(payload_changes={'campaign_id': 'another'})
        with self.assertRaisesRegex(ValueError, 'outside the frozen'):
            sampler.verified_checkpoint(self.run, step=1)

    def test_wrong_cursor(self):
        self.fixture(payload_changes={'offset': 8191})
        with self.assertRaisesRegex(ValueError, 'cursor/token'):
            sampler.verified_checkpoint(self.run, step=1)

    def test_explicit_selection_required_and_no_path_escape(self):
        self.fixture()
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            sampler.verified_checkpoint(self.run)
        with self.assertRaisesRegex(ValueError, 'not a receipted'):
            sampler.verified_checkpoint(self.run, filename='../fixture.pt')
        with self.assertRaisesRegex(ValueError, 'missing or ambiguous'):
            sampler.verified_checkpoint(self.run, protected_step=2)

    def test_protected_symlink_rejected(self):
        name, _ = self.fixture()
        file = self.run / name
        file.rename(self.run / 'other.pt')
        file.symlink_to(self.run / 'other.pt')
        with self.assertRaisesRegex(ValueError, 'regular local file'):
            sampler.verified_checkpoint(self.run, protected_step=1)

    def test_model_loader_parameter_count(self):
        self.fixture()
        tiny = GPT2(Config(vocabulary=19, width=12, heads=3, depth=1, context=512))
        with patch.object(sampler, 'GPT2', return_value=tiny):
            with self.assertRaisesRegex(ValueError, 'parameter count'):
                sampler.load_model(self.run, step=1)

    def test_context_and_temperature_limits(self):
        for ids, count, temp in [([], 1, 0.), ([1]*512, 1, 0.), ([1], 0, 0.),
                                 ([1], 1, -1.), ([1], 1, float('nan'))]:
            with self.assertRaises(ValueError):
                sampler.validate_generation(ids, count, temp)
        sampler.validate_generation([1]*500, 12, 0.)

    def test_tiny_cpu_generation_repeatable(self):
        torch.manual_seed(42)
        model = GPT2(Config(vocabulary=19, width=12, heads=3, depth=1, context=512)).eval()
        for temperature in (0., .8):
            first = sampler.complete(model, [1, 2], 4, temperature, seed=7, eot=18)
            self.assertEqual(first, sampler.complete(model, [1, 2], 4, temperature, seed=7, eot=18))
            self.assertLessEqual(len(first), 4)


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main(verbosity=2)
