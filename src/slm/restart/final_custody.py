"""Separate final evaluator custody: read-only candidate state, isolated results."""
from pathlib import Path
from . import custody,candidate_custody
from .evaluation_snapshot import _file


def readable_files(project):
    project=Path(project).resolve(strict=True)
    relative=['restart/execution-v1/data-final/'+name for name in ('manifest.json','index.jsonl','tokens.u16')]
    relative+=['restart/execution-v1/evaluation-frozen-v1/final/'+name+'.jsonl' for name in ('grammar','grounded','narrative','copy')]
    relative+=['restart/execution-v1/unigram-receipt.json']
    relative+=['restart/execution-v1/kn-preparation/model/'+name for name in
               ['receipt.json','manifest.json']+[f'{kind}-{n}.npy' for kind in ('counts','grams') for n in range(1,6)]]
    return candidate_custody.readable_files(project)+[_file(project,name) for name in relative]


def profile(project,state_root,output):
    project=Path(project).resolve(strict=True);state_root=Path(state_root).absolute();output=Path(output).absolute()
    execution=project/'restart/execution-v1'
    allowed=(state_root==execution/'candidate-run-v1' and output==state_root/'final-run-v1') or (
        state_root==execution/'final-custody-probe-v1/state' and output==execution/'final-custody-probe-v1/results')
    if not allowed or state_root.resolve(strict=True)!=state_root or output.resolve(strict=True)!=output:
        raise ValueError('Unowned final evaluator directories')
    roots=custody.runtime_roots(project)+readable_files(project)
    roots+=[state_root,project/'tests',execution/'tokenizer-8192']
    return custody.profile(read_roots=roots,write_root=output)
