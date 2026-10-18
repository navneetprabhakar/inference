"""Exact candidate-evaluation isolation; no semantic contamination guarantee."""
from slm.data.schema import digest


def check_training_context(context,identifiers=()):
    from slm.eval.cases import heldout_prompts
    if any(isinstance(v,str) and any(v.startswith(prefix) or ':'+prefix in v for prefix in ('eval-v1/','eval-tools-v1/')) for v in identifiers):
        raise ValueError('Reserved evaluation family cannot enter training')
    # Match complete user/tool-ended prefixes, including a demonstration's context.
    for i,message in enumerate(context):
        prefix=context[:i+1]
        candidates=(prefix,prefix[1:]) if prefix[0].get('role')=='system' else (prefix,)
        if message.get('role') in ('user','tool') and any(digest(v) in heldout_prompts() for v in candidates):
            raise ValueError('Exact held-out evaluation context cannot enter training')
