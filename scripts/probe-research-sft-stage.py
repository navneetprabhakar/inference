#!/usr/bin/env python3
"""Execute one explicitly frozen initialization or disposable full-step probe."""
# Creator: Navneet Prabhakar
import argparse
import fcntl
import json
import os
from pathlib import Path
from slm.data.tokenized import sha
from slm.research_sft_stage import ResearchStageInputs, run, POLICY
from slm.sft_research_preflight import preflight
from slm.train import read


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default='data/iteration-three-sft-stage-v2')
    parser.add_argument('--trial', choices=('lr-00001','lr-00005'), required=True)
    parser.add_argument('--mode', choices=('initialize','preflight'), required=True)
    args = parser.parse_args()
    root = Path(args.root)
    protocol = read(root/'preparation.json')
    for filename, checksum in protocol['source_sha256'].items():
        if sha(filename) != checksum: raise ValueError('Frozen probe implementation differs')
    trial = protocol['trials'][args.trial]
    file = root/(args.trial+'.json')
    if sha(file) != trial['spec_file_sha256'] or sha(root/'origin-spec.json') != protocol['origin_spec_sha256']:
        raise ValueError('Frozen probe specification differs')
    spec, origin = read(file), read(root/'origin-spec.json')
    reason = protocol['transition_reason']
    source = protocol['source_checkpoint']
    report = protocol['source_report']
    if args.mode == 'initialize':
        result = run(spec, origin, source, report, root/(args.trial+'-initialization'), optimizer_policy=POLICY,
                     reason=reason, backend='mlx', device='default', initialize_only=True)
    else:
        output = root/('preflight-'+args.trial+'.json')
        if output.exists(): raise FileExistsError(output)
        inp = ResearchStageInputs(spec, origin, source, report, POLICY, reason)
        try:
            if inp.identity != trial['plan_hash']: raise ValueError('Frozen preflight plan differs')
            with (root/'preflight.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                ledger = root/'preflight-reservations.jsonl'
                prior = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
                positions = inp.data.max_length*inp.recipe.accumulation_steps
                if (sum(v['positions'] for v in prior)+positions > inp.research_limits['synthetic_preflight_gradient_positions']
                        or any(v['trial'] == args.trial for v in prior)):
                    raise ValueError('Preflight already reserved or combined workload exceeds policy; no silent replay')
                event = dict(trial=args.trial, plan_hash=inp.identity, positions=positions,
                             policy_file_sha256=inp.policy_hash, status='reserved_before_clone_update')
                with ledger.open('a') as stream:
                    stream.write(json.dumps(event, sort_keys=True)+'\n'); stream.flush(); os.fsync(stream.fileno())
                result = preflight(inp, output, 'mlx', 'default')
        finally: inp.close()
    if result['plan_hash'] != trial['plan_hash']:
        raise ValueError('Executed probe plan differs')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
