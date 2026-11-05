"""Prepare isolated clean-chat plus existing TRAIN-only English replay; never train."""
from collections import Counter, defaultdict
import argparse
import hashlib
import json
from pathlib import Path
import re
import numpy as np
from tokenizers import Tokenizer
from goal_training_records import encode_training_row

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/eight-hour-english-replay-v1'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def norm(text):
    return ' '.join(re.findall(r'\w+', text.casefold()))


def main(a):
    OUT = ROOT / a.output
    if OUT.exists():
        raise RuntimeError('Never overwrite a prepared corpus')
    clean = ROOT / 'data/eight-hour-permission-expanded-v1'
    clean_manifest = json.loads((clean / 'manifest.json').read_text())
    for name, expected in clean_manifest['files'].items():
        assert sha(clean / name) == expected
    rows = [json.loads(x) for x in (clean / 'records.jsonl').read_text().splitlines()]
    tokenizer_path = ROOT / 'data/sft-v3/tokenizer.json'
    assert sha(tokenizer_path) == sha(ROOT / 'data/pilot-v1/tokenizer.json')
    tok = Tokenizer.from_file(str(tokenizer_path))
    protected = defaultdict(set)
    pins = {}
    def protect(path, texts):
        pins[str(path.relative_to(ROOT))] = sha(path)
        for text in texts:
            text = norm(text)
            words = text.split()
            if words:
                protected[tuple(words[:min(5, len(words))])].add(text)
    for split in ['development', 'confirmation']:
        path = ROOT / f'data/eight-hour-improvement-v1/evaluation-v3-corrected-r2/{split}.jsonl'
        cases = [json.loads(x) for x in path.read_text().splitlines()]
        protect(path, [t['user'] for c in cases for t in c['turns']])
    for version in ['sft-v1', 'sft-v2', 'sft-v3']:
        for split in ['dev', 'test']:
            path = ROOT / f'data/{version}/{split}.jsonl'
            if path.exists():
                cases = [json.loads(x) for x in path.read_text().splitlines()]
                protect(path, [m['content'] for c in cases for m in c.get('episode', c.get('messages', [])) if m['role'] == 'user'])
    pools = defaultdict(list)
    def add(source, values, parent, offset):
        identity = hashlib.sha256(np.asarray(values, np.int32).tobytes()).hexdigest()
        pools[source].append((hashlib.sha256(('replay-2026110397' + identity).encode()).hexdigest(), identity, values, parent, offset))
    if a.replay_source == 'continuation':
        upstream = ROOT / 'data/continuation-v1/manifest.json'
        original = json.loads(upstream.read_text())
        upstream_sha256 = sha(upstream)
        assert sha(ROOT / 'data/continuation-v1/tokenizer.json') == sha(tokenizer_path)
        for source in ['wikipedia', 'pressbooks']:
            stream = ROOT / f'data/continuation-v1/{source}-train.bin'
            assert sha(stream) == original['sources'][source+'-train']['sha256']
            raw = np.memmap(stream, dtype=np.uint16, mode='r')
            rng = np.random.default_rng(2026110397 if source == 'wikipedia' else 2026110398)
            for segment in rng.choice((len(raw)-1)//128, 6000, replace=False):
                start = int(segment) * 128
                parent = {'id': f'continuation-{source}-{start}', 'provenance': {'path': str(stream), 'block': start//512}}
                add(source, np.asarray(raw[start:start+129], np.int32).tolist(), parent, start%512)
    else:
        upstream = ROOT / 'data/sft-v3/train.jsonl'
        original = json.loads((ROOT / 'data/sft-v3/manifest.json').read_text())
        upstream_sha256 = sha(upstream)
        assert upstream_sha256 == original['files']['train.jsonl']
        for r in map(json.loads, upstream.read_text().splitlines()):
            if r.get('objective') != 'causal_lm':
                continue
            assert r['provenance']['previous_split'] == 'train'
            source = 'fineweb' if 'fineweb' in r['id'] else 'tinystories'
            stream = ROOT / f'data/pilot-v1/{source}-train.bin'
            assert Path(r['provenance']['path']).resolve() == stream.resolve()
            raw = np.memmap(stream, dtype=np.uint16, mode='r')
            start = r['provenance']['block'] * 512
            assert np.array_equal(np.asarray(r['tokens']), raw[start:start + 513])
            for offset in [0, 128, 256, 384]:
                add(source, r['tokens'][offset:offset + 129], r, offset)
    seen = set()
    rejected = Counter()
    accepted = []
    for source, candidates in sorted(pools.items()):
        count = 0
        for _, identity, values, parent, offset in sorted(candidates, key=lambda x: x[0]):
            if identity in seen:
                rejected['duplicate_token_block'] += 1
                continue
            row = {'id': 'english-replay-' + identity, 'training_group': 'english_replay',
                   'objective': 'causal_lm', 'tokens': values,
                   'provenance': {'source': source, 'old_train_record': parent['id'],
                                  'source_index_path': str(upstream.relative_to(ROOT)), 'source_index_sha256': upstream_sha256,
                                  'path': parent['provenance']['path'], 'block': parent['provenance']['block'],
                                  'segment_offset': offset, 'previous_split': 'train',
                                  'review': 'existing raw English pretraining text; not chat-authored, not semantic certification'}}
            try:
                encode_training_row(tok, row, True)
            except ValueError:
                rejected['invalid_or_role_marker'] += 1
                continue
            text = norm(tok.decode(values, skip_special_tokens=False))
            words = text.split()
            if a.replay_source == 'continuation':
                decoded = tok.decode(values, skip_special_tokens=False)
                letters = [c for c in decoded if c.isalpha()]
                if not letters or sum(c.isascii() for c in letters)/len(letters) < .98 or not re.search(r'\b(the|is|are|was|were|with|from|that|this|and)\b', decoded, re.I):
                    rejected['language_heuristic'] += 1
                    continue
                if re.search(r'https?://|www\.|cheap.{0,30}(baclofen|zoloft|viagra|cialis)', decoded, re.I):
                    rejected['url_or_observed_spam_pattern'] += 1
                    continue
                if a.prose_screen:
                    function_words = {'the','a','an','and','is','are','was','were','to','of','in','for','with','on','that','this','as','by','from','be','or','it','not'}
                    lines = [line.split() for line in decoded.splitlines() if line.strip()]
                    if (sum(c.isdigit() for c in decoded)/max(len(decoded),1) > .04
                        or sum(w in function_words for w in words)/max(len(words),1) < .12
                        or len(re.findall(r'[.!?](?:\s|$)', decoded)) < 2
                        or (len(lines) >= 4 and sum(map(len, lines))/len(lines) < 12)
                        or re.search(r'\b(?:negro|nigger)\b', decoded, re.I)):
                        rejected['prose_replay_scope_screen'] += 1
                        continue
            candidates_to_check = set()
            for width in range(1, 6):
                for i in range(len(words) - width + 1):
                    candidates_to_check.update(protected.get(tuple(words[i:i + width]), ()))
            if any(t in text for t in candidates_to_check):
                rejected['protected_normalized_user_substring'] += 1
                continue
            seen.add(identity)
            accepted.append(row)
            count += 1
            if count == 1000:
                break
        assert count == 1000, (source, count)
    OUT.mkdir()
    rows += accepted
    (OUT / 'records.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n' for r in rows))
    sample = []
    for source in sorted(pools):
        for r in [r for r in accepted if r['provenance']['source'] == source][:8]:
            sample.append({'id': r['id'], 'source': source, 'text': tok.decode(r['tokens'], skip_special_tokens=False)})
    (OUT / 'replay-inspection-sample.json').write_text(json.dumps(sample, indent=2) + '\n')
    manifest = {'state': 'prepared_not_scheduled_not_trained', 'replay_source': a.replay_source, 'prose_screen': a.prose_screen, 'chat_tool_records': len(rows) - len(accepted),
                'raw_replay_segments': len(accepted), 'segment_targets': 128,
                'tokenizer_sha256': sha(tokenizer_path), 'clean_source_manifest_sha256': sha(clean / 'manifest.json'),
                'old_training_source_sha256': upstream_sha256, 'protected_split_hashes': pins,
                'rejected': dict(rejected), 'files': {'records.jsonl': sha(OUT / 'records.jsonl')},
                'limitations': ['Raw pretraining replay, not newly authored conversations.',
                               'Protected prompt substring screen is lexical, not semantic decontamination.',
                               'No change to the live V18 corpus or configuration.',
                               '128-token segments limit padding/gradient-weight imbalance; not a context extension.']}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'records': len(rows), 'replay': len(accepted), 'rejected': dict(rejected)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', default='data/eight-hour-english-replay-v1')
    p.add_argument('--replay-source', choices=['legacy', 'continuation'], default='legacy')
    p.add_argument('--prose-screen', action='store_true')
    main(p.parse_args())
