"""Real tiny backend mechanics with synthetic source decisions and bounded ledgers."""
# Creator: Navneet Prabhakar
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest

from test_sft_research import fixture, publish
from test_train import spec as old_fixture_spec
from slm.common import checkpoint
from slm.common.tokenizer import BPE
from slm.common.training import Trainer
from slm.data.tokenized import build_shards, sha
from slm.data.mixture import build_mixture
from slm.data.sft_research_tokens import build_tokens
from slm.research_sft_stage import ResearchStageInputs, ExposureLedger, run, POLICY
from slm.sft_research_preflight import preflight
from slm.train import run as old_run, verify_checkpoint
from test_resume import compare


REASON = 'Synthetic fixture tests objective transition with explicitly fresh optimizer; not actual corpus training.'


@pytest.fixture
def setup(fixture, tmp_path):
    f = fixture
    base = tmp_path/'origin-fixture'
    base.mkdir()
    origin = old_fixture_spec(base, 'foundation')
    origin['tokenizer'] = str(f['tokenizer'])
    origin['config']['vocab_size'] = BPE.load(f['tokenizer']).vocab_size
    origin['config']['max_seq_len'] = 256
    prepared = build_shards(next(iter(origin['releases'].values())), f['tokenizer'], tmp_path/'origin-tokens',
                            'foundation', context_length=64, shard_positions=128)
    origin['data'] = dict(kind='tokens', path=str(tmp_path/'origin-tokens'), fingerprint=prepared['dataset_hash'])
    origin['limits']['updates'] = 1
    report = old_run(origin, tmp_path/'origin-run')
    publish(f, tmp_path/'release')
    target = deepcopy(origin)
    target.update(version=2, scope='language_pilot', policy_file_sha256=sha(f['policy_file']))
    target['releases'] = {sha(tmp_path/'release/manifest.json'): str(tmp_path/'release')}
    tokens = build_tokens(tmp_path/'release', f['tokenizer'], tmp_path/'sft-tokens', target['policy_file_sha256'],
                          context_length=256, shard_positions=512)
    target['data'] = dict(kind='tokens', path=str(tmp_path/'sft-tokens'), fingerprint=tokens['dataset_hash'])
    target['limits'] = dict(updates=3, processed_positions=tokens['processed_prediction_positions'])
    target['recipe']['lr'] = 5e-5
    return target, origin, Path(report['latest_checkpoint']), tmp_path/'origin-run/report.json'


def inputs(setup):
    return ResearchStageInputs(*setup, POLICY, REASON)


def contract(setup, tmp_path, backend):
    folder = tmp_path/'experiment'
    folder.mkdir()
    inp = inputs(setup)
    try:
        device = 'default' if backend == 'mlx' else 'cpu'
        preflight(inp, folder/'preflight.json', backend, device)
        assessment = dict(kind='sft-terminal-assessment-contract-v1',
            actual_conversation_and_direct_score_required=True, policy_file_sha256=inp.policy_hash,
            scope='Synthetic fixture contract only; actual tests do not count as a language iteration.')
        (folder/'assessment.json').write_text(json.dumps(assessment))
        c = dict(version=1, kind='bounded-research-sft-experiment-v1', policy_file_sha256=inp.policy_hash,
            execution_root=str((folder/'execution').resolve()),
            plans=[inp.identity], limits=dict(physical_data_positions=100000, optimizer_updates=20,
                max_physical_passes_per_group=3),
            preflight={inp.identity: dict(path='preflight.json', sha256=sha(folder/'preflight.json'))},
            assessment=dict(path='assessment.json', sha256=sha(folder/'assessment.json')))
        (folder/'contract.json').write_text(json.dumps(c))
    finally: inp.close()
    return folder/'contract.json'


def execute(setup, tmp_path, name, backend='torch', **kwargs):
    target, origin, ckpt, report = setup
    return run(target, origin, ckpt, report, tmp_path/name, optimizer_policy=POLICY, reason=REASON,
               backend=backend, device='default' if backend == 'mlx' else 'cpu', **kwargs)


@pytest.mark.parametrize('backend', ['torch','mlx'])
def test_exact_import_and_checked_same_stage_resume(setup, tmp_path, backend):
    if backend == 'mlx': pytest.importorskip('mlx.core')
    init = execute(setup, tmp_path, 'init', backend, initialize_only=True)
    assert init['status'] == 'initialized_only' and init['executed_this_invocation']['updates'] == 0
    a, x = checkpoint.load(setup[2]/'state/model')
    b, y = checkpoint.load(Path(init['latest_checkpoint'])/'state/model')
    assert a == b and all(np.array_equal(v.view(np.uint32), y[k].view(np.uint32)) for k,v in x.items())
    c = contract(setup, tmp_path, backend)
    full = execute(setup, tmp_path, 'full', backend, contract_file=c)
    first = execute(setup, tmp_path, 'first', backend, contract_file=c, max_new_updates=1)
    resumed = execute(setup, tmp_path, 'resumed', backend, contract_file=c, resume=first['latest_checkpoint'])
    inp = inputs(setup)
    try:
        one = Trainer.resume(Path(full['latest_checkpoint'])/'state', inp.data, backend,
                             'default' if backend == 'mlx' else 'cpu', inp.data.tokenizer_hash)
        two = Trainer.resume(Path(resumed['latest_checkpoint'])/'state', inp.data, backend,
                             'default' if backend == 'mlx' else 'cpu', inp.data.tokenizer_hash)
        compare(one, two, True)
        verify_checkpoint(resumed['latest_checkpoint'], inp)
    finally: inp.close()
    assert full['final'] == resumed['final']
    assert resumed['initial']['step'] == 1 and resumed['conservatively_charged_updates'] == 6
    assert resumed['cumulative_logical_processed_positions'] == init['initialization']['source_final']['tokens']+resumed['final']['tokens']


def test_no_training_without_frozen_prerequisites(setup, tmp_path):
    with pytest.raises(ValueError, match='Frozen experiment'):
        execute(setup, tmp_path, 'refused')
    assert not (tmp_path/'refused').exists()


@pytest.mark.parametrize('defect', ['limit', 'policy', 'objective', 'model', 'convention'])
def test_input_expansion_refused(setup, defect):
    target, origin, ckpt, report = setup
    changed = deepcopy(target)
    if defect == 'limit': changed['limits']['processed_positions'] = 1048577
    if defect == 'policy': changed['policy_file_sha256'] = '0'*64
    if defect == 'objective': changed['data'] = deepcopy(origin['data'])
    if defect == 'model': changed['config']['hidden_size'] *= 2
    if defect == 'convention': changed['recipe']['embedding_implementation'] = 'native-gather-v1'
    with pytest.raises(ValueError):
        ResearchStageInputs(changed, origin, ckpt, report, POLICY, REASON)


def test_budget_group_cap_and_concurrent_invocation_refused(setup, tmp_path):
    c = contract(setup, tmp_path, 'torch')
    inp = inputs(setup)
    try:
        ledger = ExposureLedger(c, inp)
        try:
            with pytest.raises(BlockingIOError): ExposureLedger(c, inp)
            for _ in range(3): ledger.reserve(inp, 0, 1)
            with pytest.raises(ValueError, match='Global physical'): ledger.reserve(inp, 0, 1)
            assert ledger.updates == 3
        finally: ledger.close()
        reopened = ExposureLedger(c, inp)
        try:
            assert reopened.updates == 3
            with pytest.raises(ValueError): reopened.reserve(inp, 0, 1)
        finally: reopened.close()
    finally: inp.close()


def test_changed_contract_or_unknown_resume_cannot_reset_accounting(setup, tmp_path):
    c = contract(setup, tmp_path, 'torch')
    first = execute(setup, tmp_path, 'first', contract_file=c, max_new_updates=1)
    events = c.parent/'execution/physical-events.jsonl'
    original = events.read_text()
    rows = [json.loads(l) for l in original.splitlines()]
    rows[0]['positions'] += 1
    events.write_text(''.join(json.dumps(v)+'\n' for v in rows))
    with pytest.raises(ValueError): execute(setup, tmp_path, 'bad', contract_file=c, resume=first['latest_checkpoint'])
    events.write_text(original)
    changed = json.loads(c.read_text()); changed['limits']['physical_data_positions'] -= 1
    c.write_text(json.dumps(changed))
    with pytest.raises(ValueError): execute(setup, tmp_path, 'bad-contract', contract_file=c, resume=first['latest_checkpoint'])


def test_full_step_preflight_is_disposable_and_no_fallback(setup, tmp_path):
    inp = inputs(setup)
    try:
        before = sha(inp.source_model/'manifest.json')
        p = preflight(inp, tmp_path/'resource.json', 'torch', 'cpu')
        assert p['passed'] and p['source_unchanged'] and p['disposable_optimizer_updates'] == 1
        assert p['main_student_updates'] == 0 and sha(inp.source_model/'manifest.json') == before
        assert p['synthetic_gradient_positions'] == inp.data.max_length*inp.recipe.accumulation_steps
        with pytest.raises(ValueError): preflight(inp, tmp_path/'cuda.json', 'torch', 'cuda')
    finally: inp.close()


@pytest.mark.parametrize('field,value', [('passed', False), ('device', 'cuda'), ('source_unchanged', False)])
def test_failed_or_wrong_device_preflight_refused_before_output(setup, tmp_path, field, value):
    c = contract(setup, tmp_path, 'torch')
    path = c.parent/'preflight.json'
    p = json.loads(path.read_text()); p[field] = value
    path.write_text(json.dumps(p))
    spec = json.loads(c.read_text())
    next(iter(spec['preflight'].values()))['sha256'] = sha(path)
    c.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match='preflight'):
        execute(setup, tmp_path, 'refused', contract_file=c)
    assert not (tmp_path/'refused').exists()


def test_lost_journal_and_copied_contract_cannot_reset_budget(setup, tmp_path):
    import shutil
    c = contract(setup, tmp_path, 'torch')
    inp = inputs(setup)
    try:
        ledger = ExposureLedger(c, inp)
        ledger.reserve(inp, 0, 1)
        ledger.close()
        (c.parent/'execution/physical-events.jsonl').unlink()
        with pytest.raises(ValueError, match='lost its journal'): ExposureLedger(c, inp)
        other = tmp_path/'copied'
        other.mkdir()
        for name in ('contract.json','preflight.json','assessment.json'):
            shutil.copyfile(c.parent/name, other/name)
        with pytest.raises(ValueError, match='execution location'): ExposureLedger(other/'contract.json', inp)
    finally: inp.close()


def test_learned_checkpoint_from_unaccounted_experiment_refused(setup, tmp_path):
    c = contract(setup, tmp_path, 'torch')
    first = execute(setup, tmp_path, 'first', contract_file=c, max_new_updates=1)
    other = tmp_path/'other'
    other.mkdir()
    different = contract(setup, other, 'torch')
    with pytest.raises(ValueError, match='not recorded'):
        execute(setup, tmp_path, 'unaccounted', contract_file=different, resume=first['latest_checkpoint'])
    assert not (tmp_path/'unaccounted').exists()


def test_learned_mlx_state_can_import_exactly_to_cpu_without_updates(setup, tmp_path):
    pytest.importorskip('mlx.core')
    c = contract(setup, tmp_path, 'mlx')
    first = execute(setup, tmp_path, 'first', 'mlx', contract_file=c, max_new_updates=1)
    moved = execute(setup, tmp_path, 'cpu-import', 'torch', contract_file=c,
                    resume=first['latest_checkpoint'], initialize_only=True)
    inp = inputs(setup)
    try:
        a = Trainer.resume(Path(first['latest_checkpoint'])/'state', inp.data, 'mlx', 'default', inp.data.tokenizer_hash)
        b = Trainer.resume(Path(moved['latest_checkpoint'])/'state', inp.data, 'torch', 'cpu', inp.data.tokenizer_hash)
        compare(a, b, True)
    finally: inp.close()
    assert moved['executed_this_invocation']['updates'] == 0 and moved['initial'] == moved['final']


@pytest.mark.parametrize('cap', ['physical_data_positions','optimizer_updates'])
def test_global_position_or_update_cap_refuses_before_charge(setup, tmp_path, cap):
    c = contract(setup, tmp_path, 'torch')
    inp = inputs(setup)
    try:
        value = json.loads(c.read_text())
        value['limits'][cap] = inp.data.counts(1)[0] if cap == 'physical_data_positions' else 1
        c.write_text(json.dumps(value))
        ledger = ExposureLedger(c, inp)
        try:
            ledger.reserve(inp, 0, 1)
            positions = ledger.positions
            with pytest.raises(ValueError): ledger.reserve(inp, 1, 2)
            assert ledger.updates == 1 and ledger.positions == positions
        finally: ledger.close()
    finally: inp.close()


def test_finite_mixture_groups_and_counts_are_bound(setup, tmp_path):
    target, origin, ckpt, report = setup
    target = deepcopy(target)
    path = Path(target['data']['path'])
    tokens = json.loads((path/'manifest.json').read_text())
    amount = 2*tokens['supervised_tokens']
    mixed = build_mixture([dict(id='conversation', path=path, dataset_hash=sha(path/'manifest.json'),
        weight=1, max_passes=2, max_positions=amount)], target['tokenizer'], tmp_path/'mixture',
        objective='sft', budget=amount, minimum=amount, group_cap=100000, seed='synthetic-mixture', max_batches=1000)
    target['data'] = dict(kind='mixture', path=str(tmp_path/'mixture'), fingerprint=mixed['dataset_hash'],
                           bindings=dict(conversation=str(path)))
    target['limits']['processed_positions'] = mixed['planned_processed_positions']
    inp = ResearchStageInputs(target, origin, ckpt, report, POLICY, REASON)
    try:
        from collections import Counter
        assert len(inp.data) == 52 and set(Counter(inp.scheduled_groups).values()) == {2}
        assert inp.data.counts(52)[0] == 2*tokens['processed_tokens']
    finally: inp.close()


def test_complete_prefix_truncation_and_last_event_tampering_refused(setup, tmp_path):
    c = contract(setup, tmp_path, 'torch')
    inp = inputs(setup)
    try:
        ledger = ExposureLedger(c, inp)
        ledger.reserve(inp, 0, 1)
        ledger.reserve(inp, 1, 2)
        log = ledger.log
        ledger.close()
        original = log.read_text()
        log.write_text(original.splitlines()[0]+'\n')
        with pytest.raises(ValueError, match='rollback/truncation'): ExposureLedger(c, inp)
        rows = [json.loads(line) for line in original.splitlines()]
        rows[-1]['positions'] += 1
        log.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        with pytest.raises(ValueError, match='committed tail'): ExposureLedger(c, inp)
    finally: inp.close()


def test_valid_durable_suffix_recovers_conservatively(setup, tmp_path):
    c = contract(setup, tmp_path, 'torch')
    inp = inputs(setup)
    try:
        ledger = ExposureLedger(c, inp)
        old_head = ledger.head.read_text()
        ledger.reserve(inp, 0, 1)
        head = ledger.head
        ledger.close()
        head.write_text(old_head)
        recovered = ExposureLedger(c, inp)
        try:
            assert recovered.updates == 1 and recovered.positions == inp.data.counts(1)[0]
            assert json.loads(head.read_text())['events'] == 1
        finally: recovered.close()
    finally: inp.close()
