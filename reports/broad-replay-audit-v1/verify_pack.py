"""Independent membership, provenance and byte comparison for filtered replay."""
import hashlib
import json
from pathlib import Path
import shutil
import time

ROOT = Path(__file__).resolve().parents[2]


def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    start = time.monotonic()
    old = ROOT/'data/base-foundation-100m'
    new = ROOT/'data/broad-replay-v1'
    report = Path(__file__).parent
    output = new/'verification.json'
    assert not output.exists()
    m = json.loads((new/'manifest.json').read_text())
    assert m['state'] == 'packed_pending_independent_verification' and not m['training_admitted']
    assert m['source_manifest'] == {'path':str(old/'manifest.json'), 'sha256':digest(old/'manifest.json')}
    for pin in m['evidence']:
        assert digest(Path(pin['path'])) == pin['sha256']
    original = json.loads((old/'manifest.json').read_text())
    assert digest(old/'documents.jsonl') == original['documents_sha256']
    audit = json.loads((report/'result.json').read_text())
    public = json.loads((report/'public-custody.json').read_text())
    excluded = set(public['excluded_doc_ids'])
    for pin in audit['custody']:
        assert digest(Path(pin['path'])) == pin['sha256']
        excluded.update(json.loads(Path(pin['path']).read_text())['excluded_doc_ids'])
    source = [json.loads(line) for line in (old/'documents.jsonl').open()]
    domains = {d['group'] for d in source if d['document_id'] in excluded}
    assert set(m['excluded_domain_families']) == domains
    removed = [d['document_id'] for d in source if d['split']=='train' and d['group'] in domains]
    assert removed == m['excluded_document_ids']
    retained = [d for d in source if d['split']=='validation' or d['group'] not in domains]
    actual = [json.loads(line) for line in (new/'documents.jsonl').open()]
    assert len(actual) == len(retained)
    assert digest(new/'documents.jsonl') == m['documents_sha256']
    counts = {}
    for split in ('train', 'validation'):
        assert digest(old/f'fineweb-{split}.u16') == original['shards'][f'fineweb-{split}']['sha256']
        want = [d for d in retained if d['split']==split]
        got = [d for d in actual if d['split']==split]
        assert len(want)==len(got)
        position = 0
        with (old/f'fineweb-{split}.u16').open('rb') as src, (new/f'{split}.u16').open('rb') as dst:
            for before, after in zip(want, got):
                assert time.monotonic()-start < 600
                assert not (ROOT/'runs/STOP').exists() and not (report/'STOP').exists()
                for key, value in before.items():
                    assert after[key] == (position if key=='offset' else value)
                assert after['original_offset']==before['offset'] and after['file']==f'{split}.u16'
                src.seek(2*before['offset'])
                original_bytes = src.read(2*before['tokens'])
                packed_bytes = dst.read(2*before['tokens'])
                assert original_bytes == packed_bytes and len(packed_bytes)==2*before['tokens']
                assert hashlib.sha256(packed_bytes).hexdigest()==after['token_sha256']
                assert packed_bytes[-2:]==(50256).to_bytes(2, 'little')
                position += before['tokens']
            assert not dst.read(1)
        shard = m['shards'][split]
        assert shard['tokens']==position and shard['documents']==len(got)
        assert shard['sha256']==digest(new/f'{split}.u16')
        counts[split] = dict(documents=len(got), tokens=position)
    assert m['shards']['validation']['sha256']==original['shards']['fineweb-validation']['sha256']
    assert shutil.disk_usage(ROOT).free > 20*1024**3
    result = dict(state='PASS_independent_replay_packing_not_admitted', failures=[],
                  manifest_sha256=digest(new/'manifest.json'), verified=counts,
                  excluded_domains=len(domains), excluded_documents=len(removed),
                  validation_unchanged=True, every_retained_byte_compared=True,
                  training_admitted=False, seconds=time.monotonic()-start)
    with output.open('x') as f:
        json.dump(result, f, indent=2); f.write('\n')
    (report/'packing-result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__': main()
