#!/usr/bin/env python3
"""Reserve the remaining frozen physical work and resume only the chosen chain."""
# Creator: Navneet Prabhakar
from datetime import datetime,timezone
import fcntl
import json
from pathlib import Path
import subprocess
from slm.data.tokenized import sha
from slm.eval.iteration_two_selection import select_from_results
from slm.train import run


def main():
    root=Path('data/iteration-two-experiment-v1').resolve();selection_file=Path('reports/milestone-forty-nine-optimizer-selection.json')
    selection=json.loads(selection_file.read_text());protocol=json.loads((root/'protocol.json').read_text())
    with (root/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        expected=select_from_results(root,'reports/milestone-forty-eight-experiment-freeze.json',
            {k:'reports/iteration-two-'+k+'-score.json' for k in ('lr-0003','lr-0010')})
        if selection!=expected:raise ValueError('Saved optimizer selection differs from verified screen evidence')
        for trial in ('lr-0003','lr-0010'):
            reservation=json.loads((root/'reservations'/(trial+'.json')).read_text())
            if (reservation['reserved_processed_positions']!=262144 or reservation['protocol_sha256']!=selection['protocol_sha256']
                or reservation['plan_hash']!=protocol['plan_hashes'][trial]):raise ValueError('Historical screen reservation differs')
        trial=selection['selected_trial']
        with (root/'reservations/continuation.json').open('x') as out:
            json.dump(dict(creator='Navneet Prabhakar',selected_trial=trial,selection_sha256=sha(selection_file),
                protocol_sha256=selection['protocol_sha256'],reserved_processed_positions=selection['continuation_reserved_positions'],
                reserved_at_utc=datetime.now(timezone.utc).isoformat(),launch_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                note='Persistent physical reservation; no automatic fresh restart or retry.'),out,indent=2)
        report=run(json.loads((root/(trial+'.json')).read_text()),root/'runs/selected-continuation',backend='mlx',device='default',
            resume=selection['selected']['checkpoint'],wall_seconds=protocol['invocation']['continuation_soft_wall_seconds'])
        print(json.dumps({k:report[k] for k in ('status','initial','final','latest_checkpoint')},indent=2),flush=True)


if __name__=='__main__':main()
