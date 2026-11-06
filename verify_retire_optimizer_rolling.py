"""Synthetic file/metadata retirement tests; never reads or mutates real runs."""
from copy import deepcopy
import fcntl
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import retire_optimizer_rolling as subject


class Crash(RuntimeError):
    pass


def write(path, value):
    path.write_bytes(subject.canonical(value))


def checkpoint(run, step, content):
    sha = subject.byte_sha(content)
    path = run/f'step-{step:06d}-{sha}.pt'
    path.write_bytes(content)
    return dict(file=path.name, sha256=sha, bytes=len(content))


def fixture(root):
    root.mkdir()
    (root/'runs').mkdir()
    (root/'runs/mps.lock').touch()
    (root/'reports').mkdir()
    protocol = root/'reports/protocol.json'
    write(protocol, {'test': 'synthetic retirement only'})
    reporter = root/'optimizer_ablation_report.py'
    reporter.write_text('synthetic completed reporter identity')
    trainer = root/'optimizer_ablation_train.py'
    trainer.write_text('synthetic frozen trainer identity')
    common = dict(parent=dict(run=str(root/'runs/own-base-foundation-01'),
                              checkpoint='step-012207-'+'a'*64+'.pt', sha256='a'*64),
                  source_offset=99999744, target_tokens=subject.TARGET, length=512, microbatch=2,
                  targets_per_update=8192, seed=20261106, bf16=True, corpus='fixture-corpus',
                  manifest_sha256='fixture-manifest', validation_blocks_sha256='fixture-windows',
                  diagnostics_sha256='fixture-diagnostics', scheduler={'fixture': 'common restart'},
                  protocol_sha256=subject.digest(protocol),
                  code_sha256={'optimizer_ablation_train.py': subject.digest(trainer)})
    receipts, candidates = {}, {}
    for branch in subject.BRANCHES:
        run = root/'runs'/('optimizer-ablation-v1-'+branch)
        run.mkdir(); (run/'.checkpoint.lock').touch()
        old = checkpoint(run, 2300, ('old rolling fixture '+branch).encode())
        endpoint = checkpoint(run, subject.TARGET//8192, ('protected endpoint fixture '+branch).encode())
        candidates[branch] = old
        spec = dict(common, branch=branch, protocol_path=str(protocol))
        identity = dict(protocol=spec,
                        model=dict(vocabulary=50257, context=1024, width=768, heads=12, depth=12),
                        initialization=dict(mode='own_pretraining', path=str(Path(common['parent']['run'])/common['parent']['checkpoint']),
                                            sha256='a'*64, random_lineage_root=subject.LINEAGE),
                        tokenizer=subject.TOKENIZER, seed=common['seed'], scheduler=common['scheduler'],
                        code=common['code_sha256'], corpus=dict(directory=common['corpus'], manifest=common['manifest_sha256'],
                              validation=common['validation_blocks_sha256'], source_offset=common['source_offset']))
        frozen = dict(schema=1, identity=identity, token_limit=subject.TARGET)
        ledger = dict(spec=frozen, campaign_id='synthetic-'+branch, state='completed',
                      step=subject.TARGET//8192, trained_tokens=subject.TARGET,
                      reserved_tokens=subject.TARGET, checkpoints=[endpoint, old])
        write(run/'campaign-spec.json', frozen)
        write(run/'campaign.json', subject.signed(ledger))
        write(run/'latest.json', [endpoint, old])
        write(run/'protected.json', [endpoint['file']])
        receipts[branch] = dict(run=str(run), checkpoint=endpoint, ledger_sha256=subject.digest(run/'campaign.json'))
    report = dict(state='screen-completed', usable_assistant=False, receipts=receipts,
                  common=common, report_code_sha256=subject.digest(reporter))
    path = root/'reports/comparison.json'
    write(path, report)
    return report, path, candidates


def invoke(root, report, path, branch='preserve-095', **kwargs):
    run = Path(report['receipts'][branch]['run'])
    with patch.object(subject, 'ROOT', root.resolve()):
        return subject.retire(run, report['receipts'][branch]['checkpoint']['sha256'], path,
                              subject.digest(path), **kwargs)


def expect_reject(function):
    try:
        function()
    except (ValueError, FileNotFoundError):
        return
    raise AssertionError('unsafe retirement accepted')


def files(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def run():
    count = 0
    with TemporaryDirectory() as temporary:
        base = Path(temporary)
        root = base/'normal'; report, path, candidates = fixture(root)
        before = files(root)
        result = invoke(root, report, path)
        assert result['state'] == 'ready-to-retire' and not result['applied']
        assert before == files(root); count += 1
        untouched_report = path.read_bytes()
        original_ledgers = {b: (Path(r['run'])/'campaign.json').read_bytes() for b, r in report['receipts'].items()}
        endpoint_bytes = {b: (Path(r['run'])/r['checkpoint']['file']).read_bytes() for b, r in report['receipts'].items()}
        for branch in subject.BRANCHES:
            result = invoke(root, report, path, branch, apply=True)
            assert result['state'] == 'retired'
            run_path = Path(report['receipts'][branch]['run'])
            assert not (run_path/candidates[branch]['file']).exists()
            assert (run_path/report['receipts'][branch]['checkpoint']['file']).read_bytes() == endpoint_bytes[branch]
            assert subject.read_signed(run_path/'campaign.json')['checkpoints'] == [report['receipts'][branch]['checkpoint']]
            archive = Path(result['audit_directory'])
            assert (archive/'original-campaign.json').read_bytes() == original_ledgers[branch]
            assert subject.digest(archive/'original-campaign.json') == report['receipts'][branch]['ledger_sha256']
            assert path.read_bytes() == untouched_report
            current = files(root)
            assert invoke(root, report, path, branch, apply=True)['state'] == 'retired'
            assert current == files(root); count += 1
        # Simulate process death at every durable publication boundary.
        for stage in ('archives', 'prepared', 'latest-published', 'ledger-published', 'deletion-authorized', 'unlinked', 'receipt'):
            root = base/('crash-'+stage); report, path, candidates = fixture(root)
            run_path = Path(report['receipts']['preserve-095']['run'])
            original = (run_path/'campaign.json').read_bytes()
            def crash(where):
                if where == stage:
                    raise Crash(stage)
            try:
                invoke(root, report, path, apply=True, _fault=crash)
            except Crash:
                pass
            else:
                raise AssertionError('crash hook not reached')
            assert (run_path/report['receipts']['preserve-095']['checkpoint']['file']).exists()
            recovered = invoke(root, report, path, apply=True)
            assert recovered['state'] == 'retired'
            assert (Path(recovered['audit_directory'])/'original-campaign.json').read_bytes() == original
            assert not (run_path/candidates['preserve-095']['file']).exists(); count += 1
        # No mutation for a protected candidate, an incomplete arm, or corruption.
        for case in ('protected', 'candidate-tamper', 'endpoint-tamper', 'comparison-tamper',
                     'incomplete', 'external-reference', 'queued-template-reference', 'same-step-candidate',
                     'archive-tamper', 'missing-before-intent'):
            root = base/case; report, path, candidates = fixture(root)
            run_path = Path(report['receipts']['preserve-095']['run'])
            candidate = candidates['preserve-095']
            if case == 'protected':
                write(run_path/'protected.json', [report['receipts']['preserve-095']['checkpoint']['file'], candidate['file']])
            elif case == 'candidate-tamper':
                (run_path/candidate['file']).write_bytes(b'changed')
            elif case == 'endpoint-tamper':
                (run_path/report['receipts']['preserve-095']['checkpoint']['file']).write_bytes(b'changed')
            elif case == 'comparison-tamper':
                expected = subject.digest(path)
                path.write_bytes(path.read_bytes()+b' ')
                with patch.object(subject, 'ROOT', root.resolve()):
                    expect_reject(lambda: subject.retire(run_path, report['receipts']['preserve-095']['checkpoint']['sha256'], path, expected, apply=True))
                count += 1; continue
            elif case == 'incomplete':
                other = Path(report['receipts']['reset-scaled']['run'])
                ledger = subject.read_signed(other/'campaign.json'); ledger['state'] = 'paused-lease'
                write(other/'campaign.json', subject.signed(ledger))
                # Update the pinned report receipt: semantic completion is still mandatory.
                report['receipts']['reset-scaled']['ledger_sha256'] = subject.digest(other/'campaign.json')
                write(path, report)
            elif case == 'external-reference':
                other = root/'runs/other-campaign'; other.mkdir()
                write(other/'config.json', {'parent': {'sha256': candidate['sha256']}})
            elif case == 'queued-template-reference':
                write(root/'reports/preserve-095.r2.template.json', {'parent': {'sha256': candidate['sha256']}})
            elif case == 'same-step-candidate':
                same_step = checkpoint(run_path, subject.TARGET//8192, b'distinct same-step fixture')
                endpoint = report['receipts']['preserve-095']['checkpoint']
                ledger = subject.read_signed(run_path/'campaign.json')
                ledger['checkpoints'] = [endpoint, same_step]
                write(run_path/'campaign.json', subject.signed(ledger))
                write(run_path/'latest.json', [endpoint, same_step])
                report['receipts']['preserve-095']['ledger_sha256'] = subject.digest(run_path/'campaign.json')
                write(path, report)
            elif case in ('archive-tamper', 'missing-before-intent'):
                def stop(where):
                    if where == 'prepared': raise Crash()
                try: invoke(root, report, path, apply=True, _fault=stop)
                except Crash: pass
                if case == 'archive-tamper':
                    archive = next((run_path/subject.ARCHIVE).glob('*/original-campaign.json'))
                    archive.write_bytes(archive.read_bytes()+b' ')
                else:
                    (run_path/candidate['file']).unlink()
            before = files(root)
            expect_reject(lambda: invoke(root, report, path, apply=True))
            assert before == files(root); count += 1
        # A reference added after publication is checked again before deletion.
        for moment in ('ledger-published', 'deletion-authorized'):
            root = base/('late-reference-'+moment); report, path, candidates = fixture(root)
            run_path = Path(report['receipts']['preserve-095']['run'])
            def late_reference(where):
                if where == moment:
                    other = root/'runs/later'; other.mkdir()
                    write(other/'campaign-spec.json', {'checkpoint': str(run_path/candidates['preserve-095']['file'])})
            expect_reject(lambda: invoke(root, report, path, apply=True, _fault=late_reference))
            assert (run_path/candidates['preserve-095']['file']).exists(); count += 1
        # Active GPU worker and concurrent checkpoint publication both refuse apply.
        for case, lock_name in [('gpu-busy', 'gpu'), ('checkpoint-busy', 'checkpoint')]:
            root = base/case; report, path, candidates = fixture(root)
            target = root/'runs/mps.lock' if lock_name == 'gpu' else Path(report['receipts']['preserve-095']['run'])/'.checkpoint.lock'
            with target.open('rb') as held:
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                before = files(root)
                expect_reject(lambda: invoke(root, report, path, apply=True))
                assert before == files(root)
            count += 1
        # Unknown run names and wrong explicit endpoint pins are never eligible.
        root = base/'allowlist'; report, path, candidates = fixture(root)
        with patch.object(subject, 'ROOT', root.resolve()):
            expect_reject(lambda: subject.retire(root/'runs/own-base-foundation-01', '0'*64, path, subject.digest(path), apply=True))
            expect_reject(lambda: subject.retire(Path(report['receipts']['preserve-095']['run']), '0'*64, path, subject.digest(path), apply=True))
        count += 2
    print(f'PASS {count} synthetic CPU retirement cases; no model tensors, GPU operations, or real-run reads/writes')


if __name__ == '__main__':
    run()
