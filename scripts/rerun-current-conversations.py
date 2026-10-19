"""Explicit user-requested fresh execution of the unchanged100-conversation protocol."""
# Creator: Navneet Prabhakar
import importlib.util
import json
from pathlib import Path
from slm.data.stream_hash import sha

PLAN=Path('configs/current-model-conversation-rerun-v1.json')

def main():
    plan=json.loads(PLAN.read_text())
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Rerun input changed')
    spec=importlib.util.spec_from_file_location('frozen_current_conversation_runner',plan['runner'])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.OUT=Path(plan['output']);module.main()
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Rerun input changed during generation')
    receipt=dict(creator='Navneet Prabhakar',kind='actual-user-requested-conversation-rerun-v1',complete=True,
        wrapper_plan_sha256=sha(PLAN),wrapper_sha256=sha(__file__),
        completion_sha256=sha(module.OUT/'completion.json'),original_protocol_unchanged=True,
        model_updates=0,teacher_calls=0,cloud_spend=0,training_approved=False)
    (module.OUT/'rerun-receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')

if __name__=='__main__':main()
