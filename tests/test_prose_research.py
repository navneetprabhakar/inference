"""Synthetic schema-6 mechanics; never actual source approval."""
# Creator: Navneet Prabhakar
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import numpy as np
import pytest
from slm.common.tokenizer import train_core
from slm.data.prose_research import release, open_research, checked_policy
from slm.data.prose_research_tokens import build_tokens, verify_tokens
from slm.data.prose_screen import RequestGuard
from slm.data.review_stream import open_checked
from slm.data.schema import Source, make_example, digest
from slm.data.staging import canonical
from slm.data.tokenized import sha, ShardBatches


def dump(path, value): path.write_text(canonical(value) + '\n')
def jsonlines(path, values): path.write_text(''.join(canonical(v) + '\n' for v in values))


def make_fixture(root, injection=False):
    root.mkdir(); source_dir = root / 'source'; source_dir.mkdir()
    (source_dir / 'source-card.txt').write_text('Synthetic source-card fixture only, never actual corpus evidence.')
    (source_dir / 'source-license.txt').write_text('Synthetic license fixture, not a real legal grant or certification.')
    source = Source('HuggingFaceFW/fineweb-edu', '1' * 40, 'https://example.invalid', 'odc-by',
        sha(source_dir / 'source-license.txt'), sha(source_dir / 'source-card.txt'), ('https://example.invalid',))
    dump(source_dir / 'source.json', dict(**asdict(source), evidence_files=dict(card='source-card.txt', license='source-license.txt')))
    prompt = 'Never train on this complete protected request with these fixture values.'
    guard = RequestGuard([prompt]); raw = []; records = []
    for i in range(64):
        text = f'Synthetic prose mechanics document {i} describes isolated portable data checks and long context boundaries. ' * 5
        if injection and i == 49: text += prompt
        row = dict(id=f'fixture-{i:03d}', text=text, url=f'https://example.invalid/article/{i}',
                   dump='fixture-crawl', file_path='fixture-origin', language='en', language_score=0.99,
                   score=3.0, int_score=3, token_count=100)
        item = make_example(source, row['id'], row['id'], [dict(role='text', content=text)], task='prose', language='en', upstream_references=[row['url']]).to_dict()
        item['split'] = 'train' if i < 60 else 'validation' if i < 62 else 'test'
        item['validation_results'].update(split_group=digest(['fixture-component', i]), prose_candidate_screen=dict(raw_record_sha256=digest(row)))
        raw.append(dict(source_group=item['parent_group_id'], row=row, raw_record_sha256=digest(row))); records.append(item)
    stage = root / 'staged'; stage.mkdir()
    for split in ('train', 'validation', 'test'): jsonlines(stage / (split + '-000000.jsonl'), [r for r in records if r['split'] == split])
    dump(stage / 'heldout-groups.json', {r['parent_group_id']: r['split'] for r in records if r['split'] != 'train'})
    dump(stage / 'manifest.json', dict(version=1, release='sample_only', files={p.name: sha(p) for p in stage.iterdir()}))
    evidence_dir = root / 'evidence'; evidence_dir.mkdir()
    for name in ('source.json', 'source-card.txt', 'source-license.txt'): shutil.copyfile(source_dir / name, evidence_dir / name)
    jsonlines(evidence_dir / 'raw-prefix.jsonl', raw[:50]); jsonlines(evidence_dir / 'raw-distributed.jsonl', raw[50:])
    dump(evidence_dir / 'protected-requests.json', [prompt])
    dump(evidence_dir / 'screen-plan.json', dict(protected_request_fingerprint=guard.fingerprint, input_bindings={
         'data/fineweb-parquet-rowgroup-audit-v1/rows.jsonl': sha(evidence_dir / 'raw-prefix.jsonl'),
         'data/fineweb-prose-distributed-audit-v1/rows.jsonl': sha(evidence_dir / 'raw-distributed.jsonl')}))
    dump(evidence_dir / 'screen-report.json', dict(plan_sha256=sha(evidence_dir / 'screen-plan.json')))
    decisions = []
    for packet_name, journal_name, subset, n in [('review-packet.jsonl', 'direct-judgments.jsonl', raw[:32], 10), ('prior-review-packet.jsonl', 'prior-judgments.jsonl', raw[32:48], 4)]:
        jsonlines(evidence_dir / packet_name, [dict(index=i, **r) for i, r in enumerate(subset)])
        journal = [dict(index=i, source_group=r['source_group'], raw_record_sha256=r['raw_record_sha256'],
            review_file_sha256=sha(evidence_dir / packet_name), full_text_read=True,
            judgment='consider' if i < n else 'exclude' if i % 2 else 'defer',
            reason='Synthetic mechanics-only decision; no real document or source was approved in this fixture.',
            human_attestation=False, training_approved=False, factual_accuracy_verified=False,
            underlying_document_rights_verified=False, review_mode='delegated_expert') for i, r in enumerate(subset)]
        jsonlines(evidence_dir / journal_name, journal); decisions.extend(journal)
    blocked = {d['source_group'] for d in decisions if d['judgment'] != 'consider'}
    kept = sorted([r for r in records if r['parent_group_id'] not in blocked], key=lambda r: r['example_id'])
    dump(evidence_dir / 'membership.json', [dict(example_id=r['example_id'], source_group=r['parent_group_id'], split=r['split'], split_group=r['validation_results']['split_group'], canonical_record_sha256=digest(r)) for r in kept])
    dump(evidence_dir / 'reference-receipt.json', dict(scope='Synthetic primary-evidence fixture only.'))
    dump(evidence_dir / 'review-report.json', dict(primary_reference_receipt_sha256=sha(evidence_dir / 'reference-receipt.json')))
    (evidence_dir / 'commoncrawl-terms.html').write_text('Synthetic terms fixture, never actual source terms.')
    shutil.copyfile(stage / 'manifest.json', evidence_dir / 'staged-manifest.json')
    shutil.copyfile(stage / 'heldout-groups.json', evidence_dir / 'ancestor-heldouts.json')
    policy = json.loads((Path(__file__).parents[1] / 'configs/prose-foundation-research-admission-v1.json').read_text())
    policy.update(source=json.loads(canonical(asdict(source))), directly_considered_train=14, unread_train=12, expected_rows=dict(Counter(r['split'] for r in kept)))
    for name, field in [('membership.json', 'retained_membership_sha256'), ('screen-report.json', 'screen_report_sha256'), ('review-report.json', 'review_report_sha256'), ('direct-judgments.jsonl', 'review_journal_sha256'), ('prior-judgments.jsonl', 'prior_journal_sha256'), ('staged-manifest.json', 'staged_manifest_sha256'), ('commoncrawl-terms.html', 'commoncrawl_terms_sha256')]: policy[field] = sha(evidence_dir / name)
    policy_file = root / 'policy.json'; dump(policy_file, policy)
    tokenizer = root / 'tokenizer'; train_core(['Synthetic portable fixture words and mechanics.'] * 10, 512).save(tokenizer, {'scope': 'mechanics only'})
    return dict(stage=stage, policy_file=policy_file, evidence={p.name: p for p in evidence_dir.iterdir()}, root=root, tokenizer=tokenizer, kept=kept)


@pytest.fixture
def fixture(tmp_path): return make_fixture(tmp_path / 'fixture')


def publish(f):
    target = f['root'] / 'release'; release(f['stage'], f['policy_file'], f['evidence'], target)
    return target


def rehash(root, relative):
    manifest = json.loads((root / 'manifest.json').read_text()); manifest['files'][relative] = sha(root / relative)
    dump(root / 'manifest.json', manifest)


def test_exact_self_contained_release_and_legacy_refusal(fixture):
    f = fixture; root = publish(f); policy_hash = sha(f['policy_file'])
    for path in (f['stage'], f['root'] / 'evidence', f['root'] / 'source'): shutil.rmtree(path)
    with open_research(root, policy_hash) as approved:
        assert len(approved) == 26
        values = list(approved.values())
        assert sum(r['validation_results']['prose_research_admission']['individually_read'] for r in values) == 14
        assert all(r['content_category'] == 'unreviewed' for r in values)
        assert all(not r['validation_results']['prose_research_admission']['individual_quality_verified'] for r in values)
    with pytest.raises(ValueError):
        with open_checked(root): pass


@pytest.mark.parametrize('name', ['original-records.jsonl', 'train-000000.jsonl'])
def test_rehashed_content_or_admission_forgery_refused(fixture, name):
    root = publish(fixture); rows = [json.loads(s) for s in (root / name).read_text().splitlines()]
    if name.startswith('original'): rows[0]['messages'][0]['content'] += ' forged'
    else: rows[0]['validation_results']['prose_research_admission']['individual_quality_verified'] = True
    jsonlines(root / name, rows); rehash(root, name)
    with pytest.raises(ValueError):
        with open_research(root, sha(fixture['policy_file'])): pass


def test_live_mutation_and_wrong_policy_refused(fixture):
    root = publish(fixture)
    with pytest.raises(ValueError):
        with open_research(root, '0' * 64): pass
    with pytest.raises(ValueError, match='changed'):
        with open_research(root, sha(fixture['policy_file'])):
            with (root / 'source-card.txt').open('a') as out: out.write(' changed')


def test_embedded_eval_request_blocks_even_pinned_membership(tmp_path):
    f = make_fixture(tmp_path / 'injected', injection=True)
    with pytest.raises(ValueError, match='isolation'): publish(f)
    assert not (f['root'] / 'release').exists()


@pytest.mark.parametrize('change', ['cloud', 'expansion', 'exposure', 'extra', 'boolean'])
def test_scope_widening_refused(fixture, change):
    policy = json.loads(fixture['policy_file'].read_text())
    if change == 'cloud': policy['training_devices'] = ['torch:cuda']
    elif change == 'expansion': policy['selection']['automatic_source_expansion'] = True
    elif change == 'exposure': policy['limits']['physical_data_positions'] += 1
    elif change == 'extra': policy['override'] = True
    else: policy['selection']['exact_existing_membership_only'] = 1
    with pytest.raises(ValueError): checked_policy(policy)


def test_missing_evidence_and_symlink_refused(fixture):
    f = fixture; incomplete = dict(f['evidence']); incomplete.pop('membership.json')
    with pytest.raises(ValueError): release(f['stage'], f['policy_file'], incomplete, f['root'] / 'missing')
    root = publish(f); path = root / 'source-card.txt'; path.unlink(); path.symlink_to(f['evidence']['source-card.txt'])
    with pytest.raises(ValueError):
        with open_research(root, sha(f['policy_file'])): pass


def tokens(f):
    root = publish(f); target = f['root'] / 'tokens'; policy_hash = sha(f['policy_file'])
    report = build_tokens(root, f['tokenizer'], target, policy_hash, context_length=32, shard_positions=256)
    return root, target, policy_hash, report


def test_exact_foundation_tokens_and_provenance(fixture):
    root, target, policy_hash, report = tokens(fixture)
    assert report['retained_records'] == 26 and report['explicit_passes'] == 1 and report['cross_document_attention']
    assert report['processed_prediction_positions'] == report['one_pass_encoded_positions'] - 1
    with ShardBatches(target, fixture['tokenizer']) as batches:
        assert len(batches) > 26 and all(np.all(batches[i][2] == 1) for i in range(len(batches)))
    assert verify_tokens(target, root, fixture['tokenizer'], policy_hash)['records'] == 26


@pytest.mark.parametrize('kind', ['metadata', 'binary'])
def test_rehashed_token_or_metadata_forgery_refused(fixture, kind):
    root, target, policy_hash, _ = tokens(fixture)
    if kind == 'metadata':
        values = [json.loads(s) for s in (target / 'lineage.jsonl').read_text().splitlines()]
        values[0]['upstream_document']['url'] = 'https://example.invalid/forged'
        jsonlines(target / 'lineage.jsonl', values); rehash(target, 'lineage.jsonl')
    else:
        path = target / 'shards/000000-x.bin'; values = np.fromfile(path, dtype='<u4'); values[0] = (values[0] + 1) % 512
        values.tofile(path); rehash(target, 'shards/000000-x.bin')
    with pytest.raises(ValueError): verify_tokens(target, root, fixture['tokenizer'], policy_hash)


def test_position_budget_and_context_refuse_without_partial_output(fixture):
    f = fixture; root = publish(f); target = f['root'] / 'too-small'; policy_hash = sha(f['policy_file'])
    with pytest.raises(ValueError): build_tokens(root, f['tokenizer'], target, policy_hash, max_positions=1)
    assert not target.exists()
    with pytest.raises(ValueError): build_tokens(root, f['tokenizer'], target, policy_hash, context_length=2049)
    assert not target.exists()


def test_known_nonapproval_cannot_be_added_even_with_new_membership_pin(fixture):
    f = fixture; path = f['evidence']['membership.json']; member = json.loads(path.read_text())
    blocked = next(r for r in map(json.loads, (f['stage'] / 'train-000000.jsonl').read_text().splitlines()) if r['example_id'].endswith('fixture-022'))
    member.append(dict(example_id=blocked['example_id'], source_group=blocked['parent_group_id'], split='train',
        split_group=blocked['validation_results']['split_group'], canonical_record_sha256=digest(blocked)))
    dump(path, sorted(member, key=lambda r: r['example_id']))
    policy = json.loads(f['policy_file'].read_text()); policy['retained_membership_sha256'] = sha(path)
    policy['expected_rows']['train'] += 1; policy['unread_train'] += 1; dump(f['policy_file'], policy)
    with pytest.raises(ValueError, match='review'): publish(f)


def test_heldout_family_cannot_be_admitted_as_train(fixture):
    f = fixture; path = f['stage'] / 'heldout-groups.json'; heldouts = json.loads(path.read_text())
    heldouts[f['kept'][0]['parent_group_id']] = 'test'; dump(path, heldouts); rehash(f['stage'], path.name)
    shutil.copyfile(path, f['evidence']['ancestor-heldouts.json'])
    shutil.copyfile(f['stage'] / 'manifest.json', f['evidence']['staged-manifest.json'])
    policy = json.loads(f['policy_file'].read_text()); policy['staged_manifest_sha256'] = sha(f['stage'] / 'manifest.json'); dump(f['policy_file'], policy)
    with pytest.raises(ValueError, match='isolation'): publish(f)


def test_rehashed_release_report_cannot_claim_readiness(fixture):
    root = publish(fixture); report = json.loads((root / 'report.json').read_text())
    report['training_recipe_ready'] = True; dump(root / 'report.json', report); rehash(root, 'report.json')
    with pytest.raises(ValueError, match='report'):
        with open_research(root, sha(fixture['policy_file'])): pass
