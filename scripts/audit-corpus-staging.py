#!/usr/bin/env python3
"""Synthetic local staging scale probe; does not admit or train any corpus."""
# Creator: Navneet Prabhakar
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import random
import resource
import time
from slm.data.schema import Source,make_example
from slm.data.staging import stage,canonical
from slm.data.tokenized import sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(a.output);root.mkdir(parents=True,exist_ok=False)
    (root/'card').write_text('Synthetic independently sampled word sequences for staging mechanics only.')
    (root/'license').write_text('Synthetic fixture; no source admission or learned-quality claim.')
    source=Source('staging-scale-fixture','a'*40,'https://example.org/synthetic','fixture',sha(root/'license'),sha(root/'card'),('synthetic',))
    (root/'source.json').write_text(canonical({**asdict(source),'evidence_files':dict(card='card',license='license')})+'\n')
    rng=random.Random(20261019);vocabulary=['word'+format(i,'08x') for i in range(20000)]
    raw=root/'input.jsonl';n=11000
    with raw.open('w') as f:
        for i in range(n):
            text=' '.join(rng.choices(vocabulary,k=260))
            record=make_example(source,str(i),str(i),[dict(role='text',content=text)],task='prose',language='unknown')
            f.write(canonical(record.to_dict())+'\n')
    limits=dict(max_input_bytes=64*1024*1024,max_records=12000,max_record_bytes=65536,max_shingles=4096,
                max_pair_checks=2000000,max_db_bytes=1024*1024*1024)
    spec=dict(path=str(raw.resolve()),sha256=sha(raw),source_record=str((root/'source.json').resolve()),adapter='canonical')
    (root/'spec.json').write_text(canonical(dict(inputs=[spec],limits=limits))+'\n')
    start=time.monotonic();report=stage([spec],root/'staged',limits=limits)
    result=dict(scope='Synthetic word-sequence JSONL mechanics; no natural-language quality or production scaling proof.',
                wall_seconds=time.monotonic()-start,process_peak_rss_platform_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                rss_unit='bytes on macOS; KiB on Linux',records=n,input_sha256=sha(raw),report=report,
                neural_updates=0,public_or_teacher_examples=0,code_sha256=sha(Path(__file__)))
    assert report['retained_examples']==n and raw.stat().st_size>32*1024*1024 and n>10000
    (root/'audit.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
