"""Exact candidate-evaluation isolation; no semantic contamination guarantee."""
from slm.data.schema import digest


def check_training_context(context,identifiers=()):
    from slm.eval.cases import heldout_prompts
    if any(isinstance(v,str) and (v.startswith('eval-v1/') or ':eval-v1/' in v) for v in identifiers):
        raise ValueError('Reserved evaluation family cannot enter training')
    # Match complete user/tool-ended prefixes, including a demonstration's context.
    for i,message in enumerate(context):
        if message.get('role') in ('user','tool') and digest(context[:i+1]) in heldout_prompts():
            raise ValueError('Exact held-out evaluation context cannot enter training')
