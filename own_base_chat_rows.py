"""Pure text-chat SFT alignment; no corpus access or teacher-quality certification."""
from copy import deepcopy
import hashlib
import json

from dialogue import IGNORE
from own_base_chat import policy_text
from own_base_sft_rows import last_turn_row

TRANSFORMATION_VERSION = 'publisher-system-to-first-user-v1'
POSITION_BINS = ((0, 255), (256, 511), (512, 767), (768, 1023))


def build_chat_rows(tokenizer, source_history, *, provenance=None,
                    permit_calls=True, allowed_names=None):
    """Return all turn-prefix rows atomically, or refuse the entire history.

Original texts are retained in separate metadata. Relocation is an explicit
training-format proposal, not a claim that publisher instructions are runtime
host policy. Position counts refer to raw predicted-token positions, i.e.
shifted label index + 1, and count supervised targets only.
    """
    if not isinstance(source_history, (list, tuple)) or not source_history:
        raise ValueError('nonempty source history required')
    original = deepcopy(list(source_history))
    for message in original:
        if type(message) is not dict or set(message) != {'role', 'text'}:
            raise ValueError('only exact role/text messages accepted; no tool frames')
        if not isinstance(message['text'], str) or not message['text'].strip():
            raise ValueError('nonempty text required')
        message['text'].encode('utf-8')
    canonical = json.dumps(original, ensure_ascii=False, sort_keys=True,
                           separators=(',', ':'), allow_nan=False).encode('utf-8')
    transformed = deepcopy(original)
    publisher_system = None
    if transformed[0]['role'] == 'system':
        publisher_system = transformed.pop(0)['text']
    if not transformed or len(transformed) % 2:
        raise ValueError('complete user/assistant pairs required')
    for index, message in enumerate(transformed):
        if message['role'] != ('user' if index % 2 == 0 else 'assistant'):
            raise ValueError('only alternating user/assistant text pairs accepted')
    if publisher_system is not None:
        transformed[0]['text'] = ('Task instructions:\n' + publisher_system +
                                  '\n\nInput:\n' + transformed[0]['text'])
    host_policy = policy_text(permit_calls, allowed_names)
    histories, rows = [], []
    exposure = {f'{low}..{high}': 0 for low, high in POSITION_BINS}
    per_row = []
    for end in range(2, len(transformed) + 1, 2):
        history = [dict(role='system', text=host_policy)] + deepcopy(transformed[:end])
        row = last_turn_row(tokenizer, history, reply_budget=256, context=1024)
        row_exposure = dict.fromkeys(exposure, 0)
        for index, label in enumerate(row.labels):
            if label != IGNORE:
                position = index + 1
                if not 0 <= position < 1024:
                    raise ValueError('supervised position outside frozen context')
                key = f'{(position // 256) * 256}..{(position // 256) * 256 + 255}'
                row_exposure[key] += 1
                exposure[key] += 1
        histories.append(history)
        rows.append(row)
        per_row.append(row_exposure)
    return dict(histories=histories, rows=rows,
                metadata=dict(original_history=original,
                              original_history_sha256=hashlib.sha256(canonical).hexdigest(),
                              transformation_version=TRANSFORMATION_VERSION,
                              publisher_system_relocated=publisher_system is not None,
                              provenance=deepcopy(provenance), teacher_quality_certified=False),
                counters=dict(source_messages=len(original), turns=len(rows), rows=len(rows),
                              supervised_targets=sum(row.target_count for row in rows)),
                position_exposure=exposure, per_row_position_exposure=per_row)
