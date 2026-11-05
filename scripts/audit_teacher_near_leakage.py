"""Blind overlap screening; reports training IDs and similarities, never held-out text."""
import argparse, difflib, hashlib, json, re
from pathlib import Path

def normalize(text):
    return ' '.join(re.findall(r'\w+', text.casefold()))

def main(args):
    protected = []
    hashes = {}
    for split in ['development', 'confirmation']:
        p = args.evaluation / (split + '.jsonl')
        hashes[split] = hashlib.sha256(p.read_bytes()).hexdigest()
        for line in p.read_text().splitlines():
            row = json.loads(line)
            protected.append((split, normalize(row['turns'][0]['user'])))
    warnings, count = [], 0
    previous = []
    sources=[args.data] if args.data.is_file() else sorted(args.data.glob('batch-*.jsonl'))
    for p in sources:
        for line in p.read_text().splitlines():
            if not line.strip(): continue
            row = json.loads(line)
            text = normalize(next(m['content'] for m in row['messages'] if m['role'] == 'user'))
            count += 1
            for split, target in protected:
                ratio = difflib.SequenceMatcher(None, text, target, autojunk=False).ratio()
                if ratio >= .85:
                    warnings.append({'training_id': row['id'], 'protected_split': split, 'similarity': ratio, 'exact': text == target})
            for ident, target in previous:
                ratio = difflib.SequenceMatcher(None, text, target, autojunk=False).ratio()
                if ratio >= .9:
                    warnings.append({'training_id': row['id'], 'other_training_id': ident, 'similarity': ratio, 'exact': text == target})
            previous.append((row['id'], text))
    report = {'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, 'records': count, 'warnings': warnings, 'protected_sha256': hashes,
              'limitation': 'Lexical screen only, not semantic independence certification; no protected text emitted.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('data', type=Path)
    p.add_argument('--evaluation', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    main(p.parse_args())
