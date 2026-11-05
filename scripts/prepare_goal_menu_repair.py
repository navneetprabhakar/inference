"""Prepare a separate candidate corpus; never mutate a running training dataset."""
import copy
import hashlib
import json
from pathlib import Path

from tokenizers import Tokenizer
from sft_common import ROOT, SCHEMAS, encode_episode, system
from audit_teacher_fixture_trajectories import audit


def main():
    source = ROOT / 'data/eight-hour-improvement-v9/records.jsonl'
    out = ROOT / 'data/eight-hour-menu-repair-v1'
    out.mkdir(exist_ok=False)
    tok = Tokenizer.from_file(str(ROOT / 'data/sft-v3/tokenizer.json'))
    rows = [json.loads(s) for s in source.read_text().splitlines()]
    admitted, decisions = [], []
    menu_index = 0
    for original in rows:
        row = copy.deepcopy(original)
        if row['training_group'] == 'short_upstream':
            decisions.append({'id': row['id'], 'decision': 'quarantine',
                              'reason': 'Unverified upstream subset; random audit found substantive factual errors. This does not assert every row is wrong.'})
            continue
        changed = False
        if row['training_group'] in ('positive_tools', 'tool_boundaries'):
            for message in row['messages']:
                if message['role'] != 'system' or 'Tools: ' not in message['content']:
                    continue
                menu = json.JSONDecoder().raw_decode(message['content'].split('Tools: ', 1)[1])[0]
                if len(menu) == 1:
                    # 80% of formerly single-tool episodes now contain distractors.
                    # Rotate menu order to avoid a fixed position shortcut.
                    if menu_index % 5 != 0:
                        names = list(SCHEMAS)
                        shift = menu_index % len(names)
                        message['content'] = system(names[shift:] + names[:shift])
                        changed = True
                    menu_index += 1
        if encode_episode(tok, row['messages']) is None:
            decisions.append({'id': row['id'], 'decision': 'quarantine',
                              'reason': 'Full episode exceeds context after menu expansion; no truncation.'})
            continue
        admitted.append(row)
        if changed:
            decisions.append({'id': row['id'], 'decision': 'menu_repair',
                              'reason': 'Expose all five tools in varied order; user messages, tool calls and results unchanged.'})
    records = out / 'records.jsonl'
    records.write_text(''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n' for r in admitted))
    (out / 'decisions.json').write_text(json.dumps(decisions, indent=2) + '\n')
    result = audit([records])
    (out / 'fixture-context-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    assert not result['errors'], result['errors']
    manifest = {'state': 'prepared_only_no_training_schedule',
                'records': len(admitted), 'original_records': len(rows),
                'source': str(source.relative_to(ROOT)),
                'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in out.iterdir() if p.is_file()},
                'limitations': ['Only menu changes are newly validated; prior semantic provenance remains unchanged.',
                                'No new prompts or answers are authored here; no held-out text used.',
                                'Quarantined records remain in the original frozen source.']}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'records': len(admitted), 'decisions': len(decisions),
                      'quarantined': sum(r['decision'] == 'quarantine' for r in decisions),
                      'menu_repairs': sum(r['decision'] == 'menu_repair' for r in decisions),
                      'fixture_errors': len(result['errors'])}))


if __name__ == '__main__':
    main()
