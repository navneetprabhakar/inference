#!/usr/bin/env python3
"""Creator: Navneet Prabhakar. Bounded, pinned public-source schema audit."""
import argparse
from dataclasses import asdict
import json
import hashlib
from pathlib import Path
from slm.data.acquire import register, sample, sample_ready_trees, verified_cached_spec
from slm.data.build import build, verify, read_source
from slm.data.schema import digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry',default='configs/source-audit-v1.json')
    parser.add_argument('--output',required=True,help='New directory, normally under data/')
    parser.add_argument('--cached-input',help='Verified prior acquisition root; avoids network downloads')
    args=parser.parse_args()
    root=Path(args.output)
    if root.exists(): raise FileExistsError(root)
    registry=json.loads(Path(args.registry).read_text())
    specs=[]
    for item in registry:
        expected=item['source']
        folder=(Path(args.cached_input) if args.cached_input else root)/item['name']
        if args.cached_input:
            actual=read_source(folder/'source/source.json')
            acquisition=json.loads((folder/'sample/acquisition.json').read_text())
            checksum=hashlib.sha256((folder/'sample/rows.jsonl').read_bytes()).hexdigest()
            if (acquisition['revision'] != expected['revision']
                or acquisition['rows'] != item['sample_count']
                or acquisition['rows_sha256'] != checksum):
                raise ValueError('Cached acquisition identity or content differs')
        else:
            actual=register(expected['source_id'],expected['license_id'],folder/'source',
                            expected['revision'],expected['upstream_origins'])
        if digest(asdict(actual)) != digest(expected):
            raise ValueError('Pinned source evidence changed; inspect before updating registry')
        if args.cached_input:
            pass
        elif item['adapter']=='oasst':
            sample_ready_trees(actual,folder/'sample',item['sample_count'])
        else:
            sample(actual,item['config'],item['upstream_split'],folder/'sample',item['sample_count'])
        specs.append(verified_cached_spec(item,folder))
    # Freeze three-source evaluation before importing the complete-tree source.
    base=root/'base'
    build([s for s in specs if s['adapter']!='oasst'],base)
    report=build(specs,root/'curated',frozen_dataset=base)
    build(specs,root/'replay',frozen_dataset=base)
    if verify(root/'curated') != verify(root/'replay'):
        raise AssertionError('Deterministic rebuild failed')
    report.pop('heldout_groups');report.pop('duplicates')
    report['deterministic_rebuild']=True
    (root/'audit-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('release','retained_examples','splits','deterministic_rebuild')},indent=2))


if __name__=='__main__': main()
