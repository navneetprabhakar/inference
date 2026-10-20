"""Reuse the frozen language harness with explicit carried physical accounting."""
# Creator: Navneet Prabhakar
import importlib.util
from slm import english_language_stage as original
from slm.english_budget_v2 import Meter


def run(plan, root, corpus, tokenizer, plan_hash):
    spec = importlib.util.spec_from_file_location('_carried_english_language_v2', original.__file__)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    def carried(path, contract_hash, maximum=100000000, phase_maximum=78000000):
        return Meter(path, contract_hash, maximum, phase_maximum, prior=plan['prior_physical_ledger'])
    module.Meter = carried
    module.run(plan, root, corpus, tokenizer, plan_hash)
