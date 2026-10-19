"""Synthetic policy/release mechanics; never actual corpus quality approval."""
# Creator: Navneet Prabhakar
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import pytest

from slm.common.tokenizer import train_core
from slm.data.oasst_sft_screen import RULE
from slm.data.schema import Source, make_example, digest
from slm.data.sft_research import checked_policy, select, release, open_research
from slm.data.sft_research_tokens import build_tokens
from slm.data.staging import canonical
from slm.data.tokenized import sha, ShardBatches
from slm.data.review_stream import open_checked


def dump(path, value):
    path.write_text(canonical(value)+'\n')


@pytest.fixture
def fixture(tmp_path):
    source_dir = tmp_path/'source'
    source_dir.mkdir()
    (source_dir/'card.txt').write_text('Synthetic source-card mechanics fixture, not actual source review.')
    (source_dir/'license.txt').write_text('Synthetic license-evidence mechanics fixture, not legal clearance.')
    source = Source('OpenAssistant/oasst2', '1'*40, 'https://example.invalid', 'apache-2.0',
                    sha(source_dir/'license.txt'), sha(source_dir/'card.txt'), ('https://example.invalid',))
    dump(source_dir/'source.json', {**asdict(source), 'evidence_files': {'card': 'card.txt', 'license': 'license.txt'}})
    tok = tmp_path/'tokenizer'
    train_core(['Synthetic fixture-only words and decimal identifiers.']*10, 512).save(tok, {'scope': 'synthetic mechanics'})
    rows = []
    for i in range(67):
        split = 'train' if i < 65 else 'validation' if i == 65 else 'test'
        row = make_example(source, str(i), str(i), [dict(role='user', content=f'Fixture-only request code {i}.'),
            dict(role='assistant', content=f'This is a synthetic answer for object {i} with deliberately ordinary words '
                 'to exercise complete supervised response masks and deterministic record reconstruction in isolated testing.')],
            official_split=split, content_category='sfw', language='en').to_dict()
        row['split'] = split
        row['validation_results']['split_group'] = digest(['fixture-group', i])
        rows.append(row)
    candidate = tmp_path/'candidate'
    candidate.mkdir()
    (candidate/'candidates.jsonl').write_text(''.join(canonical(r)+'\n' for r in rows))
    samples = [dict(index=i, record=r, record_sha256=digest(r), training_approved=False,
                    full_text_read=False, judgment=None) for i, r in enumerate(rows[:64])]
    (candidate/'sample.jsonl').write_text(''.join(canonical(s)+'\n' for s in samples))
    dump(candidate/'report.json', dict(rule=RULE, training_eligible=False, tokenizer_manifest_sha256=sha(tok/'manifest.json')))
    dump(candidate/'manifest.json', dict(version=1, release='sample_only', files={p.name: sha(p) for p in candidate.iterdir()}))
    journal = [dict(index=i, example_id=s['record']['example_id'], record_sha256=s['record_sha256'],
        sample_sha256=sha(candidate/'sample.jsonl'), full_text_read=True, human_attestation=False,
        training_approved=False, review_mode='delegated_expert', judgment='consider' if i < 25 else 'exclude' if i < 36 else 'defer',
        reason='Synthetic fixture decision only; never a statement about actual source quality or human review.')
        for i, s in enumerate(samples)]
    review = tmp_path/'review'
    review.mkdir()
    (review/'direct-judgments.jsonl').write_text(''.join(canonical(d)+'\n' for d in journal))
    correction = dict(index=63, example_id=journal[63]['example_id'], record_sha256=journal[63]['record_sha256'],
        original_judgment='defer', judgment='exclude', reason='Synthetic fixture amendment; retained original decision is never overwritten in the journal.',
        primary_references=['https://example.invalid'])
    amendment = dict(version=1, prior_journal_sha256=sha(review/'direct-judgments.jsonl'), review_mode='delegated_expert',
                     human_attestation=False, training_approved=False, amendments=[correction])
    dump(review/'amendments.json', amendment)
    refs = dict(references=[])
    dump(review/'reference-verification.json', refs)
    effective = deepcopy(journal)
    effective[63].update(judgment='exclude', reason=correction['reason'], primary_references=correction['primary_references'])
    rr = tmp_path/'review-report.json'
    dump(rr, dict(effective_decisions=effective, candidate_manifest_sha256=sha(candidate/'manifest.json'),
                  references=refs, references_sha256=sha(review/'reference-verification.json')))
    template = Path(__file__).parents[1]/'configs/iteration-three-sft-research-admission-v1.json'
    policy = json.loads(template.read_text())
    policy.update(source_record_sha256=digest(asdict(source)), candidate_manifest_sha256=sha(candidate/'manifest.json'),
        candidate_file_sha256=sha(candidate/'candidates.jsonl'), sample_sha256=sha(candidate/'sample.jsonl'),
        journal_sha256=sha(review/'direct-judgments.jsonl'), amendments_sha256=sha(review/'amendments.json'),
        review_report_sha256=sha(rr))
    kept = rows[:25]+rows[64:]
    policy['retained_membership_sha256'] = digest([dict(example_id=r['example_id'], record_sha256=digest(r), split=r['split'],
        split_group=r['validation_results']['split_group']) for r in kept])
    policy['selection'].update(expected_rows=dict(train=26, validation=1, test=1), unread_train=1, individually_considered_train=25)
    policy_file = tmp_path/'policy.json'
    dump(policy_file, policy)
    return dict(rows=rows, samples=samples, journal=journal, amendment=amendment, policy=policy, candidate=candidate,
                review=review, source=source_dir, policy_file=policy_file, report=rr, tokenizer=tok)


def publish(f, output):
    return release(f['candidate'], f['review'], f['source'], f['policy_file'], output, review_report=f['report'])


def test_exact_selection_blocks_deferrals_and_preserves_unread_identity(fixture):
    f = fixture
    retained, effective, considered = select(f['rows'], f['samples'], f['journal'], f['amendment'], f['policy'])
    assert len(retained) == 28 and len(considered) == 25
    assert retained[-3:] == f['rows'][64:] and effective[63]['judgment'] == 'exclude'
    assert f['journal'][63]['judgment'] == 'defer'


@pytest.mark.parametrize('field,value', [('training_ready', True), ('human_attestation', True),
                                       ('allowed_training_devices', ['torch:cuda']), ('status', 'production')])
def test_authority_and_device_expansion_refused(fixture, field, value):
    p = deepcopy(fixture['policy'])
    p[field] = value
    with pytest.raises(ValueError): checked_policy(p)


@pytest.mark.parametrize('key', ['physical_data_positions', 'optimizer_updates', 'max_physical_passes_per_group',
                               'max_context', 'max_parameters', 'synthetic_preflight_gradient_positions'])
def test_limits_cannot_expand_or_be_booleans(fixture, key):
    p = deepcopy(fixture['policy'])
    p['limits'][key] += 1
    with pytest.raises(ValueError): checked_policy(p)
    p['limits'][key] = True
    with pytest.raises(ValueError): checked_policy(p)


@pytest.mark.parametrize('field,value', [('index', True), ('training_approved', True), ('human_attestation', True),
                                       ('full_text_read', False), ('record_sha256', '0'*64), ('reason', '')])
def test_review_elevation_or_unbound_decision_refused(fixture, field, value):
    f = fixture
    journal = deepcopy(f['journal'])
    journal[0][field] = value
    with pytest.raises(ValueError): select(f['rows'], f['samples'], journal, f['amendment'], f['policy'])


def test_extra_or_repartitioned_candidates_and_missing_reviews_refused(fixture):
    f = fixture
    for rows, journal in [(f['rows']+[f['rows'][0]], f['journal']), (f['rows'], f['journal'][:-1])]:
        with pytest.raises(ValueError): select(rows, f['samples'], journal, f['amendment'], f['policy'])
    rows = deepcopy(f['rows'])
    rows[-1]['split'] = 'train'
    with pytest.raises(ValueError): select(rows, f['samples'], f['journal'], f['amendment'], f['policy'])


def test_release_tokens_and_original_reader_boundary(fixture, tmp_path):
    f = fixture
    output = tmp_path/'release'
    result = publish(f, output)
    assert result['counts'] == dict(train=26, validation=1, test=1)
    ph = sha(f['policy_file'])
    with open_research(output, ph) as checked:
        assert len(checked) == 26
        rows = list(checked.values())
        assert sum(r['validation_results']['sft_research_admission']['individually_read'] for r in rows) == 25
        assert all(r['validation_results']['sft_research_admission']['individual_quality_verified'] is False for r in rows)
    with pytest.raises(ValueError):
        with open_checked(output): pass
    tokens = tmp_path/'tokens'
    report = build_tokens(output, f['tokenizer'], tokens, ph, context_length=256, shard_positions=512)
    with ShardBatches(tokens, f['tokenizer']) as batches:
        assert len(batches) == 26
        assert batches.counts(26) == (report['processed_prediction_positions'], report['supervised_positions'])
    assert report['cross_document_attention'] is False and report['implicit_wraparound'] is False
    with pytest.raises(FileExistsError): publish(f, output)


def test_pinned_policy_and_rehashed_released_text_mutation_refused(fixture, tmp_path):
    f = fixture
    root = tmp_path/'release'
    publish(f, root)
    with pytest.raises(ValueError):
        with open_research(root, '0'*64): pass
    shard = root/'train-000000.jsonl'
    rows = [json.loads(l) for l in shard.read_text().splitlines()]
    rows[0]['messages'][-1]['content'] = 'Invented unapproved training target.'
    shard.write_text(''.join(canonical(r)+'\n' for r in rows))
    manifest = json.loads((root/'manifest.json').read_text())
    manifest['files'][shard.name] = sha(shard)
    dump(root/'manifest.json', manifest)
    with pytest.raises(ValueError, match='Released records differ'):
        with open_research(root, sha(f['policy_file'])): pass


def test_preparation_refuses_foundation_overlong_and_budget_excess(fixture, tmp_path):
    f = fixture
    root = tmp_path/'release'
    publish(f, root)
    for kwargs in (dict(objective='foundation'), dict(context_length=4096), dict(context_length=1),
                   dict(max_positions=1048577), dict(max_positions=1)):
        out = tmp_path/'refused'
        with pytest.raises(ValueError): build_tokens(root, f['tokenizer'], out, sha(f['policy_file']), **kwargs)
        assert not out.exists()


def test_amendment_cannot_promote_deferral_or_change_original_history(fixture):
    f = fixture
    for key, value in [('judgment', 'consider'), ('original_judgment', 'consider'), ('index', True)]:
        amendment = deepcopy(f['amendment'])
        amendment['amendments'][0][key] = value
        with pytest.raises(ValueError): select(f['rows'], f['samples'], f['journal'], amendment, f['policy'])


def test_modified_review_cannot_be_accepted_by_rehashing_release_manifest(fixture, tmp_path):
    f = fixture
    root = tmp_path/'release'
    publish(f, root)
    path = root/'direct-judgments.jsonl'
    path.write_text(path.read_text().replace('"judgment":"exclude"', '"judgment":"consider"', 1))
    manifest = json.loads((root/'manifest.json').read_text())
    manifest['files'][path.name] = sha(path)
    dump(root/'manifest.json', manifest)
    with pytest.raises(ValueError, match='Pinned candidate/review payload'):
        with open_research(root, sha(f['policy_file'])): pass


def test_live_artifact_mutation_is_refused_on_exit(fixture, tmp_path):
    f = fixture
    root = tmp_path/'release'
    publish(f, root)
    with pytest.raises(ValueError):
        with open_research(root, sha(f['policy_file'])):
            # Mutate an existing pinned payload; no training can silently outlive its source.
            (root/'source-card.txt').write_text('Changed while open.')


def test_live_artifact_extra_file_is_refused_on_exit(fixture, tmp_path):
    f = fixture
    root = tmp_path/'release'
    publish(f, root)
    with pytest.raises(ValueError):
        with open_research(root, sha(f['policy_file'])):
            (root/'extra.txt').write_text('Unexpected extra artifact.')


def test_wrong_candidate_tokenizer_refused_without_output(fixture, tmp_path):
    f = fixture
    root = tmp_path/'release'
    publish(f, root)
    other = tmp_path/'other-tokenizer'
    train_core(['Different synthetic tokenizer context.']*10, 512).save(other, {'scope': 'synthetic'})
    with pytest.raises(ValueError, match='Original candidate tokenizer'):
        build_tokens(root, other, tmp_path/'tokens', sha(f['policy_file']))
    assert not (tmp_path/'tokens').exists()
