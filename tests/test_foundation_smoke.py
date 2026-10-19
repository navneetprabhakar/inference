"""Frozen validation selection and paired metrics, independent of real capability."""
# Creator: Navneet Prabhakar
from copy import deepcopy
from contextlib import contextmanager
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from slm.common.config import Config, initialize
from slm.common.training import Recipe
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.eval import foundation_smoke as smoke


def index_fixture():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE approved (eid TEXT, gid TEXT, split TEXT, data TEXT)')
    for i in range(35):
        # Second eligible row in each family must never multiply its weight.
        for suffix in ('a', 'b'):
            row = dict(example_id=f'val-{i:02}-{suffix}', messages=[dict(content=f'text-{i}')])
            db.execute('INSERT INTO approved VALUES (?,?,?,?)', (row['example_id'], f'g-{i}', 'validation', json.dumps(row)))
    for split in ('train', 'test'):
        row = dict(example_id=split, messages=[dict(content=split)])
        db.execute('INSERT INTO approved VALUES (?,?,?,?)', (split, split, split, json.dumps(row)))
    return SimpleNamespace(db=db)


def test_selection_has_one_canonical_row_per_group_and_no_train_or_test_access():
    index = index_fixture()
    class Encoder:
        def encode(self, text):
            assert text not in ('train', 'test')
            return list(range(140))
    try:
        rows = smoke.select_groups(index, Encoder())
        assert len(rows) == len({r['group'] for r in rows}) == 32
        assert all(r['example_id'].endswith('-a') and len(r['tokens']) == 129 for r in rows)
        assert rows == smoke.select_groups(index, Encoder())
        index.db.execute('UPDATE approved SET gid="g-0" WHERE split="train"')
        with pytest.raises(ValueError, match='intersects'):
            smoke.select_groups(index, Encoder())
    finally:
        index.db.close()


def test_selection_requires_enough_eligible_groups():
    index = index_fixture()
    try:
        with pytest.raises(ValueError, match='32 eligible'):
            smoke.select_groups(index, SimpleNamespace(encode=lambda _: [1]*128))
    finally:
        index.db.close()


def test_paired_bootstrap_reproduces_declared_sampling_and_preserves_failure():
    initial = np.linspace(8., 10., 32)
    delta = np.linspace(-.2, .8, 32)
    result = smoke.paired_summary(initial, initial-delta)
    rng = np.random.default_rng(20261019)
    expected = np.percentile(delta[rng.integers(0, 32, (10000, 32))].mean(1), [2.5, 97.5])
    np.testing.assert_allclose(result['improvement_95_percentile_ci'], expected)
    assert result['smoke_passed'] and not result['production_accepted']
    assert not smoke.paired_summary([8.]*32, [8.]*32)['smoke_passed']
    assert not smoke.paired_summary([8.]*32, [8.05]*32)['smoke_passed']
    # Positive average alone is insufficient with a negative uncertainty bound.
    mixed = np.array([2.]*17+[-2.]*15)
    assert mixed.mean() > .1
    assert not smoke.paired_summary([8.]*32, 8.-mixed)['smoke_passed']


@pytest.mark.parametrize('a,b', [([1.]*31, [1.]*32), ([1.]*32, [float('nan')]*32),
                                  ([float('inf')]*32, [1.]*32)])
def test_invalid_paired_losses_fail(a, b):
    with pytest.raises(ValueError, match='32 finite'):
        smoke.paired_summary(a, b)


@pytest.mark.parametrize('backend', ['torch', 'mlx'])
def test_prefix_loss_matches_direct_numpy_logit_nll(backend):
    if backend == 'mlx':
        pytest.importorskip('mlx.core')
    from slm.backends import torch_backend
    import torch
    config = Config(vocab_size=16, hidden_size=8, intermediate_size=16, num_layers=1,
                    num_heads=2, num_kv_heads=1, max_seq_len=128)
    weights = initialize(config, 17)
    ids = [i % 16 for i in range(129)]
    group = dict(tokens=ids, prediction_positions=128)
    recipe = Recipe(embedding_implementation='dense-onehot-v1')
    actual = smoke.score_weights(config, weights, [group, deepcopy(group)], recipe, backend)
    with torch.no_grad():
        logits, _, _ = torch_backend.forward(torch_backend.load(config, weights), config,
            torch.tensor([ids[:-1]]), embedding_implementation=recipe.embedding_implementation)
    logits = logits.numpy().astype(np.float64)[0]
    maximum = logits.max(1)
    expected = (maximum+np.log(np.exp(logits-maximum[:, None]).sum(1))-logits[np.arange(128), ids[1:]]).mean()
    np.testing.assert_allclose(actual, [expected]*2, rtol=2e-6, atol=2e-6)
    with pytest.raises(ValueError, match='Integer'):
        smoke.score_weights(config, weights, [dict(tokens=[1.5]*129, prediction_positions=128)], recipe, backend)


def protocol_fixture(tmp_path, monkeypatch):
    index = index_fixture()
    bpe = SimpleNamespace(encode=lambda _: list(range(140)))
    chosen = smoke.select_groups(index, bpe)
    monkeypatch.setattr(smoke.BPE, 'load', lambda _: bpe)
    @contextmanager
    def checked(_):
        yield index
    monkeypatch.setattr(smoke, 'open_checked', checked)
    config = Config(vocab_size=256, max_seq_len=128)
    recipe = Recipe()
    spec = dict(seed=19, releases={'release-hash': 'unused'}, tokenizer='unused')
    spec_path = tmp_path/'spec.json'
    spec_path.write_text(json.dumps(spec))
    inputs = SimpleNamespace(config=config, recipe=recipe, data=SimpleNamespace(tokenizer_hash='tok-hash'))
    p = dict(version=1, scope='local_foundation_smoke_only', selection_seed=smoke.SELECTION_SEED,
             test_records_used=0, prediction_positions=4096, pilot_spec_sha256=sha(spec_path),
             config=config.to_dict(), initialization_seed=19, loss_implementation=recipe.loss_implementation,
             embedding_implementation=recipe.embedding_implementation, tokenizer_manifest_sha256='tok-hash',
             release_manifest_sha256='release-hash', groups=chosen)
    pp, fp = tmp_path/'protocol.json', tmp_path/'freeze.json'
    def save(protocol, reseal=True):
        pp.write_text(json.dumps(protocol))
        if reseal:
            f = {k: v for k, v in protocol.items() if k != 'groups'}
            f.update(protocol_file_sha256=sha(pp), model_updates=0, model_scores_observed=0,
                     selected_groups=32, selected_rows_sha256=digest(protocol['groups']))
            fp.write_text(json.dumps(f))
    save(p)
    return index, p, pp, fp, spec_path, spec, inputs, save


@pytest.mark.parametrize('defect', ['none', 'unsealed', 'token', 'row', 'seed', 'config', 'spec', 'test', 'recipe'])
def test_protocol_checks_pretraining_receipt_and_reconstructs_prefixes(tmp_path, monkeypatch, defect):
    index, p, pp, fp, sp, spec, inputs, save = protocol_fixture(tmp_path, monkeypatch)
    try:
        if defect == 'none':
            assert smoke.verify_protocol(pp, fp, sp, spec, inputs) == p
            return
        if defect in ('unsealed', 'token'):p['groups'][0]['tokens'][0] += 1
        elif defect == 'row':p['groups'][0]['record_sha256'] = 'forged'
        elif defect == 'seed':p['initialization_seed'] += 1
        elif defect == 'config':p['config']['norm_eps'] = .01
        elif defect == 'spec':sp.write_text(sp.read_text()+'\n')
        elif defect == 'test':p['test_records_used'] = 1
        elif defect == 'recipe':p['embedding_implementation'] = 'other'
        save(p, reseal=defect != 'unsealed')
        with pytest.raises(ValueError):
            smoke.verify_protocol(pp, fp, sp, spec, inputs)
    finally:
        index.db.close()


def test_incomplete_live_run_cannot_be_scored_as_final(tmp_path):
    # Valid real fixture inputs get past spec resolution; absence of the terminal
    # report, rather than an unrelated missing specification, prevents scoring.
    from test_train import spec as fixture_spec
    spec = fixture_spec(tmp_path, 'foundation')
    path = tmp_path/'spec.json'
    path.write_text(json.dumps(spec))
    live = tmp_path/'live'
    live.mkdir()
    (live/'run.json').write_text('{}')
    with pytest.raises(FileNotFoundError) as exc:
        smoke.evaluate(path, tmp_path/'protocol.json', tmp_path/'freeze.json', live)
    assert Path(exc.value.filename) == live/'report.json'
