"""Strict comparison of separately executed qualification checkpoint branches.

Inputs must be trusted own-model bundles. This tool validates hashes before
loading, compares full model/optimizer/RNG/data state, and grants no tolerance.
It neither trains nor allocates compute. Use uninterrupted step2 versus restored
step1 followed by one update, with matching frozen runtime/data identities.
"""
import argparse,json
import os
from pathlib import Path
import torch
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_benchmark import compare_state

def compare_and_record(reference, resumed, output):
    """Persist a comparison, including failures, before enforcing the exact gate.

    Exclusive creation prevents a retry from replacing an earlier failure. An
    unwritable receipt is itself fatal; a comparison never passes without proof.
    """
    output = Path(output)
    if output.exists():
        raise FileExistsError('Do not overwrite qualification evidence')
    try:
        result = compare_bundles(reference, resumed)
    except Exception as error:
        result = {'status': 'hold', 'comparison_error': repr(error),
                  'quality_accepted': False}
    with output.open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    if result['status'] != 'pass':
        raise ValueError(f'Exact restart gate failed; evidence: {output}')
    return result

def compare_bundles(reference,resumed):
    paths=[Path(reference),Path(resumed)]
    manifests=[validate_bundle(p) for p in paths]
    metadata=[json.loads((p/'metadata.json').read_text()) for p in paths]
    if metadata[0]['identity']!=metadata[1]['identity'] or metadata[0]['step']!=metadata[1]['step']:
        raise ValueError('Qualification branches differ in identity or completed step')
    states=[torch.load(p/'payload.pt',map_location='cpu',weights_only=False) for p in paths]
    result=compare_state(states[0],states[1])
    loop_equal=metadata[0].get('loop')==metadata[1].get('loop')
    return {'status':'pass' if result['bitwise_equal'] and loop_equal else 'hold',
            'step':metadata[0]['step'],'full_state':result,'quality_loop_equal':loop_equal,
            'manifest_files_verified':True,'quality_accepted':False,
            'limitation':'Caller must prove branches were separately executed and one restored from GCS; equal files alone do not establish a restart experiment.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--resumed',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    output=Path(a.output)
    if output.exists():raise FileExistsError('Do not overwrite qualification evidence')
    value=compare_bundles(a.reference,a.resumed);output.write_text(json.dumps(value,indent=2)+'\n')
    return 0 if value['status']=='pass' else 2
if __name__=='__main__':raise SystemExit(main())
