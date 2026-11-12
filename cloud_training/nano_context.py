"""Explicit context transitions; larger framing capacity is not trained capability."""
DEFAULT_CONTEXT = 2048
MAX_CONTEXT = 4096
SUPPORTED_CONTEXTS = (2048, 4096)


def transition_config(parent_config, target, *, allow_extension=False):
    if type(target) is not int or target not in SUPPORTED_CONTEXTS:
        raise ValueError('Supported model contexts are2048 and4096;8K is not qualified')
    source = parent_config.get('sequence_len')
    if source not in SUPPORTED_CONTEXTS or type(source) is not int:
        raise ValueError('Unsupported parent context')
    if target == source:
        return dict(parent_config), None
    if (source, target) != (2048, 4096) or not allow_extension:
        raise ValueError('Context extension requires explicit2048-to4096 opt-in; no downgrade')
    config = dict(parent_config, sequence_len=target)
    record = {'from': source, 'to': target, 'position_policy': 'native_rope_no_rescaling',
              'attention_policy': 'native_sssl_quarter_and_full_windows',
              'requires_continuation_and_quality_evaluation': True}
    return config, record


def validate_context_edge(parent, child):
    config, record = transition_config(parent['config'], child['config'].get('sequence_len'),
                                       allow_extension=True)
    if child['config'] != config:
        raise ValueError('Ancestor architecture mismatch outside context length')
    if child.get('context_transition') != record:
        raise ValueError('Missing or mismatched explicit context transition')
