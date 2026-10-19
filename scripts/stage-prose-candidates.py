#!/usr/bin/env python3
"""Use existing exact/near-duplicate staging; candidate output stays sample-only."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
import shutil

from slm.data.adapters import rows
from slm.data.schema import Source
from slm.data.staging import stage
from slm.data.tokenized import sha

ROOT = Path('data/fineweb-prose-candidate-staging-v1')
PARENT = Path('data/smol-content-review-v2/staged')
SCREEN = Path('data/fineweb-prose-screen-v1')


def read(path): return json.loads(path.read_text())
def lines(path): return [json.loads(line) for line in path.read_text().splitlines()]


def publish(path, value):
    with path.open('x') as out: out.write(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    if ROOT.exists(): raise FileExistsError(ROOT)
    screen = read(SCREEN / 'report.json')
    if sha(SCREEN / 'screened.jsonl') != screen['screen_file_sha256']: raise ValueError('Screen bytes differ')
    selected = {r['source_group']: r for r in lines(SCREEN / 'screened.jsonl') if r['candidate']}
    raw = {}
    for path in ('data/fineweb-parquet-rowgroup-audit-v1/rows.jsonl', 'data/fineweb-prose-distributed-audit-v1/rows.jsonl'):
        for record in lines(Path(path)): raw[record['source_group']] = record['row']
    original_sources = read(PARENT / 'sources.json')
    fineweb = Source(**original_sources['HuggingFaceFW/fineweb-edu'])
    limits = dict(max_input_bytes=16 * 1024**2, max_records=12000, max_record_bytes=1024**2,
                  max_shingles=100000, max_pair_checks=500000, max_db_bytes=768 * 1024**2)
    plan = dict(creator='Navneet Prabhakar', kind='screened-prose-sample-staging-v1',
                screen_report_sha256=sha(SCREEN / 'report.json'), parent_manifest_sha256=sha(PARENT / 'manifest.json'),
                candidate_groups=len(selected), limits=limits, script_sha256=sha(__file__),
                training_approved=False, seed='slm-splits-v1')
    ROOT.mkdir(); publish(ROOT / 'plan.json', plan)
    new_path = ROOT / 'candidate-prose.jsonl'
    with new_path.open('x') as out:
        for group in sorted(selected):
            item = rows(fineweb, [raw[group]], 'prose')[0]
            if item.parent_group_id != group: raise ValueError('Candidate source group differs')
            item.validation_results['prose_candidate_screen'] = dict(
                raw_record_sha256=selected[group]['raw_record_sha256'],
                screen_report_sha256=sha(SCREEN / 'report.json'), training_approved=False)
            out.write(json.dumps(item.to_dict(), sort_keys=True, ensure_ascii=False) + '\n')
    evidence = list(PARENT.glob('evidence-*'))
    by_hash = {sha(path): path for path in evidence}
    empty = ROOT / 'empty.jsonl'; empty.write_text('')
    specs = []
    for i, (name, description) in enumerate(sorted(original_sources.items())):
        folder = ROOT / f'source-{i:02d}'; folder.mkdir()
        for field, target in (('card_sha256', 'card.txt'), ('license_text_sha256', 'license.txt')):
            shutil.copyfile(by_hash[description[field]], folder / target)
        source_record = dict(description, evidence_files=dict(card='card.txt', license='license.txt'))
        publish(folder / 'source.json', source_record)
        path = new_path if name == fineweb.source_id else empty
        specs.append(dict(path=str(path), sha256=sha(path), source_record=str(folder / 'source.json'), adapter='canonical'))
    publish(ROOT / 'specs.json', specs)
    result = stage(specs, ROOT / 'staged', limits=limits, seed=plan['seed'], frozen_dataset=PARENT)
    report = dict(creator='Navneet Prabhakar', kind=plan['kind'], plan_sha256=sha(ROOT / 'plan.json'),
                  staged_manifest_sha256=sha(ROOT / 'staged/manifest.json'), stage_report=result,
                  training_approved=False, scope='Existing sample-only staging, exact/near grouping before splits, all ancestral heldout rows imported. Existing cleaner may normalize/redact; raw rows retained by hash. No research admission or training release; final actual lineage/partition/content-change audit still required.')
    publish(ROOT / 'report.json', report)
    publish(Path('reports/milestone-sixty-nine-prose-staging.json'), report)
    print(json.dumps(dict(status='sample-only staging complete', candidate_groups=len(selected)), indent=2))


if __name__ == '__main__': main()
