"""Separate pinned, bounded SFT research release; original readers stay unchanged."""
# Creator: Navneet Prabhakar
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from slm.data.build import read_source, verify
from slm.data.holdout import check_training_context
from slm.data.oasst_sft_screen import RULE
from slm.data.research_admission import bundle
from slm.data.review_stream import DEFAULT_LIMITS, Index, guarded, lines
from slm.data.schema import digest
from slm.data.staging import canonical, metadata
from slm.data.tokenized import sha

KIND = 'rated-oasst-bounded-sft-research-v1'
FIELDS = set('version kind status training_ready scope review_mode human_attestation authorized_by authorization_instruction '
             'source source_record_sha256 source_evidence_decision candidate_manifest_sha256 candidate_file_sha256 '
             'sample_sha256 journal_sha256 amendments_sha256 review_report_sha256 eligibility_rule_sha256 '
             'retained_membership_sha256 selection limits allowed_training_devices prohibited_uses '
             'required_before_training risk_acceptance implementation_boundary'.split())
CAPS = dict(physical_data_positions=1048576, optimizer_updates=4096, max_physical_passes_per_group=3,
            max_parameters=100000000, max_context=2048, synthetic_preflight_gradient_positions=16384)
BOUNDS = {**DEFAULT_LIMITS, 'max_records': 3000, 'max_input_bytes': 64*1024**2}


def checked_policy(policy):
    if (set(policy) != FIELDS or type(policy['version']) is not int or policy['version'] != 1
            or policy['kind'] != KIND or policy['status'] != 'accepted_for_bounded_research'
            or policy['training_ready'] is not False or policy['human_attestation'] is not False
            or policy['scope'] != 'local_conversation_sft_pilot' or policy['review_mode'] != 'delegated_expert'
            or policy['authorized_by'] != 'Navneet Prabhakar' or policy['source'] != 'OpenAssistant/oasst2'
            or policy['allowed_training_devices'] != ['mlx:default', 'torch:cpu']
            or policy['eligibility_rule_sha256'] != digest(RULE)):
        raise ValueError('Exact delegated bounded SFT policy required')
    for key, value in policy.items():
        if key.endswith('sha256') and (not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value)):
            raise ValueError('Pinned policy digest required')
    if set(policy['limits']) != set(CAPS) or any(type(v) is not int or not 1 <= v <= CAPS[k]
                                                for k, v in policy['limits'].items()):
        raise ValueError('SFT research limits exceed allowed ceilings')
    selection = policy['selection']
    expected = {'remove_all_observed_exclude_and_defer_groups', 'retain_original_text_splits_groups',
                'one_path_per_group', 'merge_prior_explicit_releases', 'source_rule_changes_require_new_policy',
                'expected_rows', 'individually_considered_train', 'unread_train'}
    if (set(selection) != expected or selection['merge_prior_explicit_releases'] is not False
            or any(selection[k] is not True for k in expected-set(('expected_rows', 'individually_considered_train',
                                                                  'unread_train', 'merge_prior_explicit_releases')))):
        raise ValueError('Exact research selection contract required')
    counts = selection['expected_rows']
    if (set(counts) != {'train', 'validation', 'test'} or any(type(v) is not int or not 1 <= v <= 1500 for v in counts.values())
            or any(type(selection[k]) is not int or selection[k] < 0 for k in ('unread_train', 'individually_considered_train'))
            or selection['unread_train']+selection['individually_considered_train'] != counts['train']):
        raise ValueError('Bounded research selection counts differ')
    for name in ('authorization_instruction', 'source_evidence_decision', 'risk_acceptance', 'implementation_boundary'):
        if not isinstance(policy[name], str) or len(policy[name].strip()) < 40:
            raise ValueError('Explicit research authority/evidence/risk boundary required')
    if (not isinstance(policy['required_before_training'], list) or len(policy['required_before_training']) != 6
            or not all(isinstance(v, str) and v.strip() for v in policy['required_before_training'])
            or policy['prohibited_uses'] != ['cloud_training_under_validation_budget', 'production_or_public_distribution',
                                             'automatic_teacher_admission', 'claims_of_individual_quality_verification_for_unread_rows']):
        raise ValueError('Research restrictions required')


def select(candidates, samples, journal, amendments, policy):
    """Reconstruct membership from a trusted pinned pool; never infer individual approval."""
    checked_policy(policy)
    population = {}
    groups = set()
    for row in candidates:
        eid = row['example_id']
        gid = row['validation_results']['split_group']
        if (eid in population or gid in groups or row['source'] != policy['source']
                or not isinstance(gid, str) or not re.fullmatch('[a-f0-9]{64}', gid)
                or row['license_record'] != policy['source_record_sha256']
                or row['split'] not in ('train', 'validation', 'test')
                or not row['messages'] or row['messages'][-1]['role'] != 'assistant'):
            raise ValueError('Candidate identity/source/group/shape differs')
        population[eid] = row
        groups.add(gid)
    if len(samples) != 64 or len(journal) != 64:
        raise ValueError('All 64 direct decisions required')
    effective = deepcopy(journal)
    reviewed = set()
    for i, (sample, decision) in enumerate(zip(samples, effective)):
        row = sample['record']
        if (type(sample['index']) is not int or sample['index'] != i or type(decision['index']) is not int
                or decision['index'] != i or sample['record_sha256'] != digest(row)
                or row != population.get(row['example_id']) or row['split'] != 'train'
                or row['example_id'] in reviewed or decision['example_id'] != row['example_id']
                or decision['record_sha256'] != digest(row) or decision['sample_sha256'] != policy['sample_sha256']
                or decision['full_text_read'] is not True or decision['human_attestation'] is not False
                or decision['training_approved'] is not False or decision['review_mode'] != 'delegated_expert'
                or decision['judgment'] not in ('consider', 'exclude', 'defer')
                or not isinstance(decision['reason'], str) or len(decision['reason'].strip()) < 40):
            raise ValueError('Direct review identity/authority/meaning differs')
        reviewed.add(row['example_id'])
    if (type(amendments['version']) is not int or amendments['version'] != 1
            or amendments['prior_journal_sha256'] != policy['journal_sha256']
            or amendments['review_mode'] != 'delegated_expert' or amendments['human_attestation'] is not False
            or amendments['training_approved'] is not False):
        raise ValueError('Amendment authority/binding differs')
    changed = set()
    for correction in amendments['amendments']:
        index = correction['index']
        if type(index) is not int or not 0 <= index < 64 or index in changed:
            raise ValueError('Duplicate or invalid amendment index')
        old = effective[index]
        if (correction['example_id'] != old['example_id'] or correction['record_sha256'] != old['record_sha256']
                or correction['original_judgment'] != old['judgment'] or correction['judgment'] != 'exclude'
                or not isinstance(correction['reason'], str) or len(correction['reason'].strip()) < 40):
            raise ValueError('Amendment history differs; only explicit exclusion supported')
        changed.add(index)
        old.update(judgment='exclude', reason=correction['reason'], primary_references=correction['primary_references'])
    blocked = {samples[i]['record']['validation_results']['split_group'] for i, d in enumerate(effective)
               if d['judgment'] != 'consider'}
    retained = [row for row in candidates if row['validation_results']['split_group'] not in blocked]
    membership = [dict(example_id=row['example_id'], record_sha256=digest(row), split=row['split'],
                       split_group=row['validation_results']['split_group']) for row in retained]
    counts = dict(Counter(row['split'] for row in retained))
    considered = {d['example_id'] for d in effective if d['judgment'] == 'consider'}
    if (digest(membership) != policy['retained_membership_sha256'] or counts != policy['selection']['expected_rows']
            or len(considered) != policy['selection']['individually_considered_train']
            or sum(row['split'] == 'train' and row['example_id'] not in reviewed for row in retained)
               != policy['selection']['unread_train']):
        raise ValueError('Retained membership/counts differ from pinned decision')
    return retained, effective, considered


def populate(root, index, policy_hash):
    if sha(root/'research-policy.json') != policy_hash:
        raise ValueError('Pinned policy file differs')
    policy = metadata(root/'research-policy.json')
    checked_policy(policy)
    bundle(root, 'candidate-', policy['candidate_manifest_sha256'])
    for name, field in [('candidate-candidates.jsonl', 'candidate_file_sha256'), ('candidate-sample.jsonl', 'sample_sha256'),
                        ('direct-judgments.jsonl', 'journal_sha256'), ('amendments.json', 'amendments_sha256'),
                        ('review-report.json', 'review_report_sha256')]:
        if sha(root/name) != policy[field]:
            raise ValueError('Pinned candidate/review payload differs')
    source = read_source(root/'source.json')
    if source.source_id != policy['source'] or source.license_id != 'apache-2.0' or digest(source.__dict__) != policy['source_record_sha256']:
        raise ValueError('Source/card/license evidence differs')
    measured = metadata(root/'candidate-report.json')
    if digest(measured['rule']) != policy['eligibility_rule_sha256'] or measured['training_eligible'] is not False:
        raise ValueError('Candidate selection rule differs')
    candidates = list(lines(root/'candidate-candidates.jsonl', BOUNDS))
    samples = list(lines(root/'candidate-sample.jsonl', BOUNDS))
    journal = list(lines(root/'direct-judgments.jsonl', BOUNDS))
    retained, effective, considered = select(candidates, samples, journal, metadata(root/'amendments.json'), policy)
    review = metadata(root/'review-report.json')
    if review['effective_decisions'] != effective or review['candidate_manifest_sha256'] != policy['candidate_manifest_sha256']:
        raise ValueError('Direct report reconciliation differs')
    if sha(root/'reference-verification.json') != review['references_sha256']:
        raise ValueError('Primary reference verification differs')
    references = metadata(root/'reference-verification.json')
    if references != review['references']:
        raise ValueError('Primary reference metadata differs')
    for i, reference in enumerate(references['references']):
        if sha(root/f'reference-{i:02d}.bin') != reference['sha256']:
            raise ValueError('Pinned primary reference bytes differ')
    counts = Counter()
    for row in retained:
        if row['source_revision'] != source.revision:
            raise ValueError('Candidate source revision differs')
        item = deepcopy(row)
        item['validation_results']['sft_research_admission'] = dict(kind=KIND, policy_file_sha256=policy_hash,
            original_record_sha256=digest(row), individually_read=item['example_id'] in considered,
            individual_quality_verified=False, human_attestation=False, review_mode='delegated_expert',
            scope=policy['scope'], objective='sft', assessment='Bounded corpus research with residual noise; not factual gold.')
        if item['split'] == 'train':
            check_training_context(item['messages'], (item['example_id'], item['parent_group_id'], item['validation_results']['split_group']))
        index.db.execute('INSERT INTO approved(eid,data,gid,split) VALUES(?,?,?,?)',
                         (item['example_id'], canonical(item), item['validation_results']['split_group'], item['split']))
        index.tick()
        counts[item['split']] += 1
    index.db.commit()
    index.research_limits = policy['limits']
    index.research_scope = policy['scope']
    return dict(counts=dict(counts), policy_file_sha256=policy_hash, individually_considered_train=len(considered),
                unread_train=policy['selection']['unread_train'], training_recipe_ready=False,
                scope=policy['scope'], human_attestation=False)


@contextmanager
def open_research(root, policy_hash):
    root = Path(root)
    manifest = metadata(root/'manifest.json')
    if (manifest.get('release') != 'research_training' or manifest.get('review_schema_version') != 5
            or manifest.get('kind') != KIND or manifest.get('policy_file_sha256') != policy_hash
            or manifest.get('reader_sha256') != sha(__file__)):
        raise ValueError('Pinned SFT research v5 release required')
    check = guarded([root], BOUNDS)
    self_stamp = sha(__file__)
    verify(root)
    expected_files = set(manifest['files']) | {'manifest.json'}
    def stable():
        check()
        if ({p.name for p in root.iterdir()} != expected_files
                or any(not p.is_file() or p.is_symlink() for p in root.iterdir())
                or sha(__file__) != self_stamp):
            raise ValueError('SFT research files or implementation changed')
    with tempfile.TemporaryDirectory(prefix='slm-sft-research-check-') as temp:
        index = Index(Path(temp)/'index.sqlite', BOUNDS)
        try:
            populate(root, index, policy_hash)
            index.shard_rows(root, 'released')
            stable()
            yield index
            stable()
        finally:
            index.db.close()


def release(candidates, review, snapshot, policy_file, output, *, review_report):
    candidates, review, snapshot, policy_file, output = map(Path, (candidates, review, snapshot, policy_file, output))
    if output.exists():
        raise FileExistsError(output)
    policy = metadata(policy_file)
    checked_policy(policy)
    verify(candidates)
    if sha(candidates/'manifest.json') != policy['candidate_manifest_sha256']:
        raise ValueError('Candidate pool differs')
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.sft-research-release-', dir=output.parent))
    index = None
    try:
        for path in candidates.iterdir():
            if not path.is_file() or path.is_symlink():
                raise ValueError('Flat candidate snapshot required')
            shutil.copyfile(path, temp/('candidate-'+path.name))
        for name in ('direct-judgments.jsonl', 'amendments.json'):
            shutil.copyfile(review/name, temp/name)
        shutil.copyfile(policy_file, temp/'research-policy.json')
        shutil.copyfile(review_report, temp/'review-report.json')
        shutil.copyfile(review/'reference-verification.json', temp/'reference-verification.json')
        references = metadata(review/'reference-verification.json')
        for i, reference in enumerate(references['references']):
            path = Path(reference['path'])
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Bounded relative reference path required')
            shutil.copyfile(review/path, temp/f'reference-{i:02d}.bin')
        read_source(snapshot/'source.json')
        source = metadata(snapshot/'source.json')
        for label in ('card', 'license'):
            shutil.copyfile(snapshot/source['evidence_files'][label], temp/('source-'+label+'.txt'))
        source['evidence_files'].update(card='source-card.txt', license='source-license.txt')
        (temp/'source.json').write_text(canonical(source)+'\n')
        policy_hash = sha(policy_file)
        with tempfile.TemporaryDirectory(prefix='slm-sft-publish-') as work:
            index = Index(Path(work)/'index.sqlite', BOUNDS)
            result = populate(temp, index, policy_hash)
            for split in ('train', 'validation', 'test'):
                with (temp/(split+'-000000.jsonl')).open('w') as out:
                    for data, in index.db.execute('SELECT data FROM approved WHERE split=? ORDER BY eid', (split,)):
                        out.write(data+'\n')
            index.db.close()
            index = None
        (temp/'report.json').write_text(canonical(result)+'\n')
        manifest = dict(version=1, release='research_training', review_schema_version=5, kind=KIND,
                        policy_file_sha256=policy_hash, reader_sha256=sha(__file__),
                        files={p.name: sha(p) for p in sorted(temp.iterdir())})
        (temp/'manifest.json').write_text(canonical(manifest)+'\n')
        with open_research(temp, policy_hash) as checked:
            if len(checked) != policy['selection']['expected_rows']['train']:
                raise ValueError('Published train count differs')
        if sha(policy_file) != policy_hash or sha(candidates/'manifest.json') != policy['candidate_manifest_sha256']:
            raise ValueError('Publication source identity changed')
        os.rename(temp, output)
        return result
    except BaseException:
        if index is not None:
            index.db.close()
        shutil.rmtree(temp, ignore_errors=True)
        raise
