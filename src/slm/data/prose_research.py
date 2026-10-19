"""Separate finite prose research reader; pinned membership is the trust boundary.

Rechecks exact admitted records and their retained evidence. It does not rerun
the historical global duplicate analysis or independently certify review claims.
"""
# Creator: Navneet Prabhakar
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
import re
import shutil
import tempfile

from slm.data.build import read_source, verify
from slm.data.prose_screen import RequestGuard
from slm.data.review_stream import Index, guarded, lines
from slm.data.schema import digest
from slm.data.staging import canonical, metadata
from slm.data.tokenized import sha

KIND = 'fineweb-finite-prose-research-v1'
FIELDS = frozenset(('authorization_instruction authorized_by commoncrawl_terms_sha256 creator directly_considered_train '
    'expected_rows human_attestation kind limits prior_journal_sha256 prohibited_uses required_before_gradients '
    'retained_membership_sha256 review_journal_sha256 review_mode review_report_sha256 risk_acceptance schema_version '
    'scope screen_report_sha256 selection source source_evidence_decision staged_manifest_sha256 status '
    'training_devices training_ready unread_train version').split())
CAPS = dict(physical_data_positions=2000000, optimizer_updates=4096,
            max_physical_passes_per_group=2, max_parameters=100000000, max_context=2048)
BOUNDS = dict(max_input_bytes=64 * 1024**2, max_records=2000,
              max_record_bytes=1024**2, max_db_bytes=64 * 1024**2)
EVIDENCE = frozenset(('membership.json', 'screen-plan.json', 'screen-report.json', 'protected-requests.json',
    'raw-prefix.jsonl', 'raw-distributed.jsonl', 'prior-judgments.jsonl', 'direct-judgments.jsonl',
    'review-report.json', 'staged-manifest.json', 'ancestor-heldouts.json', 'source.json',
    'source-card.txt', 'source-license.txt', 'commoncrawl-terms.html', 'reference-receipt.json',
    'review-packet.jsonl', 'prior-review-packet.jsonl'))


def require(condition, reason):
    if not condition: raise ValueError(reason)


def checked_policy(policy):
    require(set(policy) == FIELDS and policy.get('creator') == 'Navneet Prabhakar'
            and policy.get('version') == 1 and type(policy['version']) is int and policy.get('kind') == KIND
            and policy.get('schema_version') == 6 and type(policy['schema_version']) is int
            and policy.get('status') == 'accepted_for_bounded_private_research'
            and policy.get('training_ready') is False and policy.get('human_attestation') is False
            and policy.get('review_mode') == 'delegated_expert'
            and policy.get('authorized_by') == 'Navneet Prabhakar'
            and policy.get('training_devices') == ['mlx:default', 'torch:cpu'], 'Finite delegated local prose policy required')
    require(set(policy['limits']) == set(CAPS) and all(type(v) is int and 1 <= v <= CAPS[k]
            for k, v in policy['limits'].items()), 'Prose research ceilings exceeded')
    require(policy['selection'] == dict(exact_existing_membership_only=True,
            remove_all_known_exclusions_and_deferrals=True, preserve_original_groups_splits_and_text=True,
            retain_all_ancestral_heldout_protection=True, automatic_source_expansion=False), 'Exact selection boundary required')
    require(all(type(value) is bool for value in policy['selection'].values()), 'Boolean selection flags required')
    counts = policy['expected_rows']
    require(set(counts) == {'train', 'validation', 'test'} and all(type(v) is int and 1 <= v <= 1500 for v in counts.values())
            and sum(counts.values()) <= BOUNDS['max_records'], 'Finite positive partition counts required')
    require(all(type(policy[k]) is int and policy[k] >= 0 for k in ('directly_considered_train', 'unread_train'))
            and policy['directly_considered_train'] + policy['unread_train'] == counts['train'], 'Read/unread counts differ')
    for name, value in policy.items():
        if name.endswith('sha256'):
            require(isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value), 'Pinned evidence hashes required')
    for name in ('scope', 'authorization_instruction', 'source_evidence_decision', 'risk_acceptance'):
        require(isinstance(policy[name], str) and len(policy[name].strip()) >= 40, 'Explicit research authority/risk/scope required')
    require(isinstance(policy['required_before_gradients'], list) and len(policy['required_before_gradients']) >= 6
            and isinstance(policy['prohibited_uses'], list) and len(policy['prohibited_uses']) >= 6, 'Research restrictions required')


def populate(root, index, policy_hash):
    require(sha(root / 'research-policy.json') == policy_hash, 'External policy binding differs')
    policy = metadata(root / 'research-policy.json'); checked_policy(policy)
    for filename, field in (('membership.json', 'retained_membership_sha256'), ('screen-report.json', 'screen_report_sha256'),
            ('review-report.json', 'review_report_sha256'), ('direct-judgments.jsonl', 'review_journal_sha256'),
            ('prior-judgments.jsonl', 'prior_journal_sha256'), ('staged-manifest.json', 'staged_manifest_sha256'),
            ('commoncrawl-terms.html', 'commoncrawl_terms_sha256')):
        require(sha(root / filename) == policy[field], 'Pinned prose evidence differs: ' + filename)
    source_meta = metadata(root / 'source.json')
    require(source_meta['evidence_files'] == dict(card='source-card.txt', license='source-license.txt'), 'Fixed local source evidence names required')
    source = read_source(root / 'source.json')
    require(metadata(root / 'research-policy.json')['source'] == {k: v for k, v in source_meta.items() if k != 'evidence_files'}
            and source.source_id == 'HuggingFaceFW/fineweb-edu' and source.license_id == 'odc-by'
            and source.review_status == 'sample_only', 'Prose source/card/license status differs')
    screen_report, screen_plan = metadata(root / 'screen-report.json'), metadata(root / 'screen-plan.json')
    require(sha(root / 'screen-plan.json') == screen_report['plan_sha256'], 'Screen plan differs')
    raw = {}
    for name, suffix in (('raw-prefix.jsonl', 'fineweb-parquet-rowgroup-audit-v1/rows.jsonl'),
                         ('raw-distributed.jsonl', 'fineweb-prose-distributed-audit-v1/rows.jsonl')):
        expected = [value for key, value in screen_plan['input_bindings'].items() if key.endswith(suffix)]
        require(expected == [sha(root / name)], 'Raw acquisition binding differs')
        for item in lines(root / name, BOUNDS):
            group = item['source_group']; row = item['row']
            require(group == source.source_id + ':' + row['id'] and digest(row) == item['raw_record_sha256'], 'Raw source identity differs')
            require(group not in raw or raw[group] == row, 'Conflicting duplicate raw identity')
            raw[group] = row
    guard = RequestGuard(metadata(root / 'protected-requests.json'))
    require(guard.fingerprint == screen_plan['protected_request_fingerprint'], 'Protected request set differs')
    parent = metadata(root / 'staged-manifest.json')
    require(sha(root / 'ancestor-heldouts.json') == parent['files']['heldout-groups.json'], 'Global heldout protection differs')
    heldouts = metadata(root / 'ancestor-heldouts.json')
    require(all(value in ('validation', 'test') for value in heldouts.values()), 'Invalid ancestral partition')
    decisions = {}
    for journal_name, packet_name, count in (('prior-judgments.jsonl', 'prior-review-packet.jsonl', 16),
                                             ('direct-judgments.jsonl', 'review-packet.jsonl', 32)):
        journal, packet = list(lines(root / journal_name, BOUNDS)), list(lines(root / packet_name, BOUNDS))
        require(len(journal) == len(packet) == count, 'Complete original review packet/journal required')
        for i, (decision, original) in enumerate(zip(journal, packet)):
            group = decision['source_group']
            require(type(decision['index']) is int and decision['index'] == original['index'] == i
                    and original['source_group'] == group and group not in decisions
                    and decision['raw_record_sha256'] == original['raw_record_sha256'] == digest(raw[group])
                    and original['row'] == raw[group] and decision['review_file_sha256'] == sha(root / packet_name)
                    and decision['judgment'] in ('consider', 'exclude', 'defer') and decision['full_text_read'] is True
                    and decision['human_attestation'] is False and decision['training_approved'] is False
                    and decision['factual_accuracy_verified'] is False and decision['underlying_document_rights_verified'] is False
                    and decision['review_mode'] == 'delegated_expert' and len(decision['reason'].strip()) >= 40,
                    'Direct decision/raw packet binding differs')
            decisions[group] = decision['judgment']
    review = metadata(root / 'review-report.json')
    require(sha(root / 'reference-receipt.json') == review['primary_reference_receipt_sha256'], 'Specific primary-reference receipt differs')
    membership = metadata(root / 'membership.json')
    originals = list(lines(root / 'original-records.jsonl', BOUNDS))
    require(len(membership) == len(originals) == sum(policy['expected_rows'].values()), 'Exact admitted row count required')
    expected = [dict(example_id=r['example_id'], source_group=r['parent_group_id'], split=r['split'],
                    split_group=r['validation_results']['split_group'], canonical_record_sha256=digest(r)) for r in originals]
    require(expected == membership and [r['example_id'] for r in originals] == sorted({r['example_id'] for r in originals}), 'Original admitted membership differs')
    counts = Counter(); considered = 0; groups = {}
    for row in originals:
        group, split = row['parent_group_id'], row['split']; record = raw.get(group)
        require(row['example_id'] == group and row['source'] == source.source_id and row['source_revision'] == source.revision
                and row['license_record'] == digest(source.__dict__) and record is not None
                and decisions.get(group) not in ('exclude', 'defer')
                and split in ('train', 'validation', 'test') and row['task'] == 'prose'
                and row['content_category'] == 'unreviewed' and len(row['messages']) == 1
                and set(row['messages'][0]) == {'role', 'content'} and row['messages'][0]['role'] == 'text'
                and row['upstream_references'] == [record['url']], 'Admitted prose shape/source/review differs')
        gid = row['validation_results']['split_group']
        require(isinstance(gid, str) and re.fullmatch('[a-f0-9]{64}', gid)
                and (gid not in groups or groups[gid] == split), 'Related records cross partitions')
        groups[gid] = split
        if split == 'train':
            require(group not in heldouts and row['messages'][0]['content'] == record['text']
                    and not guard.matches(record['text']) and not re.search(r'eval-(?:tools-)?v1/', record['text'], re.I), 'Train text/heldout/request isolation differs')
            require(row['validation_results']['prose_candidate_screen']['raw_record_sha256'] == digest(record), 'Train raw-screen lineage differs')
            considered += decisions.get(group) == 'consider'
        else:
            require(heldouts.get(group) == split, 'Original heldout family partition differs')
        item = deepcopy(row)
        item['validation_results']['prose_research_admission'] = dict(policy_file_sha256=policy_hash,
            original_record_sha256=digest(row), raw_record_sha256=digest(record), individually_read=group in decisions,
            individual_quality_verified=False, human_attestation=False, training_recipe_ready=False, objective='foundation')
        index.db.execute('INSERT INTO approved(eid,data,gid,split) VALUES(?,?,?,?)',
                         (item['example_id'], canonical(item), gid, split))
        index.tick(); counts[split] += 1
    require(dict(counts) == policy['expected_rows'] and considered == policy['directly_considered_train'], 'Admitted source/read counts differ')
    index.db.commit(); index.research_limits = policy['limits']; index.research_scope = policy['scope']
    index.prose_metadata = {group: {k: v for k, v in record.items() if k != 'text'} for group, record in raw.items()}
    return dict(creator='Navneet Prabhakar', counts=dict(counts), directly_considered_train=considered,
                unread_train=counts['train'] - considered, training_recipe_ready=False,
                scope='Exact finite private prose ingredient; no capability, factual/privacy/rights certification or training launch.')


@contextmanager
def open_research(root, policy_hash):
    root = Path(root); manifest = metadata(root / 'manifest.json')
    require(manifest.get('release') == 'research_training' and manifest.get('review_schema_version') == 6
            and manifest.get('kind') == KIND and manifest.get('policy_file_sha256') == policy_hash
            and manifest.get('reader_sha256') == sha(__file__), 'Separate pinned prose research v6 reader required')
    required = EVIDENCE | {'original-records.jsonl', 'research-policy.json', 'report.json'} | {s + '-000000.jsonl' for s in ('train', 'validation', 'test')}
    require(set(manifest['files']) == required, 'Exact flat prose evidence/release file set required')
    check = guarded([root], BOUNDS); reader_hash = sha(__file__); guard_hash = sha(Path(__file__).with_name('prose_screen.py'))
    require(manifest.get('request_guard_sha256') == guard_hash, 'Prose request-guard implementation differs')
    verify(root)
    def stable():
        check()
        require({p.name for p in root.iterdir()} == required | {'manifest.json'} and sha(__file__) == reader_hash
                and sha(Path(__file__).with_name('prose_screen.py')) == guard_hash, 'Prose release or implementation changed')
    with tempfile.TemporaryDirectory(prefix='slm-prose-research-check-') as work:
        index = Index(Path(work) / 'index.sqlite', BOUNDS)
        try:
            result = populate(root, index, policy_hash)
            require(metadata(root / 'report.json') == result, 'Research report differs')
            index.shard_rows(root, 'released'); stable()
            yield index
            stable()
        finally: index.db.close()


def release(staged, policy_file, evidence, output):
    staged, policy_file, output = map(Path, (staged, policy_file, output))
    require(set(evidence) == EVIDENCE, 'Complete explicit prose evidence bindings required')
    if output.exists(): raise FileExistsError(output)
    policy = metadata(policy_file); checked_policy(policy); verify(staged)
    require(sha(staged / 'manifest.json') == policy['staged_manifest_sha256'], 'Staged source differs')
    policy_hash = sha(policy_file)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.prose-research-release-', dir=output.parent))
    try:
        for name, path in evidence.items():
            require(Path(path).is_file() and not Path(path).is_symlink(), 'Regular evidence files required')
            shutil.copyfile(path, temp / name)
        shutil.copyfile(policy_file, temp / 'research-policy.json')
        wanted = {r['example_id'] for r in metadata(temp / 'membership.json')}
        selected = [row for split in ('train', 'validation', 'test') for path in sorted(staged.glob(split + '-*.jsonl'))
                    for row in lines(path, BOUNDS) if row['example_id'] in wanted]
        with (temp / 'original-records.jsonl').open('w') as out:
            for row in sorted(selected, key=lambda r: r['example_id']): out.write(canonical(row) + '\n')
        guarded([temp], BOUNDS)()
        with tempfile.TemporaryDirectory(prefix='slm-prose-publish-') as work:
            index = Index(Path(work) / 'index.sqlite', BOUNDS)
            try:
                result = populate(temp, index, policy_hash)
                for split in ('train', 'validation', 'test'):
                    with (temp / (split + '-000000.jsonl')).open('w') as out:
                        for data, in index.db.execute('SELECT data FROM approved WHERE split=? ORDER BY eid', (split,)):
                            out.write(data + '\n')
            finally: index.db.close()
        (temp / 'report.json').write_text(canonical(result) + '\n')
        manifest = dict(version=1, release='research_training', review_schema_version=6, kind=KIND,
                        policy_file_sha256=policy_hash, reader_sha256=sha(__file__),
                        request_guard_sha256=sha(Path(__file__).with_name('prose_screen.py')),
                        files={p.name: sha(p) for p in sorted(temp.iterdir())})
        (temp / 'manifest.json').write_text(canonical(manifest) + '\n')
        with open_research(temp, policy_hash) as checked:
            require(len(checked) == policy['expected_rows']['train'], 'Published train count differs')
        require(sha(policy_file) == policy_hash and sha(staged / 'manifest.json') == policy['staged_manifest_sha256'], 'Publication inputs changed')
        os.rename(temp, output)
        return result
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise
