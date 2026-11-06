"""Current-turn supervision and exact reply-reservation checks for own-base SFT.

No corpus reads or model execution. The caller supplies the current host policy
as the leading system frame. Earlier assistant frames provide context only.
"""
from dialogue import CONTEXT, IGNORE, TrainingRow, _frames, assistant_prompt, training_row


def validate_reply_reservations(tokenizer, history, *, reply_budget=256, context=CONTEXT):
    """Validate every teacher response against the actual inference framing."""
    training_row(tokenizer, history, context=context)
    lengths = []
    for index, message in enumerate(history):
        if message['role'] != 'assistant':
            continue
        prompt = assistant_prompt(tokenizer, history[:index], reply_budget=reply_budget, context=context)
        complete, _, _ = _frames(tokenizer, history[:index+1])
        if complete[:len(prompt)] != prompt:
            raise ValueError('teacher and inference assistant prefixes differ')
        body = complete[len(prompt):]
        if not 0 < len(body) <= reply_budget:
            raise ValueError('teacher frame exceeds frozen generation budget')
        lengths.append(dict(message_index=index, prefix_tokens=len(prompt), reply_tokens=len(body)))
    return lengths


def last_turn_row(tokenizer, history, *, reply_budget=256, context=CONTEXT):
    """Supervise only assistant frames following the last user message.

This avoids supervising older turns under the *current* tool permission policy.
All assistant calls and final text in the current turn remain supervised; tool,
user, system and role-header tokens remain ignored.
"""
    row = training_row(tokenizer, history, context=context)
    validate_reply_reservations(tokenizer, history, reply_budget=reply_budget, context=context)
    users = [i for i, message in enumerate(history) if message['role'] == 'user']
    if not users:
        raise ValueError('current user turn required')
    prefix, _, _ = _frames(tokenizer, history[:users[-1]])
    labels = list(row.labels)
    boundary = max(0, len(prefix)-1)  # Shifted labels predict raw token i+1.
    labels[:boundary] = [IGNORE]*boundary
    result = TrainingRow(list(row.inputs), labels)
    if result.target_count == 0:
        raise ValueError('current turn has no supervised assistant targets')
    return result
