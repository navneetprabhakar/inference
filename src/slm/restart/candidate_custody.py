"""Explicit data allowlist for the candidate training/development worker.

The future scoped launcher must pin this profile, own the output directory and
start it under independent resource/time supervision. Final scoring needs a
separate custody policy and never runs in this worker.
"""
from pathlib import Path
from . import custody,numerical_snapshot
from .evaluation_snapshot import _file


def readable_files(project):
    project=Path(project).resolve(strict=True)
    relative=['restart/approval-v1/PLAN.md','restart/approval-v1/policy.json',
              'restart/execution-v1/authorization.json','restart/execution-v1/training-loss-sample-v1.json',
              'restart/execution-v1/evaluation-frozen-v1/manifest.json',
              'restart/execution-v1/batch-schedule-draft-v3/updates.jsonl',
              'restart/execution-v1/batch-schedule-draft-v3/receipt.json']
    relative += [numerical_snapshot.REVISION_ROOT+name for name in numerical_snapshot.REVISION_PINS]
    relative += [numerical_snapshot.FIXTURE_ROOT+name for name in numerical_snapshot.FIXTURES]
    relative += ['restart/execution-v1/tokenizer-8192/'+name for name in ('manifest.json','core.json')]
    relative += ['restart/execution-v1/data-train/'+name for name in ('manifest.json','index.jsonl','tokens.u16','unigram-counts.npy')]
    relative += ['restart/execution-v1/data-dev/'+name for name in ('manifest.json','index.jsonl','tokens.u16')]
    relative += ['restart/execution-v1/evaluation-frozen-v1/development/'+suite+'.jsonl' for suite in ('grammar','grounded','narrative','copy')]
    return [_file(project,name) for name in relative]


def profile(project,output):
    project=Path(project).resolve(strict=True);output=Path(output).absolute()
    execution=project/'restart/execution-v1'
    if (output.resolve(strict=True)!=output or output.parent!=execution
            or output.name not in ('candidate-run-v1','candidate-custody-probe-v1','candidate-custody-probe-v2')):
        raise ValueError('Unowned candidate output directory')
    roots=custody.runtime_roots(project)+readable_files(project)
    # Frozen code verification can read tests, but no evaluation drafts/sources.
    roots += [project/'tests',execution/'tokenizer-8192']
    return custody.profile(read_roots=roots,write_root=output)
