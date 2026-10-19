#!/usr/bin/env python3
"""One real pinned 1,000-row Parquet extraction; never training admission."""
# Creator: Navneet Prabhakar
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import resource
import time

from slm.common.tokenizer import BPE
from slm.data.parquet_ranges import BoundedParquet, ExactRanges, Limits
from slm.data.schema import digest
from slm.data.tokenized import sha


ROOT = Path('data/fineweb-parquet-rowgroup-audit-v1')
PROBE = Path('data/fineweb-parquet-transport-probe-v1')
REVISION = '87f09149ef4734204d70ed1d046ddc9ca3f2b8f9'


def publish(path, value):
    with path.open('x') as out:
        out.write(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    if ROOT.exists(): raise FileExistsError(ROOT)
    inventory = json.loads((PROBE / 'inventory.json').read_text())
    if sha(PROBE / 'inventory.json') != '2822faa0607d3823c93a3398481d7622183820fac96b9ac7494f85559c9ed6b2':
        raise ValueError('Pinned inventory differs')
    item = inventory[0]
    limits = Limits(network_bytes=8 * 1024**2, requests=4)
    frozen = Path('data/smol-content-review-v2/staged/heldout-groups.json')
    ancestor = json.loads((frozen.parent / 'manifest.json').read_text())
    if sha(frozen) != ancestor['files'][frozen.name]: raise ValueError('Heldout ancestry differs')
    url = f"https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu/resolve/{REVISION}/{item['path']}"
    plan = dict(creator='Navneet Prabhakar', kind='pinned-prose-rowgroup-audit-v1',
                revision=REVISION, inventory_sha256=sha(PROBE / 'inventory.json'), item=item,
                limits=asdict(limits), selected_row_groups=[0], successful_output_byte_cap=16 * 1024**2,
                source_sha256=sha('src/slm/data/parquet_ranges.py'), script_sha256=sha(__file__),
                frozen_heldouts_sha256=sha(frozen), training_approved=False)
    ROOT.mkdir()
    publish(ROOT / 'plan.json', plan)
    (ROOT / 'executed-reader.py').write_bytes(Path('src/slm/data/parquet_ranges.py').read_bytes())
    transport = ExactRanges(url, item['size'], '"' + item['xetHash'] + '"', limits)
    started = time.monotonic()
    try:
        reader = BoundedParquet(transport)
        table = reader.read_group(0)
        rows = table.to_pylist()
        if len(rows) != 1000 or len({r['id'] for r in rows}) != 1000:
            raise ValueError('Exact distinct 1000-row group required')
        prior = [json.loads(s) for s in Path('data/audit-v1/fineweb-edu/sample/rows.jsonl').read_text().splitlines()]
        if rows[:len(prior)] != prior:
            raise ValueError('Prior viewer prefix differs from pinned Parquet rows')
        frozen_groups = json.loads(frozen.read_text())
        payload = b''.join((json.dumps(dict(global_row_index=i, row=r, raw_record_sha256=digest(r),
                      source_group='HuggingFaceFW/fineweb-edu:' + r['id'],
                      original_frozen_partition=frozen_groups.get('HuggingFaceFW/fineweb-edu:' + r['id'])),
                      sort_keys=True, ensure_ascii=False) + '\n').encode() for i, r in enumerate(rows))
        if len(payload) > plan['successful_output_byte_cap']: raise ValueError('Output exceeds finite cap')
        (ROOT / 'rows.jsonl').write_bytes(payload)
        bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
        report = dict(creator='Navneet Prabhakar', kind=plan['kind'], plan_sha256=sha(ROOT / 'plan.json'),
                      source_revision=REVISION, file=item['path'], file_bytes=item['size'], rows=len(rows),
                      row_file_sha256=sha(ROOT / 'rows.jsonl'), output_bytes=len(payload),
                      decoded_arrow_bytes=table.nbytes, network_attempts=transport.attempts,
                      network_reserved_bytes_including_overread=transport.reserved_bytes,
                      successful_body_bytes=sum(r['bytes'] for r in transport.receipts), ranges=transport.receipts,
                      original_viewer_rows_equal=len(prior), original_heldout_rows_preserved=sum(
                          'HuggingFaceFW/fineweb-edu:' + r['id'] in frozen_groups for r in rows),
                      crawl_counts=dict(Counter(r['dump'] for r in rows)),
                      actual_student_bpe_content_tokens=sum(len(bpe.encode(r['text'])) for r in rows),
                      elapsed_seconds=time.monotonic() - started,
                      process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      training_approved=False, scope='One pinned prefix row group; source/transport/schema evidence only, not representative content review, corpus admission, model training or a hard RSS/decompression sandbox. macOS ru_maxrss is process lifetime bytes, not incremental reader memory. Whole-shard LFS hash not independently recomputed; network counters exclude protocol/redirect overhead.')
        publish(ROOT / 'result.json', report)
        publish(Path('reports/milestone-sixty-eight-rowgroup.json'), report)
        print(json.dumps({k: report[k] for k in ('rows', 'successful_body_bytes', 'decoded_arrow_bytes',
              'original_viewer_rows_equal', 'original_heldout_rows_preserved', 'actual_student_bpe_content_tokens')}, indent=2))
    except Exception as error:
        publish(ROOT / 'failure.json', dict(error_type=type(error).__name__,
                message='Row-group probe failed; no automatic replay or training',
                attempts=transport.attempts, reserved_bytes=transport.reserved_bytes, ranges=transport.receipts))
        raise SystemExit('Bounded row-group probe failed; inspect private evidence without logging redirect URLs') from None


if __name__ == '__main__': main()
