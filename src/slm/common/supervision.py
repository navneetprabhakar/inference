"""Versioned supervision boundaries derived from the message stream."""
CONTINUATION = 'last-user-turn-v1'


def boundary(messages, supervision='all-assistant-v1', objective='assistant'):
    if supervision == 'all-assistant-v1':return -1
    if supervision != CONTINUATION:raise ValueError('Unknown supervision contract')
    if objective != 'assistant':raise ValueError('Continuation-only supervision requires assistant objective')
    users=[i for i,m in enumerate(messages) if m.get('role')=='user']
    if not users or users[-1]==len(messages)-1 or messages[-1].get('role')!='assistant':
        raise ValueError('Continuation requires a final user turn followed by an assistant completion')
    return users[-1]
