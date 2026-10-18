"""Byte-level fixture serializer, NOT the planned production BPE tokenizer.

Content is always encoded as UTF-8 bytes (0..255), so text cannot inject role
IDs (256..262). Assistant loss includes end-of-turn, but not role markers.
"""
BOS, END = 256, 257
ROLES = {'system': 258, 'user': 259, 'assistant': 260, 'tool': 261}
PAD = 262
VOCAB_SIZE = 263


def serialize(messages):
    ids, supervised = [BOS], [0]
    for message in messages:
        role, content = message['role'], message['content']
        if role not in ROLES or not isinstance(content, str):
            raise ValueError('Invalid role or content')
        payload = list(content.encode('utf-8'))
        ids.extend([ROLES[role], *payload, END])
        supervised.extend([0, *([int(role == 'assistant')]*len(payload)), int(role == 'assistant')])
    return ids[:-1], ids[1:], supervised[1:]
