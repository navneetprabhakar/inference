#!/usr/bin/env python3
"""Compare an actual one-update learned-checkpoint replay with its original end."""
# Creator: Navneet Prabhakar
import argparse
from pathlib import Path
import json
import numpy as np
from safetensors.numpy import load_file
from slm.train import Inputs, read, resolve_paths, verify_checkpoint
from slm.data.tokenized import sha


def compare(spec_path, contract_path):
    spec_path, contract_path = Path(spec_path), Path(contract_path)
    contract = read(contract_path)
    spec = resolve_paths(read(spec_path), spec_path.parent)
    inputs = Inputs(spec)
    try:
        if inputs.identity != contract['plan_hash']:
            raise ValueError('Resume contract plan differs')
        original, replay = Path(contract['original_run']), Path(contract['resume_run'])
        a, b = read(original/'report.json'), read(replay/'report.json')
        ra, rb = read(original/'run.json'), read(replay/'run.json')
        paths = [Path(r['latest_checkpoint']) for r in (a, b)]
        states = []
        for report, run, path, root in zip((a, b), (ra, rb), paths, (original, replay)):
            if (report['plan_hash'] != inputs.identity or run['logical_plan'] != inputs.plan
                or run['backend'] != contract['backend'] or run['device'] != contract['device']
                or report['status'] != 'data_exhausted_before_target'
                or report['final']['step'] != contract['expected_final_step']
                or report['final']['tokens'] != contract['expected_final_processed_positions']
                or report['final']['cursor'] != len(inputs.data)
                or sha(root/'events.jsonl') != report['events_sha256']
                or path.resolve().parent != (root/'checkpoints').resolve()
                or sha(path/'manifest.json') != report['latest_manifest_sha256']):
                raise ValueError('Terminal resume comparison bindings differ')
            inputs.pin_tree(root)
            _, state = verify_checkpoint(path, inputs)
            if any(state[k] != report['final'][k] for k in ('step', 'cursor', 'tokens', 'supervised_tokens')):
                raise ValueError('Terminal state counters differ')
            states.append(state)
        if (ra['resume_manifest_sha256'] is not None or a['initial']['step'] != 0
            or b['initial']['step'] != contract['resume_checkpoint_step']
            or b['executed_this_invocation']['updates'] != contract['max_new_updates']):
            raise ValueError('Expected original and one-update replay invocations')
        candidates = [p for p in (original/'checkpoints').iterdir()
                      if p.is_dir() and sha(p/'manifest.json') == rb['resume_manifest_sha256']]
        if len(candidates) != 1:
            raise ValueError('Exact replay origin checkpoint is absent or ambiguous')
        _, origin = verify_checkpoint(candidates[0], inputs)
        if origin['step'] != contract['resume_checkpoint_step'] or any(origin[k] != b['initial'][k] for k in b['initial']):
            raise ValueError('Replay did not start from declared original state')
        mismatches, tensors, values = [], 0, 0
        for name in ('model/model.safetensors', 'optimizer.safetensors'):
            left, right = [load_file(str(p/'state'/name)) for p in paths]
            if left.keys() != right.keys():
                raise ValueError('Checkpoint tensor inventories differ')
            for key in left:
                x, y = left[key], right[key]
                exact = x.shape == y.shape and x.dtype == y.dtype and np.array_equal(x.view(np.uint32), y.view(np.uint32))
                if not exact:
                    mismatches.append(name+':'+key)
                tensors += 1
                values += x.size
            del left, right
        keys = ('version', 'step', 'cursor', 'tokens', 'supervised_tokens', 'recipe', 'dataset_hash', 'tokenizer_hash', 'accumulation', 'precision', 'schedule')
        metadata_mismatches = [k for k in keys if states[0][k] != states[1][k]]
        inputs.check()
        return dict(version=1, creator='Navneet Prabhakar', scope=contract['scope'],
                    contract_sha256=sha(contract_path), verifier_sha256=sha(__file__), plan_hash=inputs.identity,
                    original_report_sha256=sha(original/'report.json'), replay_report_sha256=sha(replay/'report.json'),
                    resume_origin_manifest_sha256=rb['resume_manifest_sha256'],
                    final_model_manifests=[sha(p/'state/model/manifest.json') for p in paths],
                    compared_tensors=tensors, compared_fp32_values=values, tensor_mismatches=mismatches,
                    metadata_mismatches=metadata_mismatches, exact_passed=not mismatches and not metadata_mismatches,
                    original_final=a['final'], replay_initial=b['initial'], replay_final=b['final'],
                    additional_physical_replay=b['executed_this_invocation'],
                    combined_physical_positions=a['executed_this_invocation']['processed_positions']+b['executed_this_invocation']['processed_positions'],
                    final_model_logical_positions=b['final']['tokens'], limitations=contract['limitations'],
                    production_accepted=False, cross_backend_quality_proved=False)
    finally:
        inputs.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('spec', 'contract', 'output'):
        parser.add_argument('--'+key, required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    result = compare(args.spec, args.contract)
    with args.output.open('x') as f:
        f.write(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({k: result[k] for k in ('exact_passed', 'compared_tensors', 'compared_fp32_values')}))


if __name__ == '__main__':
    main()
