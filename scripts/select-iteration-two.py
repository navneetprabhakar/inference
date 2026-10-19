#!/usr/bin/env python3
"""Publish the frozen optimizer decision after both screen scores exist."""
# Creator: Navneet Prabhakar
import fcntl
import json
from pathlib import Path
from slm.eval.iteration_two_selection import select_from_results


def main():
    root=Path('data/iteration-two-experiment-v1');output=Path('reports/milestone-forty-nine-optimizer-selection.json')
    if output.exists():raise FileExistsError(output)
    with (root/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=select_from_results(root,'reports/milestone-forty-eight-experiment-freeze.json',
            {k:'reports/iteration-two-'+k+'-score.json' for k in ('lr-0003','lr-0010')})
        with output.open('x') as out:out.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
        print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
