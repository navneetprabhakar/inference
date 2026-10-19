"""Versioned text exclusions for future data intake; not a training release."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
from slm.data.prose_screen import RequestGuard, word_key
from slm.data.schema import digest
from slm.data.tokenized import sha

KINDS = {'request', 'generated_response'}
MAX_BYTES = 8 * 1024**2


def compile_inventory(records, bindings):
    """Deduplicate normalized text, preserving every type and evidence location.

    Short labels cannot be global exclusions: callers must retain their complete
    request/context separately. This schema refuses short records rather than
    silently dropping them or excluding common one-word answers everywhere.
    """
    if not isinstance(bindings, dict) or not bindings:
        raise ValueError('Pinned input bindings required')
    entries = {}
    count = 0
    for record in records:
        if set(record) != {'kind', 'text', 'origin'} or record['kind'] not in KINDS:
            raise ValueError('Explicit request/response record required')
        text, origin = record['text'], record['origin']
        if not isinstance(text, str) or not isinstance(origin, str) or not origin:
            raise ValueError('Text and evidence location required')
        key = word_key(text)
        RequestGuard([text])  # Preserve the existing nontrivial-text boundary.
        row = entries.setdefault(key, dict(text=text, key=key, origins=[], kinds=[]))
        row['origins'].append(origin)
        row['kinds'].append(record['kind'])
        count += 1
    if not entries:
        raise ValueError('Nonempty evaluation inventory required')
    rows = []
    for key in sorted(entries):
        row = entries[key]
        row['origins'] = sorted(set(row['origins']))
        row['kinds'] = sorted(set(row['kinds']))
        rows.append(row)
    guard = RequestGuard([r['text'] for r in rows])
    return dict(version=1, kind='evaluation-text-exclusions-v1', creator='Navneet Prabhakar',
        source_records=count, input_bindings=bindings, entries=rows,
        distinct_texts=len(rows), fingerprint=guard.fingerprint, training_approved=False,
        scope='Whole normalized request/generated-response sequences only. No paraphrase, arbitrary partial-span or unseen task-family guarantee. Existing data is not retroactively certified.')


class EvaluationExclusions:
    def __init__(self, path, expected_sha256):
        self.path = Path(path)
        self.expected_sha256 = expected_sha256
        if self.path.is_symlink() or not self.path.is_file() or self.path.stat().st_size > MAX_BYTES:
            raise ValueError('Bounded regular inventory file required')
        if sha(self.path) != expected_sha256:
            raise ValueError('External inventory hash differs')
        value = json.loads(self.path.read_text())
        if (value.get('version') != 1 or value.get('kind') != 'evaluation-text-exclusions-v1'
                or value.get('creator') != 'Navneet Prabhakar' or value.get('training_approved') is not False):
            raise ValueError('Unsupported exclusion inventory')
        records = []
        for row in value['entries']:
            if (set(row) != {'key', 'text', 'kinds', 'origins'} or row['key'] != word_key(row['text'])
                    or not row['kinds'] or not set(row['kinds']) <= KINDS or not row['origins']
                    or row['kinds'] != sorted(set(row['kinds']))
                    or row['origins'] != sorted(set(row['origins']))
                    or any(not isinstance(o, str) or not o for o in row['origins'])):
                raise ValueError('Invalid exclusion entry')
            records.append(row)
        keys = [r['key'] for r in records]
        if keys != sorted(set(keys)) or len(keys) != value['distinct_texts']:
            raise ValueError('Inventory order/count differs')
        self.guard = RequestGuard([r['text'] for r in records])
        if self.guard.fingerprint != value['fingerprint']:
            raise ValueError('Inventory fingerprint differs')
        self.entries = {digest(r['key']): r for r in records}
        self.value = value

    def matches(self, text):
        if not isinstance(text, str):
            raise ValueError('Raw text required')
        if self.path.is_symlink() or sha(self.path) != self.expected_sha256:
            raise ValueError('Exclusion inventory changed during use')
        return [dict(key_sha256=h, kinds=self.entries[h]['kinds'], origins=self.entries[h]['origins'])
                for h in self.guard.matches(text)]

    def inspect_record(self, record, fields=('text', 'prompt')):
        """Call before candidate eligibility; original payload is never edited."""
        if not isinstance(record, dict) or not any(k in record for k in fields):
            raise ValueError('At least one explicit raw text field required')
        hits = {key: self.matches(record[key]) for key in fields if key in record}
        return dict(blocked=any(hits.values()), hits=hits,
                    raw_record_sha256=digest(record), inventory_sha256=self.expected_sha256,
                    training_approved=False)
