#!/usr/bin/env python3
"""Large synthetic explicit-review ledger, with no real human/source approval."""
# Creator: Navneet Prabhakar
import argparse
import json
from pathlib import Path
import resource
import time
from slm.data.build import verify
from slm.data.review_stream import release,open_checked,DEFAULT_LIMITS
from slm.data.staging import canonical,metadata
from slm.data.schema import digest
from slm.data.tokenized import sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    source=Path(a.dataset);verify(source);sources=metadata(source/'sources.json')
    if set(sources)!={'staging-scale-fixture'} or sources['staging-scale-fixture']['upstream_origins']!=['synthetic']:
        raise ValueError('Only the existing synthetic staging fixture is allowed; never public/teacher data')
    root=Path(a.output);root.mkdir(parents=True,exist_ok=False);review=root/'review';review.mkdir();n=0
    with (review/'decisions.jsonl').open('w') as f:
        for path in sorted(source.glob('*.jsonl')):
            for line in path.open():
                row=json.loads(line);n+=1
                decision=dict(approved=True,english_verified=True,privacy_verified=True,quality_verified=True,
                              content_category='sfw',upstream_partition='train',partition_evidence='Synthetic fixture; no actual human assessment',note='Simulated fixture gates only')
                f.write(canonical(dict(record=row,record_sha256=digest(row),decision=decision))+'\n')
    # Simulated attestations are restricted to this synthetic fixture by the guard above.
    header=dict(version=2,scope='explicit_rows_only',dataset_manifest_sha256=sha(source/'manifest.json'),
                reviewer='Navneet Prabhakar',human_attestation=True,decisions_sha256=sha(review/'decisions.jsonl'),legacy_packet_sha256=None,
                source_reviews={k:dict(source_record=v,source_sha256=digest(v),approved=True,terms_reviewed=True,allowed_categories=['sfw'],
                                       evidence_note='Simulated fixture; not actual source rights or human approval') for k,v in sources.items()})
    (review/'header.json').write_text(canonical(header)+'\n');start=time.monotonic()
    report=release(source,review,root/'released',limits=DEFAULT_LIMITS)
    release_seconds=time.monotonic()-start;start=time.monotonic()
    with open_checked(root/'released') as index:
        total=sum(1 for _ in index.values());first=next(iter(index));assert index[first]['example_id']==first
        reader_db=index.peak
    result=dict(scope='Synthetic ledger and checked reader only; simulated decisions are not actual human/source approval.',
                input_rows=n,train_rows=total,release_wall_seconds=release_seconds,reader_wall_seconds=time.monotonic()-start,
                process_peak_rss_platform_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,rss_unit='bytes on macOS; KiB on Linux',
                reader_peak_database_allocated_bytes=reader_db,report=report,ledger_bytes=(review/'decisions.jsonl').stat().st_size,
                actual_public_or_teacher_approvals=0,neural_updates=0,teacher_launches=0,cloud_jobs=0,
                release_manifest_sha256=sha(root/'released/manifest.json'),implementation_sha256=sha('src/slm/data/review_stream.py'))
    assert n==11000 and total==9944
    (root/'audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
