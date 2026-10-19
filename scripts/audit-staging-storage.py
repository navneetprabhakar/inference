#!/usr/bin/env python3
"""Separate-process reference/current storage comparison on identical real inputs."""
# Creator: Navneet Prabhakar
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import shutil
import subprocess
import time
from slm.data.build import verify
from slm.data.staging import metadata,stage
from slm.data.tokenized import sha

REFERENCE='59f35b91df4ce1f5b6e28d1f8c7209560eba3c0b'
SEMANTIC=('input_examples','retained_examples','splits','sources','language_labels','content_categories','rejections',
          'exact_duplicates_removed','near_pairs_grouped','candidate_comparisons','max_shared_message_exposure','split_seed',
          'source_rights_approved','training_eligible','frozen_dataset_manifest_sha256')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--variant',choices=['reference','interned'],required=True);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(a.output);root.mkdir(parents=True,exist_ok=False)
    if shutil.disk_usage(root).free<3*1024**3:raise ValueError('At least 3 GiB free scratch space required')
    baseline=Path('data/complete-small-source-v1/staged');base_manifest=verify(baseline);base_report=metadata(baseline/'report.json')
    spec=metadata('data/complete-small-source-v1/staging-spec.json');function=stage
    code_hash=sha('src/slm/data/staging.py')
    if a.variant=='reference':
        source=subprocess.check_output(['git','show',REFERENCE+':src/slm/data/staging.py'])
        if hashlib.sha256(source).hexdigest()!=base_manifest['implementation_sha256']:raise ValueError('Reference code differs from retained real baseline')
        folder=root/'reference-code';folder.mkdir();path=folder/'staging.py';path.write_bytes(source)
        cleaner=subprocess.check_output(['git','show',REFERENCE+':src/slm/data/curation.py']);(folder/'curation.py').write_bytes(cleaner)
        if hashlib.sha256(cleaner).hexdigest()!=sha('src/slm/data/curation.py'):raise ValueError('Cleaner changed; comparison is no longer storage-only')
        module_spec=importlib.util.spec_from_file_location('retained_staging_reference',path)
        module=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(module);function=module.stage;code_hash=sha(path)
    started=time.monotonic();cpu=time.process_time();report=function(spec.pop('inputs'),root/'staged',**spec)
    wall=time.monotonic()-started;cpu=time.process_time()-cpu;actual=verify(root/'staged')
    expected_files={p.name:sha(p) for p in baseline.glob('*.jsonl')}
    actual_files={p.name:sha(p) for p in (root/'staged').glob('*.jsonl')}
    assert actual_files==expected_files
    for name in ('heldout-groups.json','sources.json','evidence.json'):
        assert sha(baseline/name)==sha(root/'staged'/name)
    assert {k:report[k] for k in SEMANTIC}=={k:base_report[k] for k in SEMANTIC}
    assert actual['implementation_sha256']==code_hash
    result=dict(scope='Storage implementation comparison only; no source approval, tokenizer freeze or neural training.',variant=a.variant,
                reference_commit=REFERENCE,implementation_sha256=code_hash,reference_artifact_manifest_sha256=sha(baseline/'manifest.json'),
                wall_seconds=wall,cpu_seconds=cpu,process_peak_rss_platform_units=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                rss_unit='bytes on macOS; KiB on Linux',all_record_shards_byte_identical=True,heldout_source_evidence_indexes_identical=True,
                semantic_report_fields_identical=list(SEMANTIC),record_shard_sha256=actual_files,report=report,
                output_manifest_sha256=sha(root/'staged/manifest.json'),neural_updates=0,new_teacher_launches=0,cloud_jobs=0,actual_source_or_row_approvals=0,
                comparison_note='Run variants sequentially on the same local host. This is one workload/run each, not a sustained throughput or latency distribution.')
    (root/'audit.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ('variant','wall_seconds','cpu_seconds','process_peak_rss_platform_units','all_record_shards_byte_identical')}))


if __name__=='__main__':main()
