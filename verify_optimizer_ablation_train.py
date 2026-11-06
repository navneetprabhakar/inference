"""Tiny CPU fixtures for own-base optimizer branch lineage, updates and resume."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
import torch
from torch.nn import functional as F

import checkpoint
import optimizer_ablation_train as subject
from base_run_control import Campaign
from gpt2 import Config, GPT2
from tokenizer import ASSETS
from train import optimizer_for
from verify_base_run_control import Guard
from verify_base_train import Tokenizer


class Corpus:
    seen = []

    def __init__(self, *args, device='cpu'):
        self.length = 16
        self.arrays = {'train': np.arange(4096)%31+1, 'validation': np.arange(4096)%31+1}
        self.blocks = [dict(offset=i, tokens=17) for i in range(128)]

    def row(self, split, offset, length, batch=1):
        if split == 'train':
            self.seen.append(offset)
        return torch.tensor(np.stack([self.arrays[split][offset+i*length:offset+(i+1)*length+1]
                                      for i in range(batch)]), dtype=torch.long)


class TestCampaign(Campaign):
    interrupt = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, guard_factory=Guard, **kwargs)

    def commit(self, *args):
        super().commit(*args)
        if self.interrupt == 'commit':
            type(self).interrupt = None
            raise KeyboardInterrupt('fixture committed-boundary interruption')

    def reserve(self, *args):
        super().reserve(*args)
        if self.interrupt == 'reserve':
            type(self).interrupt = None
            raise KeyboardInterrupt('fixture interrupted reservation')


def latest(path):
    ledger = json.loads((path/'campaign.json').read_text())
    return checkpoint.load(path, ledger['spec']['identity']), ledger


def equal(left, right):
    if isinstance(left, torch.Tensor):
        assert torch.equal(left, right)
    elif isinstance(left, dict):
        assert left.keys() == right.keys()
        for k in left:
            equal(left[k], right[k])
    elif isinstance(left, (tuple, list)):
        assert len(left) == len(right)
        for a, b in zip(left, right):
            equal(a, b)
    else:
        assert left == right


def fixture(root, cfg):
    """A complete tiny parent receipt chain, with no production model allocation."""
    root.mkdir()
    run = root/'runs/own-base-foundation-01'
    run.mkdir(parents=True)
    (run/'.checkpoint.lock').touch()
    (root/'gpt2.py').write_text('fixture-only source identity')
    ancestor = root/'own-random-parent.pt'
    ancestor.write_bytes(b'fixture own random provenance')
    origin = dict(path=str(ancestor), sha256=checkpoint.checksum(ancestor), acceptance_report_sha256='fixture-root')
    diagnostic = root/'diagnostics.json'
    diagnostic.write_text(json.dumps(dict(prefixes=[], pairs=[dict(id='pair', choices=[' a', ' b'],
                            members=[dict(prefix='One', correct=0), dict(prefix='Two', correct=1)])])))
    foundation = dict(target_tokens=64, targets_per_update=32, seed=17,
                      scheduler={'source_schedule': 'fixture'},
                      code_sha256={'gpt2.py': checkpoint.checksum(root/'gpt2.py')},
                      corpus='synthetic', manifest_sha256='fixture', validation_blocks_sha256='fixture',
                      diagnostics=str(diagnostic), diagnostics_sha256=checkpoint.checksum(diagnostic))
    budget = root/'foundation-budget.json'
    budget.write_text(json.dumps(foundation))
    identity = dict(model=asdict(cfg), tokenizer=ASSETS, protocol=foundation,
                    scheduler=foundation['scheduler'], seed=17, torch_version=str(torch.__version__),
                    code=foundation['code_sha256'], initialization=dict(mode='own_pretraining',
                    path=origin['path'], sha256=origin['sha256'], random_lineage_root='fixture-root'))
    frozen = dict(identity=identity, token_limit=64)
    specsha = hashlib.sha256(subject.canonical(frozen)).hexdigest()
    (run/'campaign-spec.json').write_bytes(subject.canonical(frozen))
    torch.manual_seed(17)
    model = GPT2(cfg)
    opt = optimizer_for(model)
    rows = torch.arange(17).view(1, -1)%31+1
    for _ in range(2):
        opt.zero_grad(set_to_none=True)
        F.cross_entropy(model(rows[:, :-1]).flatten(0, 1), rows[:, 1:].flatten()).backward()
        opt.step()
    parent = dict(identity=identity, campaign_id='fixture', spec_sha256=specsha,
                  step=2, trained_tokens=64, offset=64, model=model.state_dict(), optimizer=opt.state_dict(),
                  cpu_rng=torch.get_rng_state(), mps_rng=None,
                  history=[dict(trained_tokens=64, mean_ce=3.5)])
    temp = run/'fixture.pt'
    torch.save(parent, temp)
    sha = checkpoint.checksum(temp)
    dest = run/f'step-000002-{sha}.pt'
    temp.rename(dest)
    entry = dict(file=dest.name, sha256=sha, bytes=dest.stat().st_size)
    ledger = dict(spec=frozen, state='completed', trained_tokens=64, reserved_tokens=64,
                  step=2, campaign_id='fixture', checkpoints=[entry])
    ledger['sha256'] = hashlib.sha256(subject.canonical(ledger)).hexdigest()
    (run/'campaign.json').write_bytes(subject.canonical(ledger))
    (run/'latest.json').write_text(json.dumps([entry]))
    (run/'protected.json').write_text(json.dumps([dest.name]))
    supplied = dict(run=str(run), checkpoint=dest.name, sha256=sha, bytes=entry['bytes'],
                    campaign_spec_sha256=specsha, ledger_sha256=checkpoint.checksum(run/'campaign.json'))
    spec = {k: foundation[k] for k in ('corpus', 'manifest_sha256', 'validation_blocks_sha256',
                                      'diagnostics', 'diagnostics_sha256')}
    spec.update(parent=supplied, source_offset=64)
    return spec, parent, origin, budget


def run():
    torch.set_num_threads(1)
    cfg = Config(vocabulary=32, context=128, width=16, heads=2, depth=1)
    with TemporaryDirectory() as directory, ExitStack() as stack:
        root = Path(directory)
        parent_spec, parent, origin, budget = fixture(root/'parent-fixture', cfg)
        with patch.object(subject, 'ROOT', budget.parent), patch.object(subject, 'FOUNDATION_BUDGET', budget), \
                patch.object(subject, 'FOUNDATION_SHA', checkpoint.checksum(budget)), \
                patch.object(subject, 'continuation_parent', lambda *_: origin):
            loaded, receipt = subject.verify_parent(parent_spec, cfg)
            equal(loaded['model'], parent['model'])
            # Each corruption is refused before training allocation; restore bytes each time.
            prun = Path(parent_spec['parent']['run'])
            corruptions = [('campaign.json', lambda b: b+b' '),
                           ('campaign-spec.json', lambda b: b+b' '),
                           ('protected.json', lambda b: b'[]'),
                           (parent_spec['parent']['checkpoint'], lambda b: b+b'x')]
            for name, corrupt in corruptions:
                path = prun/name
                original = path.read_bytes()
                path.write_bytes(corrupt(original))
                try:
                    subject.verify_parent(parent_spec, cfg)
                except ValueError:
                    pass
                else:
                    raise AssertionError('accepted corrupted '+name)
                finally:
                    path.write_bytes(original)
            for key, value in [('source_offset', 63), ('manifest_sha256', 'changed')]:
                bad = dict(parent_spec, **{key: value})
                try:
                    subject.verify_parent(bad, cfg)
                except ValueError:
                    pass
                else:
                    raise AssertionError('accepted changed '+key)
            # Valid digests cannot make an incomplete or replay-short endpoint eligible.
            ledger_path = prun/'campaign.json'
            original_ledger = ledger_path.read_bytes()
            for key, value in [('state', 'running'), ('trained_tokens', 32), ('reserved_tokens', 65)]:
                modified = json.loads(original_ledger)
                modified.pop('sha256')
                modified[key] = value
                modified['sha256'] = hashlib.sha256(subject.canonical(modified)).hexdigest()
                ledger_path.write_bytes(subject.canonical(modified))
                bad = deepcopy(parent_spec)
                bad['parent']['ledger_sha256'] = checkpoint.checksum(ledger_path)
                try:
                    subject.verify_parent(bad, cfg)
                except ValueError:
                    pass
                else:
                    raise AssertionError('accepted semantically invalid '+key)
                finally:
                    ledger_path.write_bytes(original_ledger)
        protocol = root/'protocol.json'
        protocol.write_text('{"scope":"tiny CPU fixture"}')
        spec = dict(parent_spec, branch='preserve-095', length=16, microbatch=1,
                    targets_per_update=32, target_tokens=96, seed=17, bf16=False,
                    scheduler=dict(mode='linear-rewarm-flat', start_lr=6e-6, peak_lr=6e-5,
                                   warmup_tokens=32, horizon_tokens=96),
                    active_seconds=300, calendar_seconds=600, lease_seconds=200,
                    protocol_path=str(protocol), protocol_sha256=checkpoint.checksum(protocol),
                    code_sha256={name: checkpoint.checksum(subject.ROOT/name) for name in subject.RUNTIME})
        spec_path = root/'branch.json'
        # Training fixture injects only CPU parent/corpus/tokenizer/guard dependencies.
        for name, value in [('Corpus', Corpus), ('Campaign', TestCampaign), ('load', lambda: Tokenizer()),
                            ('verify_parent', lambda *_: (deepcopy(parent), receipt))]:
            stack.enter_context(patch.object(subject, name, value))
        baseline_rows = []
        for branch in subject.BRANCHES:
            spec['branch'] = branch
            spec_path.write_text(json.dumps(spec))
            whole = root/(branch+'-whole')
            paused = root/(branch+'-paused')
            Corpus.seen = []
            assert subject.train(spec_path, whole, device='cpu', model_config=cfg) == 'completed'
            assert Corpus.seen == [64, 80, 96, 112, 128, 144]
            a, la = latest(whole)
            baseline_rows.append(a['history'][0]['document_losses'])
            assert a['offset'] == 160 and a['trained_tokens'] == 96
            initial_step = 2 if branch == 'preserve-095' else 0
            assert {float(s['step']) for s in a['optimizer']['state'].values()} == {initial_step+3}
            assert len(json.loads((whole/'protected.json').read_text())) == 1
            assert all(n.startswith('step-000003-') for n in json.loads((whole/'protected.json').read_text()))
            assert len(list(whole.glob('step-*.pt'))) <= 2
            TestCampaign.interrupt = 'commit'
            assert subject.train(spec_path, paused, device='cpu', model_config=cfg) == 'interrupted'
            changed = dict(spec, seed=18)
            spec_path.write_text(json.dumps(changed))
            try:
                subject.train(spec_path, paused, resume=True, device='cpu', model_config=cfg)
            except ValueError:
                pass
            else:
                raise AssertionError('resume accepted changed branch identity')
            spec_path.write_text(json.dumps(spec))
            assert subject.train(spec_path, paused, resume=True, device='cpu', model_config=cfg) == 'completed'
            b, lb = latest(paused)
            for key in ('model', 'optimizer', 'cpu_rng', 'offset', 'history', 'initial_optimizer_step'):
                equal(a[key], b[key])
        equal(baseline_rows[0], baseline_rows[1])
        equal(baseline_rows[1], baseline_rows[2])
        # Reserved interrupted work consumes attempts but never skips unseen source positions.
        TestCampaign.interrupt = 'reserve'
        replay = root/'replay'
        assert subject.train(spec_path, replay, device='cpu', model_config=cfg) == 'interrupted'
        assert subject.train(spec_path, replay, resume=True, device='cpu', model_config=cfg) == 'completed'
        p, ledger = latest(replay)
        assert ledger['reserved_tokens'] == 96 and p['trained_tokens'] == 64 and p['offset'] == 128
        assert p['history'][-1]['trained_tokens'] == 64
        assert subject.learning_rate(0, spec['scheduler']) == 6e-6
        assert subject.learning_rate(32, spec['scheduler']) == 6e-5
        # Fresh states empty; preserved states exact except explicit common restart LR.
        for branch in subject.BRANCHES:
            model = GPT2(cfg)
            opt, initial = subject.initialize_optimizer(model, parent, branch)
            if branch == 'preserve-095':
                equal(opt.state_dict()['state'], parent['optimizer']['state'])
            else:
                assert opt.state_dict()['state'] == {} and initial == 0
            assert all(g['lr'] == 6e-6 for g in opt.param_groups)
        broken = deepcopy(parent)
        next(iter(broken['optimizer']['state'].values()))['step'] += 1
        try:
            subject.initialize_optimizer(GPT2(cfg), broken, 'reset-095')
        except ValueError:
            pass
        else:
            raise AssertionError('fresh branch failed to reject corrupt source optimizer')
        bad = deepcopy(spec)
        bad['code_sha256']['base_train.py'] = '0'*64
        spec_path.write_text(json.dumps(bad))
        try:
            subject.train(spec_path, root/'bad-code', device='cpu', model_config=cfg)
        except ValueError:
            pass
        else:
            raise AssertionError('accepted altered runtime')
        assert not (root/'bad-code').exists()
    print('PASS tiny CPU: parent receipt/corruption; all3 moment policies; common source/RNG/baseline; '
          'exact model+optimizer resume; replay accounting; start-update LR; endpoint-only protection; frozen code')


if __name__ == '__main__':
    run()
