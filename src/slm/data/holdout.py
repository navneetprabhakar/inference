"""Exact candidate-evaluation isolation; no semantic contamination guarantee."""
from slm.data.schema import digest


def check_training_context(context,identifiers=()):
    from slm.eval.cases import heldout_prompts
    if any(isinstance(v,str) and any(v.startswith(prefix) or ':'+prefix in v for prefix in ('eval-v1/','eval-tools-v1/')) for v in identifiers):
        raise ValueError('Reserved evaluation family cannot enter training')
    # Match complete user/tool-ended prefixes, including a demonstration's context.
    for i,message in enumerate(context):
        if message.get('role') in ('user','tool') and digest(context[:i+1]) in heldout_prompts():
            raise ValueError('Exact held-out evaluation context cannot enter training')
