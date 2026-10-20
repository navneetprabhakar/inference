"""Frozen numerical language harness with uniform data and explicit raw-ledger carry."""
# Creator: Navneet Prabhakar
import importlib.util
import json
from slm import english_language_stage as original
from slm.english_budget_v3 import Meter
from slm.data.english_corpus import save


def run(plan,root,corpus,tokenizer,plan_hash):
    spec=importlib.util.spec_from_file_location('_uniform_main_harness_v3',original.__file__)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    def carried(path,contract_hash,maximum=100000000,phase_maximum=78000000):
        return Meter(path,contract_hash,maximum,phase_maximum,priors=plan['prior_ledgers'])
    module.Meter=carried
    module.run(plan,root,corpus,tokenizer,plan_hash)
    # Qualify the unchanged harness's legacy descriptive96-update string.
    save(root/'language/lineage-summary.json',dict(creator='Navneet Prabhakar',
         source_checkpoint_manifest_sha256=plan['origin_checkpoint_sha256'],
         actual_source_steps=plan['origin_steps'],main_optimizer='explicit fresh AdamW',
         scope='Actual source counters/hashes govern. Base completion selected_source96 string is historical; raw base receipt is retained.'))
