"""Count committed stage exposures to diagnostic records; do not infer prior history."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def digest(messages):
    return hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def main(a):
    run = ROOT / f'runs/eight-hour-improvement-v{a.version}'
    config = json.loads((run / 'training-config.json').read_text())
    checkpoint = run / 'training' / json.loads((run / 'training/latest.json').read_text())['directory']
    if a.version == 11:
        checkpoint = ROOT / json.loads((ROOT / 'runs/eight-hour-improvement-v1/best-development-candidate.json').read_text())['checkpoint']
    state = json.loads((checkpoint / 'state.json').read_text())
    data = ROOT / config['data_dir']
    manifest = json.loads((data / 'manifest.json').read_text())
    for name, expected in manifest['files'].items():
        assert hashlib.sha256((data / name).read_bytes()).hexdigest() == expected
    records = [json.loads(x) for x in (data / 'records.jsonl').read_text().splitlines()]
    order = json.loads((data / 'order.json').read_text())['order']
    lengths = np.load(data / 'episodes.npz')['length']
    batches = []
    size = config['batch_size']
    for j in range(0, len(order), 64):
        block = sorted(order[j:j + 64], key=lambda i: int(lengths[i]))
        batches += [block[k:k + size] for k in range(0, len(block), size) if len(block[k:k + size]) == size]
    committed = batches[:state['cursor']]
    assert sum(sum(int(lengths[i]) - 1 for i in b) for b in committed) == state['nonpadding_input_tokens']
    counts = Counter(digest(records[i]['messages']) for batch in committed for i in batch)
    membership = {digest(r['messages']) for r in records}
    probe = ROOT / 'data/eight-hour-training-probe-v1'
    refs = json.loads((probe / 'manifest.json').read_text())['references']
    source = {r['id']: r for r in map(json.loads, (ROOT / 'data/eight-hour-permission-expanded-v1/records.jsonl').read_text().splitlines())}
    rows = []
    for ref in refs:
        key = digest(source[ref['source_id']]['messages'])
        rows.append({**ref, 'in_stage_corpus': key in membership, 'committed_stage_exposures': counts[key],
                     'exposure_conclusion': 'verified_seen_in_this_stage' if counts[key] else 'not_seen_in_this_stage_prior_lineage_unknown'})
    result = {'checkpoint': str(checkpoint.relative_to(ROOT)), 'checkpoint_sha256': state['model_sha256'],
              'stage_input_tokens': state['nonpadding_input_tokens'], 'cases': rows,
              'limitation': 'Counts this committed stage only. Zero is not proof of absence from earlier lineage.'}
    out = run / 'training-probe-exposure.json'
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'version': a.version, 'verified_seen_cases': sum(r['committed_stage_exposures'] > 0 for r in rows), 'total': len(rows)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--version', type=int, required=True)
    main(p.parse_args())
