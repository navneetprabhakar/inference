"""Human review packets and checked training releases. Decisions are never inferred."""
from collections import defaultdict, Counter
from copy import deepcopy
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import tempfile
from slm.data.build import verify
from slm.data.schema import digest

CATEGORIES = {'sfw', 'mature_language', 'adult_topic', 'adult_fiction'}
PRIORITY = {'train': 0, 'validation': 1, 'test': 2}
REVIEWER = 'Navneet Prabhakar'


def records(path):
    result = {}
    for split in PRIORITY:
        for shard in sorted(Path(path).glob(f'{split}-*.jsonl')):
            for line in shard.read_text().splitlines():
                item = json.loads(line)
                if item['split'] != split or item['example_id'] in result:
                    raise ValueError('Invalid dataset record identity or partition')
                result[item['example_id']] = item
    return result


def oasst_mapping(record):
    proof=record['validation_results'].get('upstream_mapping',{})
    root=record['parent_group_id'].removeprefix(record['source']+':')
    if (proof.get('method')!='oasst-official-id-projection-v1'
        or proof.get('source_revision')!=record['source_revision'] or proof.get('root_id')!=root
        or proof.get('split') not in PRIORITY or proof.get('split')!=record['official_split']
        or not re.fullmatch('[a-f0-9]{64}',proof.get('bundle_sha256',''))):
        raise ValueError('Verified OASST official mapping required; manual split override refused')
    return proof


def prepare(dataset, output, limit=40):
    dataset, output = Path(dataset), Path(output)
    verify(dataset)
    if output.exists(): raise FileExistsError(output)
    if limit < 1: raise ValueError('Positive review limit required')
    items = records(dataset)
    buckets = defaultdict(list)
    for item in sorted(items.values(), key=lambda e: e['example_id']):
        buckets[(item['source'], item['split'])].append(item)
    selected = []
    while buckets and len(selected) < limit:
        for key in sorted(list(buckets)):
            selected.append(buckets[key].pop(0))
            if not buckets[key]: del buckets[key]
            if len(selected) == limit: break
    packet = {'version': 1, 'dataset_manifest_sha256': hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest(),
        'reviewer': None, 'human_attestation': False,
        'source_reviews': {name: {'source_record': source, 'source_sha256': digest(source),
                          'approved': None, 'terms_reviewed': None, 'allowed_categories': [],
                          'evidence_note': ''}
            for name, source in sorted(json.loads((dataset/'sources.json').read_text()).items())},
        'examples': {e['example_id']: {'record': e, 'record_sha256': digest(e),
                       'decision': {'approved': None, 'english_verified': None,
                                    'privacy_verified': None, 'quality_verified': None,
                                    'content_category': None, 'upstream_partition': None,
                                    'partition_evidence': '', 'note': ''}}
                     for e in selected}}
    for entry in packet['examples'].values():
        record=entry['record']
        if record['source']=='OpenAssistant/oasst2' and 'upstream_mapping' in record['validation_results']:
            proof=oasst_mapping(record)
            entry['decision']['upstream_partition']=proof['split']
            entry['decision']['partition_evidence']='Machine-verified official ID projection; bundle SHA-256 '+proof['bundle_sha256']
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as stream: stream.write(json.dumps(packet, sort_keys=True, ensure_ascii=False, indent=2)+'\n')
    return {'selected': len(selected), 'sources': len(packet['source_reviews']),
            'approved': 0, 'dataset_manifest_sha256': packet['dataset_manifest_sha256']}


def check_packet(packet, sources, input_records=None):
    if packet.get('version') != 1 or packet.get('reviewer') != REVIEWER or packet.get('human_attestation') is not True:
        raise ValueError('Explicit human review attestation required')
    if set(packet['source_reviews']) != set(sources): raise ValueError('Source review set differs')
    for name, entry in packet['source_reviews'].items():
        if entry['source_sha256'] != digest(sources[name]) or entry['source_record'] != sources[name]:
            raise ValueError('Source review provenance differs')
        if entry['approved'] not in (None, True, False) or (entry['approved'] is not None and type(entry['approved']) is not bool):
            raise ValueError('Source approval must be boolean or pending')
        if entry['approved'] is True:
            if (entry['terms_reviewed'] is not True or not entry['evidence_note'].strip()
                or not entry['allowed_categories'] or not set(entry['allowed_categories']) <= CATEGORIES):
                raise ValueError('Source terms/category review incomplete')
    accepted, group_splits = {}, defaultdict(list)
    packet_hash = digest(packet)
    for key, entry in packet['examples'].items():
        record, decision = entry['record'], entry['decision']
        if key != record['example_id'] or digest(record) != entry['record_sha256']:
            raise ValueError('Reviewed record identity/content differs')
        if input_records is not None and (key not in input_records or record != input_records[key]):
            raise ValueError('Review does not match frozen input record')
        if record['source'] not in sources or record['source_revision'] != sources[record['source']]['revision']:
            raise ValueError('Reviewed source revision differs')
        if record['license_record'] != digest(sources[record['source']]):
            raise ValueError('Reviewed license provenance differs')
        if record['split'] not in PRIORITY: raise ValueError('Invalid input partition')
        group = record['validation_results']['split_group']
        group_splits[group].append(record['split'])
        upstream = decision['upstream_partition']
        if upstream is not None:
            if upstream not in PRIORITY or not decision['partition_evidence'].strip():
                raise ValueError('Upstream partition evidence required')
            # Known held-out identity protects the group even if this item is rejected.
            group_splits[group].append(upstream)
        approved = decision['approved']
        if approved is not None and type(approved) is not bool:
            raise ValueError('Example approval must be boolean or pending')
        if approved is not True: continue
        if record['source']=='OpenAssistant/oasst2':
            proof=oasst_mapping(record)
            if upstream!=proof['split']:raise ValueError('Manual split override disagrees with verified OASST mapping')
        source_review = packet['source_reviews'][record['source']]
        if (source_review['approved'] is not True or upstream is None
            or any(decision[k] is not True for k in ('english_verified','privacy_verified','quality_verified'))
            or decision['content_category'] not in source_review['allowed_categories']):
            raise ValueError('Example review gates incomplete')
        item = deepcopy(record)
        item['language'] = 'en'
        item['content_category'] = decision['content_category']
        for gate in ('language_review','content_review','privacy_review','quality_review'):
            item['validation_results'][gate] = 'human_attested'
        item['validation_results']['human_review'] = {
            'packet_sha256': packet_hash, 'reviewed_record_sha256': entry['record_sha256']}
        accepted[key] = item
    for item in accepted.values():
        item['split'] = max(group_splits[item['validation_results']['split_group']], key=PRIORITY.get)
    if not accepted: raise ValueError('No approved records; no training release')
    return accepted


def release(dataset, review_file, destination):
    dataset, destination = Path(dataset), Path(destination)
    if destination.exists(): raise FileExistsError(destination)
    verify(dataset)
    packet = json.loads(Path(review_file).read_text())
    if hashlib.sha256((dataset/'manifest.json').read_bytes()).hexdigest() != packet['dataset_manifest_sha256']:
        raise ValueError('Reviewed dataset manifest differs')
    sources = json.loads((dataset/'sources.json').read_text())
    approved = check_packet(packet, sources, records(dataset))
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.review-release-', dir=destination.parent))
    try:
        for split in PRIORITY:
            selected = [v for _,v in sorted(approved.items()) if v['split'] == split]
            if selected:
                (temp/f'{split}-00000.jsonl').write_text(''.join(json.dumps(v, sort_keys=True, ensure_ascii=False)+'\n' for v in selected))
        (temp/'sources.json').write_text(json.dumps(sources, sort_keys=True, indent=2)+'\n')
        (temp/'review.json').write_text(json.dumps(packet, sort_keys=True, ensure_ascii=False, indent=2)+'\n')
        report = {'release':'training', 'approved_examples':len(approved),
                  'splits':dict(Counter(e['split'] for e in approved.values())),
                  'categories':dict(Counter(e['content_category'] for e in approved.values())),
                  'parent_dataset_manifest_sha256':packet['dataset_manifest_sha256'],
                  'review_packet_sha256':digest(packet),
                  'limitation':'Checks attestations and record integrity; cannot prove human judgment or legal clearance.'}
        (temp/'report.json').write_text(json.dumps(report, sort_keys=True, indent=2)+'\n')
        manifest = {'version':1, 'release':'training', 'review_schema_version':1,
                    'parent_dataset_manifest_sha256':packet['dataset_manifest_sha256'],
                    'review_packet_sha256':digest(packet),
                    'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(temp.iterdir())}}
        (temp/'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n')
        os.rename(temp,destination)
    except BaseException:
        shutil.rmtree(temp,ignore_errors=True); raise
    return report


def training_examples(path):
    """Only approved train shards; review packets and evaluation text are never yielded."""
    path = Path(path)
    manifest = verify(path)
    if manifest.get('release') != 'training' or manifest.get('review_schema_version') != 1:
        raise ValueError('Reviewed training release required; sample-only data is refused')
    packet = json.loads((path/'review.json').read_text())
    if (digest(packet) != manifest['review_packet_sha256']
        or packet['dataset_manifest_sha256'] != manifest['parent_dataset_manifest_sha256']):
        raise ValueError('Review lineage differs')
    expected = check_packet(packet,json.loads((path/'sources.json').read_text()))
    actual = records(path)
    if actual != expected: raise ValueError('Released records differ from approved review')
    for key in sorted(actual):
        if actual[key]['split'] == 'train': yield deepcopy(actual[key])


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command',required=True)
    a = sub.add_parser('prepare');a.add_argument('--dataset',required=True);a.add_argument('--output',required=True);a.add_argument('--limit',type=int,default=40)
    b = sub.add_parser('release');b.add_argument('--dataset',required=True);b.add_argument('--review',required=True);b.add_argument('--output',required=True)
    args=p.parse_args()
    result=prepare(args.dataset,args.output,args.limit) if args.command=='prepare' else release(args.dataset,args.review,args.output)
    print(json.dumps(result,indent=2))


if __name__ == '__main__': main()
