"""Fail-closed selection and once-only confirmation authorization for this goal."""
import hashlib
import json
import os
from pathlib import Path
from goal_decoding import DEFAULT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def authorize(selection_path, checkpoint, evaluation, output, goal, now, decoding=None):
    selection_path = Path(selection_path).resolve()
    selection = json.loads(selection_path.read_text())
    auth = json.loads((goal / 'authorization.json').read_text())
    if now >= auth['deadline_unix'] or (goal / 'STOP').exists():
        raise RuntimeError('confirmation deadline or STOP')
    if selection.get('training_closed') is not True:
        raise RuntimeError('Selection must explicitly close training')
    if selection.get('checkpoint_sha256') != sha(checkpoint / 'model.safetensors'):
        raise RuntimeError('Selected checkpoint hash mismatch')
    if selection.get('confirmation_sha256') != sha(evaluation / 'confirmation.jsonl'):
        raise RuntimeError('Selected confirmation hash mismatch')
    review_path = Path(selection['development_review']).resolve()
    if selection.get('development_review_sha256') != sha(review_path):
        raise RuntimeError('Development review changed after selection')
    review = json.loads(review_path.read_text())
    if review.get('checkpoint_sha256') != selection['checkpoint_sha256']:
        raise RuntimeError('Development review belongs to a different checkpoint')
    if decoding is not None:
        if selection.get('decoding') != decoding:
            raise RuntimeError('Selection decoding differs from requested confirmation')
        if review.get('decoding', DEFAULT) != decoding:
            raise RuntimeError('Development review belongs to different decoding')
    cases = review['cases']
    development = [json.loads(x) for x in (evaluation / 'development.jsonl').read_text().splitlines() if x]
    expected = {r['id']: r for r in development}
    if len(cases) != len(expected) or {c['id'] for c in cases} != set(expected):
        raise RuntimeError('Development review coverage mismatch')
    if not all(type(c.get('conversation_pass')) is bool and c.get('specific_reason') for c in cases):
        raise RuntimeError('Development review lacks explicit per-case decisions')
    accuracy = sum(c['conversation_pass'] for c in cases) / len(cases)
    tool_cases = [c for c in cases if expected[c['id']]['tool_mode']]
    tool_accuracy = sum(c['conversation_pass'] for c in tool_cases) / max(1, len(tool_cases))
    # Reserve the untouched suite for a credible candidate or final deadline report.
    if now < auth['deadline_unix'] - 1200 and (accuracy < .65 or tool_accuracy < .6):
        raise RuntimeError('Too early to consume confirmation for a weak candidate')
    identity = {'selection_sha256': sha(selection_path),
                'checkpoint_sha256': selection['checkpoint_sha256'],
                'confirmation_sha256': selection['confirmation_sha256'],
                'output': str(output.resolve()),
                'decoding': decoding if decoding is not None else dict(DEFAULT)}
    receipt_path = goal / 'confirmation-started.json'
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt['identity'] != identity:
            raise RuntimeError('Confirmation already committed to a different selection/output')
        return receipt
    receipt = {'identity': identity, 'started_unix': now,
               'development_accuracy': accuracy, 'development_tool_full_success': tool_accuracy,
               'training_closed': True}
    # Exclusive creation makes simultaneous attempts fail safely.
    fd = os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(receipt, f, indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    return receipt


def validate_completed_prefix(rows, records):
    """Only whole sequential conversations may be resumed; never silently skip cases."""
    if len(rows) > len(records) or [r.get('id') for r in rows] != [r['id'] for r in records[:len(rows)]]:
        raise RuntimeError('Confirmation resume prefix mismatch')
    for row, expected in zip(rows, records):
        turns = row.get('turns', [])
        if len(turns) != len(expected['turns']):
            raise RuntimeError('Incomplete conversation in confirmation resume')
        for actual, target in zip(turns, expected['turns']):
            if actual.get('user') != target['user'] or 'student_reply' not in actual:
                raise RuntimeError('Confirmation resume conversation differs from frozen case')
    return len(rows)
