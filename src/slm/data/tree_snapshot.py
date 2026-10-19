"""Bounded complete OASST ready-tree acquisition; never training admission."""
# Creator: Navneet Prabhakar
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import urllib.request
from slm.data.acquire import fetch, open_response
from slm.data.build import read_source
from slm.data.tokenized import sha, stamp


FILENAME = '2023-11-05_oasst2_ready.trees.jsonl.gz'
MAX_COMPRESSED = 64*1024*1024
MAX_DECODED = 512*1024*1024
MAX_LINE = 8*1024*1024


def acquire(source_record, output):
    source_record, output = Path(source_record), Path(output)
    if output.exists():raise FileExistsError(output)
    source = read_source(source_record)
    if source.source_id != 'OpenAssistant/oasst2' or source.review_status == 'excluded':
        raise ValueError('Explicit pinned OASST2 source required')
    descriptor = json.loads(source_record.read_text())
    evidence = {name: source_record.parent/descriptor['evidence_files'][name] for name in ('card', 'license')}
    guards = {p.resolve(): stamp(p) for p in (source_record, *evidence.values(), Path(__file__))}
    metadata_url = f'https://huggingface.co/api/datasets/{source.source_id}/tree/{source.revision}?recursive=false&expand=false'
    raw, _ = fetch(metadata_url, limit=1024*1024)
    matches = [r for r in json.loads(raw) if r.get('type') == 'file' and r.get('path') == FILENAME]
    if len(matches) != 1:raise ValueError('Pinned ready-tree metadata missing or ambiguous')
    info = matches[0]; size = info.get('size'); expected = info.get('lfs', {}).get('oid')
    if (type(size) is not int or not 0 < size <= MAX_COMPRESSED or info.get('lfs', {}).get('size') != size
        or not isinstance(expected, str) or len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected)):
        raise ValueError('Published file size/SHA256 exceeds bounded acquisition contract')
    url = f'https://huggingface.co/datasets/{source.source_id}/resolve/{source.revision}/{FILENAME}'
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.tree-snapshot-', dir=output.parent))
    started = time.monotonic()
    try:
        request = urllib.request.Request(url, headers={'User-Agent':'portable-slm-source-audit/1', 'Accept-Encoding':'identity'})
        total = 0; h = hashlib.sha256()
        with open_response(request) as response, (temp/FILENAME).open('wb') as target:
            for chunk in iter(lambda: response.read(65536), b''):
                total += len(chunk)
                if total > size or total > MAX_COMPRESSED:raise ValueError('Compressed byte ceiling exceeded')
                if time.monotonic()-started > 180:raise ValueError('Download soft wall limit exceeded')
                h.update(chunk); target.write(chunk)
        if total != size or h.hexdigest() != expected:raise ValueError('Published size/SHA256 differs')
        decoded = trees = messages = 0; seen_trees = set(); seen_messages = set()
        with gzip.open(temp/FILENAME, 'rb') as source_stream, (temp/'trees.jsonl').open('wb') as target:
            while True:
                line = source_stream.readline(MAX_LINE+1)
                if not line:break
                decoded += len(line)
                if len(line) > MAX_LINE or decoded > MAX_DECODED:raise ValueError('Decoded tree/total byte ceiling exceeded')
                tree = json.loads(line)
                root = tree['prompt']; tid = tree['message_tree_id']
                if tree.get('tree_state') != 'ready_for_export' or tid != root['message_id'] or tid in seen_trees:
                    raise ValueError('Invalid or repeated ready-tree identity')
                seen_trees.add(tid); trees += 1
                if trees > 20000:raise ValueError('Tree count ceiling exceeded')
                stack = [(root, None, 0)]
                while stack:
                    node, parent, depth = stack.pop(); key = node['message_id']
                    if (depth > 128 or key in seen_messages or node.get('parent_id') != parent
                        or node.get('role') != ('prompter' if depth%2 == 0 else 'assistant')
                        or not isinstance(node.get('text'), str)):
                        raise ValueError('Invalid raw message lineage/role/text')
                    seen_messages.add(key); messages += 1
                    if messages > 200000:raise ValueError('Message count ceiling exceeded')
                    children = node.get('replies', [])
                    if not isinstance(children, list):raise ValueError('Invalid child list')
                    stack.extend((child, key, depth+1) for child in children)
                target.write(line)
        if not trees:raise ValueError('Empty ready-tree snapshot')
        for name, path in evidence.items():shutil.copyfile(path, temp/(name+'.txt'))
        descriptor['evidence_files'] = {**descriptor['evidence_files'], 'card':'card.txt', 'license':'license.txt'}
        (temp/'source.json').write_text(json.dumps(descriptor, indent=2, sort_keys=True)+'\n')
        read_source(temp/'source.json')
        (temp/'file-metadata.json').write_text(json.dumps(dict(metadata_url=metadata_url, metadata_sha256=hashlib.sha256(raw).hexdigest(), file=info), indent=2, sort_keys=True)+'\n')
        for path, before in guards.items():
            if stamp(path) != before:raise ValueError('Acquisition code or source evidence changed')
        report = dict(creator='Navneet Prabhakar', release='sample_only', source_id=source.source_id,
                      source_revision=source.revision, url=url, compressed_bytes=total,
                      compressed_sha256=expected, decoded_bytes=decoded, trees=trees, messages=messages,
                      decoded_sha256=sha(temp/'trees.jsonl'), source_descriptor_sha256=sha(source_record),
                      implementation_sha256=sha(__file__), elapsed_seconds=time.monotonic()-started,
                      max_compressed_bytes=MAX_COMPRESSED, max_decoded_bytes=MAX_DECODED,
                      training_eligible=False, source_rights_approved=False,
                      scope='Complete pinned multilingual raw ready-tree export, not approved training data. Preserve synthetic/deleted/review/privacy metadata for separate admission.')
        (temp/'acquisition.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
        os.rename(temp, output)
        return report
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-record', required=True); p.add_argument('--output', required=True)
    args = p.parse_args(); print(json.dumps(acquire(args.source_record, args.output), sort_keys=True))


if __name__ == '__main__':main()
