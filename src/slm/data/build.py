"""Build deterministic sample shards from explicit local input and source evidence."""
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from collections import Counter
import platform
import unicodedata
from slm.data.schema import Source, Example
from slm.data.adapters import rows
from slm.data.curation import curate, clean


def read_source(path):
    path = Path(path)
    raw = json.loads(path.read_text())
    evidence = raw.pop('evidence_files')
    source = Source(**raw)
    for key, field in [('card','card_sha256'), ('license','license_text_sha256')]:
        content = (path.parent/evidence[key]).read_bytes()
        if hashlib.sha256(content).hexdigest() != getattr(source,field):
            raise ValueError(f'Source evidence checksum mismatch: {key}')
    return source


def build(input_specs, destination, frozen_groups=None, shard_size=100, training_release=False,
          frozen_dataset=None):
    destination = Path(destination)
    if destination.exists(): raise FileExistsError(destination)
    if shard_size < 1: raise ValueError('Positive shard size required')
    sources, examples, input_hashes = {}, [], {}
    input_counts, adapted_counts = Counter(), Counter()
    for spec in input_specs:
        source = read_source(spec['source_record'])
        if source.source_id in sources and sources[source.source_id] != source:
            raise ValueError('Conflicting source registrations')
        sources[source.source_id] = source
        path = Path(spec['path'])
        if path.stat().st_size > 32*1024*1024:
            raise ValueError('Audit input exceeds 32 MiB; bulk processing is not enabled')
        raw = path.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        identity = f"{source.source_id}:{spec['adapter']}:{spec.get('official_split')}:{checksum}"
        input_hashes[identity] = checksum
        records = [json.loads(line) for line in raw.decode('utf8').splitlines() if line.strip()]
        if len(examples)+len(records) > 10_000:
            raise ValueError('Reference audit row limit exceeded')
        partitions,partition_hash=None,None
        if spec.get('partition_map') is not None:
            from slm.data.partitions import load_mapping
            partitions,partition_hash=load_mapping(spec['partition_map'],spec.get('partition_map_sha256'),source,checksum)
            input_hashes['official-partition-map:'+source.source_id]=partition_hash
        elif spec.get('partition_map_sha256') is not None:raise ValueError('Partition hash without mapping bundle')
        adapted=rows(source,records,spec['adapter'],spec.get('official_split'),partitions,partition_hash)
        input_counts[source.source_id]+=len(records)
        adapted_counts[source.source_id]+=len(adapted)
        examples.extend(adapted)
    frozen_digest, frozen_ids = None, set()
    if frozen_dataset is not None:
        frozen = Path(frozen_dataset)
        verify(frozen)
        frozen_digest = hashlib.sha256((frozen/'manifest.json').read_bytes()).hexdigest()
        prior_sources = {k:Source(**v) for k,v in json.loads((frozen/'sources.json').read_text()).items()}
        for name,source in prior_sources.items():
            if name in sources and source != sources[name]:
                raise ValueError('Frozen source registration changed')
            sources[name] = source
        previous_groups=json.loads((frozen/'heldout-groups.json').read_text())
        for group,split in (frozen_groups or {}).items():
            if group in previous_groups and previous_groups[group] != split:
                raise ValueError('Frozen group conflict')
        frozen_groups={**previous_groups,**(frozen_groups or {})}
        existing={e.example_id:e for e in examples}
        for split in ('validation','test'):
            for shard in sorted(frozen.glob(f'{split}-*.jsonl')):
                for line in shard.read_text().splitlines():
                    item=Example(**json.loads(line))
                    frozen_ids.add(item.example_id)
                    if item.example_id in existing:
                        candidate=existing[item.example_id]
                        if (clean(candidate).messages != item.messages
                            or candidate.parent_group_id != item.parent_group_id
                            or candidate.source_revision != item.source_revision):
                            raise ValueError('Frozen example changed')
                    else:
                        examples.append(item)
    retained, report = curate(examples,sources,frozen_groups=frozen_groups,
                             frozen_example_ids=frozen_ids,training_release=training_release)
    report.update(adapter_input_rows=dict(input_counts),adapter_output_examples=dict(adapted_counts))
    destination.parent.mkdir(parents=True,exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.data-build-',dir=destination.parent))
    try:
        for split in ('train','validation','test'):
            items = [e for e in retained if e.split == split]
            for offset in range(0,len(items),shard_size):
                text = ''.join(json.dumps(e.to_dict(),sort_keys=True,ensure_ascii=False)+'\n'
                               for e in items[offset:offset+shard_size])
                (temp/f'{split}-{offset//shard_size:05d}.jsonl').write_text(text)
        heldout = report['heldout_groups']
        (temp/'heldout-groups.json').write_text(json.dumps(heldout,sort_keys=True,indent=2)+'\n')
        (temp/'sources.json').write_text(json.dumps({k:asdict(v) for k,v in sorted(sources.items())},sort_keys=True,indent=2)+'\n')
        (temp/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        manifest = {'version':1,'release':report['release'],'inputs':input_hashes,
                    'python':platform.python_version(),'unicode':unicodedata.unidata_version,
                    'implementation':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in sorted(Path(__file__).parent.glob('*.py'))},
                    'frozen_dataset_manifest_sha256':frozen_digest,
                    'frozen_groups':frozen_groups or {},
                    'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(temp.iterdir())}}
        (temp/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        os.rename(temp,destination)
    except BaseException:
        shutil.rmtree(temp,ignore_errors=True); raise
    return report


def verify(path):
    path=Path(path)
    manifest=json.loads((path/'manifest.json').read_text())
    if manifest['version'] != 1: raise ValueError('Unknown dataset version')
    actual={p.name for p in path.iterdir() if p.name != 'manifest.json'}
    if actual != set(manifest['files']): raise ValueError('Dataset file set differs')
    for name,checksum in manifest['files'].items():
        if hashlib.sha256((path/name).read_bytes()).hexdigest() != checksum:
            raise ValueError(f'Dataset checksum mismatch: {name}')
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec',required=True,help='JSON input_specs list, local paths')
    p.add_argument('--output',required=True)
    p.add_argument('--heldout-groups',help='Previous frozen heldout-groups.json; mandatory for extensions')
    p.add_argument('--frozen-dataset',help='Prior snapshot; imports holdout references for cross-source duplicate checks')
    p.add_argument('--training-release',action='store_true')
    args=p.parse_args()
    frozen=json.loads(Path(args.heldout_groups).read_text()) if args.heldout_groups else None
    print(json.dumps(build(json.loads(Path(args.spec).read_text()),args.output,frozen,
                           training_release=args.training_release,frozen_dataset=args.frozen_dataset),indent=2))


if __name__ == '__main__': main()
