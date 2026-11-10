"""Materialize a reviewed, hash-bound campaign without modifying prep artifacts.

This verifies artifact integrity, whole-file duplicates, split identities and a
root review binding. It does not independently certify document-level leakage,
license suitability or benchmark contamination. No cloud operations are performed.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import shutil

from cloud_training.nano_data import PackedRows, sha256_file

REQUIRED_TARGETS = 10_000_269_312
INVENTORY = 'gs://forge-ownbase-a100-20261110/ownbase-v2/corpus-inventory'


def write_json(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write('\n')


def materialize(candidate_path, review_path, destination, *, metadata_prefix, inventory_prefix=INVENTORY):
    """Root review requires approved:true, candidate_sha256, tokenizer_sha256,
    ordered source_manifest_sha256 list, reviewer and nonempty evidence list.
    Existing destinations are refused. Admission never changes source manifests.
    """
    candidate_path, review_path = Path(candidate_path).resolve(), Path(review_path).resolve()
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    for prefix in (inventory_prefix, metadata_prefix):
        if not re.fullmatch(r'gs://[a-z0-9][a-z0-9._-]+/[A-Za-z0-9/_.-]+', prefix) or '..' in prefix.split('/'):
            raise ValueError('Invalid GCS prefix')
    candidate_bytes, review_bytes = candidate_path.read_bytes(), review_path.read_bytes()
    candidate, review = json.loads(candidate_bytes), json.loads(review_bytes)
    import hashlib
    candidate_sha = hashlib.sha256(candidate_bytes).hexdigest()
    review_sha = hashlib.sha256(review_bytes).hexdigest()
    if candidate.get('schema') != 1 or candidate.get('training_admitted') is not False:
        raise ValueError('Expected an unadmitted candidate')
    if (candidate.get('sequence_length'),candidate.get('vocab_size')) != (2048,32768):
        raise ValueError('Unsupported campaign dimensions')
    for split in ('train','validation'):
        if not isinstance(candidate.get(split),list) or not candidate[split]:
            raise ValueError('Both ordered splits are required')
    source_hashes = [e['manifest_sha256'] for split in ('train','validation') for e in candidate[split]]
    if (review.get('schema') != 1 or review.get('approved') is not True
        or review.get('candidate_sha256') != candidate_sha
        or review.get('tokenizer_sha256') != candidate.get('tokenizer_sha256')
        or review.get('source_manifest_sha256') != source_hashes
        or not isinstance(review.get('reviewer'),str) or not review['reviewer'].strip()
        or not isinstance(review.get('evidence'),list) or not review['evidence']):
        raise ValueError('Root review must bind this candidate, tokenizer and ordered source manifests')
    verified, seen, paths, train_targets = [], set(), set(), 0
    for split in ('train','validation'):
        for entry in candidate[split]:
            source = (candidate_path.parent / entry['directory']).resolve()
            name = source.name
            if not re.fullmatch(r'shard_[0-9]+',name):
                raise ValueError('Source directory must have stable shard_N name')
            relative = f'packed/{split}/{name}'
            if relative in paths: raise ValueError('Duplicate output shard path')
            paths.add(relative)
            if sha256_file(source/'manifest.json') != entry['manifest_sha256']:
                raise ValueError('Source manifest changed')
            reader = PackedRows(source,expected_tokenizer_sha256=candidate['tokenizer_sha256'],expected_split=split)
            manifest = reader.manifest
            if (manifest['sequence_length'],manifest['vocab_size']) != (2048,32768):
                raise ValueError('Shard dimensions differ')
            if manifest.get('training_admitted') is not False:
                raise ValueError('Expected original unadmitted prep manifest')
            if manifest.get('target_tokens') != manifest['rows']*2048:
                raise ValueError('Incorrect target count')
            if manifest['sha256'] in seen: raise ValueError('Duplicate payload or cross-split whole-file overlap')
            seen.add(manifest['sha256'])
            if split == 'train': train_targets += manifest['rows']*2048
            verified.append((split,source,relative,entry['manifest_sha256'],manifest))
    if train_targets < REQUIRED_TARGETS:
        raise ValueError(f'Production requires {REQUIRED_TARGETS} targets; found {train_targets}')
    destination.mkdir(parents=True,exist_ok=False)
    try:
        (destination/'root-review.json').write_bytes(review_bytes)
        (destination/'source-candidate.json').write_bytes(candidate_bytes)
        campaign = {k:candidate[k] for k in ('schema','tokenizer_sha256','sequence_length','vocab_size')}
        campaign.update(training_admitted=True,train=[],validation=[])
        files = []
        for split,source,relative,source_sha,original in verified:
            target = destination/relative;target.mkdir(parents=True)
            payload = target/'rows.u16'
            try: os.link(source/'rows.u16',payload)
            except OSError: shutil.copyfile(source/'rows.u16',payload)
            if sha256_file(payload) != original['sha256'] or payload.stat().st_size != original['bytes']:
                raise ValueError('Payload changed during materialization')
            admitted = dict(original,training_admitted=True,prep_manifest_sha256=source_sha,
                root_review_sha256=review_sha,admission_note='Admitted by bound root review; integrity verified by nano_admit.')
            write_json(target/'manifest.json',admitted)
            campaign[split].append({'directory':relative,'manifest_sha256':sha256_file(target/'manifest.json')})
            files.append({'path':relative+'/rows.u16','uri':inventory_prefix.rstrip('/')+'/'+split+'/'+source.name+'/rows.u16',
                          'sha256':original['sha256'],'bytes':original['bytes']})
        receipt = {'schema':1,'training_admitted':True,'tokenizer_sha256':candidate['tokenizer_sha256'],
            'candidate_sha256':candidate_sha,'source_manifest_sha256':source_hashes,'root_review_sha256':review_sha,
            'shard_manifest_sha256':[e['manifest_sha256'] for split in ('train','validation') for e in campaign[split]],
            'train_targets':train_targets,'required_targets':REQUIRED_TARGETS,
            'duplicate_check_scope':'whole payload files only; document-level findings belong to root review'}
        write_json(destination/'admission.json',receipt)
        campaign['admission'] = {'receipt':'admission.json','sha256':sha256_file(destination/'admission.json')}
        # Publication marker is the campaign manifest, written only after validation.
        from cloud_training.nano_train import read_campaign
        write_json(destination/'campaign.json',campaign)
        read_campaign(destination/'campaign.json')
        metadata_paths = ['campaign.json','admission.json','root-review.json','source-candidate.json']
        metadata_paths += [relative+'/manifest.json' for _,_,relative,_,_ in verified]
        for relative in metadata_paths:
            path = destination/relative
            files.append({'path':relative,'uri':metadata_prefix.rstrip('/')+'/'+relative,
                          'sha256':sha256_file(path),'bytes':path.stat().st_size})
        write_json(destination/'data-index.json',{'schema':1,'campaign_path':'campaign.json',
            'campaign_sha256':sha256_file(destination/'campaign.json'),
            'tokenizer_sha256':candidate['tokenizer_sha256'],'files':files})
        return {'campaign':str(destination/'campaign.json'),'campaign_sha256':sha256_file(destination/'campaign.json'),
                'data_index_sha256':sha256_file(destination/'data-index.json'),'train_targets':train_targets}
    except BaseException:
        shutil.rmtree(destination)
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',required=True);p.add_argument('--root-review',required=True)
    p.add_argument('--output',required=True);p.add_argument('--metadata-prefix',required=True)
    p.add_argument('--inventory-prefix',default=INVENTORY)
    a=p.parse_args()
    print(json.dumps(materialize(a.candidate,a.root_review,a.output,metadata_prefix=a.metadata_prefix,inventory_prefix=a.inventory_prefix),indent=2))


if __name__=='__main__':main()
