"""Summarize existing reviewed development results, never assign semantic scores."""
import hashlib
import json
from pathlib import Path
from score_goal_tool_calls import score

ROOT = Path(__file__).resolve().parents[1]
GOAL = ROOT / 'runs/eight-hour-improvement-v1'
SUITE = ROOT / 'data/eight-hour-improvement-v1/evaluation-v3-corrected-r2/development.jsonl'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    targets = [json.loads(x) for x in SUITE.read_text().splitlines() if x]
    rows = []
    candidates = []
    for number in range(7, 30):
        candidates.append((number, f'V{number}', 'evaluation-development-2m' if number == 12 else 'evaluation-development'))
        if number == 18:
            candidates.append((18, 'V18 (3M)', 'evaluation-development-3m'))
        if number == 21:
            candidates.append((21, 'V21 (159k)', 'evaluation-development-early'))
    for number, label, directory in candidates:
        run = ROOT / f'runs/eight-hour-improvement-v{number}'
        evaluation = run / directory
        review_path = evaluation / 'assistant-semantic-review.json'
        if not review_path.exists():
            continue
        review = json.loads(review_path.read_text())
        report = json.loads((evaluation / 'report.json').read_text())
        raw = json.loads((evaluation / 'raw-outputs.json').read_text())
        assert review['raw_outputs_sha256'] == sha(evaluation / 'raw-outputs.json')
        assert review['checkpoint_sha256'] == report['checkpoint_sha256']
        assert review['evaluation_sha256'] == report['evaluation_sha256'] == sha(SUITE)
        if 'decoding' in review:
            assert review['decoding'] == report['decoding']
        judgments = {r['id']: r for r in review['cases']}
        assert len(judgments) == len(raw) == len(targets)
        assert set(judgments) == {r['id'] for r in raw}
        for r in raw:
            c = judgments[r['id']]
            assert len(c['turn_passes']) == len(r['turns'])
            assert c['conversation_pass'] == all(c['turn_passes'])
        whole = sum(c['conversation_pass'] for c in judgments.values())
        turns = sum(sum(c['turn_passes']) for c in judgments.values())
        tools = sum(judgments[r['id']]['conversation_pass'] for r in raw if r['tool_mode'])
        assert whole == review['fully_correct_conversations']
        assert turns == review['fully_correct_turns']
        assert tools == review['tool_full_successes']
        calls = score(targets, raw)['groups']
        rows.append({'candidate': label, 'whole': whole, 'total': len(raw),
                     'turns': turns, 'total_turns': sum(len(r['turns']) for r in raw),
                     'prose_whole': whole - tools, 'tool_whole': tools,
                     'exact_calls': calls['required_call'], 'abstention': calls['required_abstention'],
                     'checkpoint': report['checkpoint'], 'checkpoint_sha256': report['checkpoint_sha256'],
                     'review': str(review_path.relative_to(ROOT)), 'review_sha256': sha(review_path),
                     'decoding': report['decoding'], 'report_sha256': sha(evaluation / 'report.json'),
                     'decoding_source': 'review_and_report' if 'decoding' in review else 'report_only_legacy_review_schema'})
    result = {'kind': 'existing_assistant_reviews_not_independent_human_review',
              'suite_sha256': sha(SUITE), 'confirmation': 'not included',
              'limitation': 'Repeated development selection is not unbiased final accuracy.', 'rows': rows}
    (GOAL / 'DEVELOPMENT_COMPARISON.json').write_text(json.dumps(result, indent=2) + '\n')
    lines = ['# Strict development comparison', '',
             'Assistant per-case judgments; not independent human review. All substantive turns must pass. Repeated development selection is not an unbiased final estimate. Confirmation and training-example probes are excluded.', '',
             '| Candidate | Whole /40 | Turns /80 | Prose /30 | Tool conversations /10 | Exact calls /8 | Abstentions /2 |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f"| {r['candidate']} | {r['whole']} | {r['turns']} | {r['prose_whole']} | {r['tool_whole']} | {r['exact_calls']['correct']} | {r['abstention']['correct']} |")
    lines += ['', 'Checkpoint, review and evaluation hashes are pinned in DEVELOPMENT_COMPARISON.json. No candidate is automatically promoted by this report.']
    (GOAL / 'DEVELOPMENT_COMPARISON.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'verified_reviewed_candidates': len(rows), 'output': str(GOAL / 'DEVELOPMENT_COMPARISON.md')}))


if __name__ == '__main__':
    main()
