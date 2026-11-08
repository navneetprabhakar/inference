"""Copy whole retained documents into a new corpus; never modify original data."""
import hashlib
import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/base-foundation-100m'
OUTPUT = ROOT / 'data/broad-replay-v1'
REPORT = Path(__file__).parent


def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    start = time.monotonic()
    def check():
        assert not (ROOT / 'runs/STOP').exists() and not (REPORT / 'STOP').exists()
        assert time.monotonic()-start < 600 and shutil.disk_usage(ROOT).free > 20*1024**3
    check()
    assert not OUTPUT.exists()
    audit = json.loads((REPORT / 'result.json').read_text())
    public = json.loads((REPORT / 'public-custody.json').read_text())
    assert audit['state'] == 'PASS_existing_train_replay_integrity_not_admission'
    assert public['state'] == 'screened_not_admitted' and not public['training_admitted']
    assert public['audit_sha256'] == sha(REPORT / 'result.json')
    m = json.loads((SOURCE / 'manifest.json').read_text())
    assert sha(SOURCE / 'manifest.json') == audit['manifest_sha256'] == public['manifest_sha256']
    assert sha(SOURCE / 'documents.jsonl') == m['documents_sha256']
    docs = [json.loads(line) for line in (SOURCE / 'documents.jsonl').open()]
    denied = set(public['excluded_doc_ids'])
    for pin in audit['custody']:
        p = Path(pin['path']); assert sha(p) == pin['sha256']
        denied.update(json.loads(p.read_text())['excluded_doc_ids'])
    families = {d['group'] for d in docs if d['document_id'] in denied}
    assert not families & {d['group'] for d in docs if d['split'] == 'validation'}
    for split in ('train', 'validation'):
        assert sha(SOURCE / f'fineweb-{split}.u16') == m['shards'][f'fineweb-{split}']['sha256']
    OUTPUT.mkdir()
    shards = {}; removed = []
    with (OUTPUT / 'documents.jsonl').open('x') as index:
        for split in ('train', 'validation'):
            count = offset = 0
            with (SOURCE / f'fineweb-{split}.u16').open('rb') as src, (OUTPUT / f'{split}.u16').open('xb') as dst:
                for d in docs:
                    if d['split'] != split: continue
                    check()
                    if split == 'train' and d['group'] in families:
                        removed.append(d['document_id']); continue
                    src.seek(2*d['offset']); raw = src.read(2*d['tokens'])
                    assert len(raw) == 2*d['tokens']
                    dst.write(raw)
                    record = dict(d, original_offset=d['offset'], offset=offset,
                                  file=f'{split}.u16', token_sha256=hashlib.sha256(raw).hexdigest())
                    index.write(json.dumps(record)+'\n')
                    offset += d['tokens']; count += 1
            shards[split] = dict(file=f'{split}.u16', tokens=offset, documents=count,
                                 sha256=sha(OUTPUT / f'{split}.u16'))
    result = dict(state='packed_pending_independent_verification', training_admitted=False,
                  source_manifest=dict(path=str(SOURCE/'manifest.json'), sha256=sha(SOURCE/'manifest.json')),
                  evidence=[dict(path=str(REPORT/n), sha256=sha(REPORT/n)) for n in
                            ('result.json', 'public-custody.json', 'filter-proposal.json')],
                  shards=shards, documents_sha256=sha(OUTPUT/'documents.jsonl'),
                  excluded_domain_families=sorted(families), excluded_document_ids=removed,
                  seconds=time.monotonic()-start,
                  limitation='Original TRAIN replay only. Excluding matches cannot erase any historical weight exposure. Public development is diagnostic, not clean acceptance evidence.')
    (OUTPUT/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(state=result['state'], shards=shards, excluded_documents=len(removed))))


if __name__ == '__main__': main()
