#!/usr/bin/env python3
"""Actual detector on existing synthetic word sequences: mechanics/negative control."""
# Creator: Navneet Prabhakar
import argparse
import json
from pathlib import Path
import resource
import time
from slm.data.quality_audit import audit,LIMITS
from slm.data.staging import metadata,canonical
from slm.data.tokenized import sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--detector',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    dataset=Path('data/corpus-staging-scale-v3/staged').resolve()
    if set(metadata(dataset/'sources.json'))!={'staging-scale-fixture'}:raise ValueError('Synthetic staging fixture only')
    root=Path(a.output);root.mkdir(parents=True,exist_ok=False)
    spec=dict(dataset=str(dataset),descriptor=str(Path(a.detector).resolve()),limits=LIMITS,seed='quality-negative-control-v1',groups_per_stratum=3,window_characters=2048)
    (root/'spec.json').write_text(canonical(spec)+'\n');start=time.monotonic();report=audit(output=root/'audit',**spec)
    result=dict(scope='Random word-sequence negative control and bounded mechanics only; never corpus quality/English acceptance.',
                wall_seconds=time.monotonic()-start,process_peak_rss_platform_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                rss_unit='bytes on macOS; KiB on Linux',report=report,audit_manifest_sha256=sha(root/'audit/manifest.json'),
                audit_implementation_sha256=sha('src/slm/data/quality_audit.py'),actual_source_or_row_approvals=0,neural_updates=0,teacher_launches=0,cloud_jobs=0)
    assert report['records']==11000 and report['training_eligible'] is False
    (root/'result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(dict(wall_seconds=result['wall_seconds'],records=report['records'],window_top_languages=report['top_language_window_counts'])))


if __name__=='__main__':main()
