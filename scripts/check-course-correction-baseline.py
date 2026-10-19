"""Read-only verification of the actual fresh run and all displayed message/reply pairs."""
# Creator: Navneet Prabhakar
import importlib.util
import json
from pathlib import Path
from slm.data.stream_hash import sha


def main():
    root = Path('data/course-correction-baseline-v1')
    spec = importlib.util.spec_from_file_location('unchanged_integrity', 'scripts/check-current-conversations.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    checker.ROOT = root
    actual = checker.check()
    recorded = json.loads(Path('reports/course-correction-baseline-integrity.json').read_text())
    if actual != recorded: raise ValueError('Recorded reconstruction differs')
    old = [json.loads(x) for x in Path('data/current-model-100-conversations-v1/turns.jsonl').read_text().splitlines()]
    new = [json.loads(x) for x in (root/'turns.jsonl').read_text().splitlines()]
    if len(old) != len(new) or len(new) != 300: raise ValueError('Complete actual300turn runs required')
    for a, b in zip(old, new, strict=True):
        for key in ('conversation', 'category', 'turn', 'user', 'context_sha256'):
            if a[key] != b[key]: raise ValueError('Context differs; prior judgments cannot transfer')
        for key in ('text', 'token_ids', 'stop_reason', 'prompt_tokens', 'generated_tokens', 'content_tokens', 'max_new_tokens'):
            if a['response'][key] != b['response'][key]:
                raise ValueError('Actual output differs; direct regrading required')
    display = Path('docs/course-correction-100-transcripts.md')
    if display.read_text().split('## Conversation 1:', 1)[1] != Path('docs/current-model-100-transcripts.md').read_text().split('## Conversation 1:', 1)[1]:
        raise ValueError('Displayed message/response pairs differ')
    result = json.loads(Path('reports/course-correction-baseline-assessment.json').read_text())
    prior = json.loads(Path('reports/current-model-100-conversations-assessment.json').read_text())
    for key in ('successful_conversations', 'successful_turns', 'mean_score_out_of_100', 'dimension_means', 'categories'):
        if result[key] != prior[key]: raise ValueError('Transferred judgment differs')
    for key, path in {'integrity_sha256': 'reports/course-correction-baseline-integrity.json',
                      'turns_sha256': root/'turns.jsonl', 'readable_transcript_sha256': display,
                      'prior_assessment_sha256': 'reports/current-model-100-conversations-assessment.json'}.items():
        if result[key] != sha(path): raise ValueError('Result evidence changed')
    receipt = json.loads((root/'execution-receipt.json').read_text())
    if receipt['complete'] is not True or receipt['completion_sha256'] != sha(root/'completion.json'):
        raise ValueError('Actual fresh terminal receipt required')
    print(json.dumps(dict(creator='Navneet Prabhakar', complete=True, conversations=100, turns=300,
                         displayed_pairs_verified=300, successful_conversations=result['successful_conversations'],
                         successful_turns=result['successful_turns'], mean_score_out_of_100=result['mean_score_out_of_100'])))


if __name__ == '__main__': main()
