"""Explicit decoding identity, shared by selection and held-out evaluation."""
import math
DEFAULT = {'greedy': True, 'seed': 20261102, 'cap': 96, 'penalty': 1.2}
def policy(prose_penalty=1.2, tool_penalty=1.2):
    if any(not math.isfinite(v) or not 1 <= v <= 2 for v in (prose_penalty, tool_penalty)):
        raise ValueError('Repetition penalties must be finite and within1..2')
    result = {**DEFAULT, 'penalty': prose_penalty}
    if tool_penalty != prose_penalty: result['tool_penalty'] = tool_penalty
    return result

def penalty_for(decoding, tool_mode):
    return decoding.get('tool_penalty', decoding['penalty']) if tool_mode else decoding['penalty']
