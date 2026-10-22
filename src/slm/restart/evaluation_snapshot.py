"""Fail-closed verification of the pinned M1 evaluation snapshot.

This prepares custody inputs only. It cannot initialize a model or launch training.
The manifest pin is reviewed code, not a caller-controlled receipt field.
"""
import hashlib
import json
from pathlib import Path

MANIFEST_SHA256 = '1b530b2cc958760fdac477e55b9bc8b7e76b5403066c468dab12298543b59d52'
EXPECTED_FILES = {f'{split}/{suite}.jsonl' for split in ('development', 'final')
                  for suite in ('grammar', 'grounded', 'narrative', 'copy')}
SCORERS = {f'src/slm/restart/{name}.py' for name in
           ('choice_scoring', 'research_gates', 'generation_metrics')}


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file(root, relative):
    """Disallow symlink redirection, absolute paths and traversal in bound files."""
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Unsafe snapshot path')
    path = root / rel
    if path.resolve(strict=True) != path.absolute() or not path.is_file():
        raise ValueError('Snapshot path is redirected or not a regular file')
    return path


def verify(project):
    project = Path(project).resolve(strict=True)
    snapshot = project / 'restart/execution-v1/evaluation-frozen-v1'
    manifest_path = _file(project, 'restart/execution-v1/evaluation-frozen-v1/manifest.json')
    if _digest(manifest_path) != MANIFEST_SHA256:
        raise ValueError('Evaluation manifest differs from reviewed pin')
    manifest = json.loads(manifest_path.read_text())
    if manifest['status'] != 'HASH_BOUND_SNAPSHOT_ACTUAL_PATH_CUSTODY_TESTED':
        raise ValueError('Snapshot not custody tested')
    if set(manifest['files_sha256']) != EXPECTED_FILES:
        raise ValueError('Evaluation file inventory differs')
    if set(manifest['scoring_code_sha256']) != SCORERS:
        raise ValueError('Scoring inventory differs')
    for relative, digest in manifest['files_sha256'].items():
        if _digest(_file(snapshot, relative)) != digest:
            raise ValueError('Evaluation content changed: ' + relative)
    for relative, digest in manifest['scoring_code_sha256'].items():
        if _digest(_file(project, relative)) != digest:
            raise ValueError('Scoring code changed: ' + relative)
    bindings = {
        'restart/execution-v1/evaluation-draft/combined-audit.json': manifest['combined_audit_sha256'],
        'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv': manifest['source_manifest_sha256'],
        'restart/execution-v1/evaluation-frozen-v1/custody-verification.json': manifest['custody_verification_sha256'],
    }
    for relative, digest in bindings.items():
        if _digest(_file(project, relative)) != digest:
            raise ValueError('Evaluation evidence changed: ' + relative)
    custody = json.loads(_file(snapshot, 'custody-verification.json').read_text())
    for relative, digest in {
        'src/slm/restart/custody.py': custody['custody_code_sha256'],
        'restart/execution-v1/evaluation-frozen-v1/training-custody-test.sb': custody['profile_sha256'],
    }.items():
        if _digest(_file(project, relative)) != digest:
            raise ValueError('Custody implementation/evidence changed: ' + relative)
    draft = project / 'restart/execution-v1/evaluation-draft'
    audit = json.loads((draft/'combined-audit.json').read_text())
    for field in ('files_sha256', 'evidence_sha256'):
        for relative, digest in audit[field].items():
            if _digest(_file(draft, relative)) != digest:
                raise ValueError('Draft/evidence changed: ' + relative)
    # Return exact paths, never the shared execution/draft root as an allowlist.
    return {'manifest_sha256': MANIFEST_SHA256,
            'development_files': [str(snapshot/r) for r in sorted(EXPECTED_FILES) if r.startswith('development/')],
            'final_files': [str(snapshot/r) for r in sorted(EXPECTED_FILES) if r.startswith('final/')],
            'smoke_ids': manifest['development_smoke_ids'],
            'training_authorized_by_this_check': False}
