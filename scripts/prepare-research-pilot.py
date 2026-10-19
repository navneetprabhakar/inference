#!/usr/bin/env python3
"""Freeze a pilot tokenizer and finite actual-data schedule; never launch training."""
# Creator: Navneet Prabhakar
from dataclasses import asdict
import json
from pathlib import Path
from slm.common.config import Config
from slm.common.training import Recipe
from slm.common.tokenizer import BPE
from slm.data.tokenized import build_shards,sha
from slm.data.mixture import build_mixture
from slm.train import Inputs


def write(path,data):path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')


def main():
    root=Path('data/context-research-pilot-v2').resolve()
    if root.exists():raise FileExistsError(root)
    release=Path('data/context-research-release-v1').resolve()
    candidates=Path('data/context-research-tokenizers-v1').resolve()
    tokenizer=candidates/'vocab-16384';bpe=BPE.load(tokenizer)
    config=Config(**json.loads(Path('configs/target-81m.json').read_text()))
    if bpe.vocab_size!=config.vocab_size:raise ValueError('Pilot requires the measured full 16K candidate')
    root.mkdir()
    freeze=dict(version=1,scope='local_foundation_smoke_only',production_frozen=False,
        tokenizer_manifest_sha256=sha(tokenizer/'manifest.json'),release_manifest_sha256=sha(release/'manifest.json'),
        comparison_sha256=sha(candidates/'comparison.json'),selected_vocab_size=bpe.vocab_size,parameters=config.parameter_count,
        selection='Keep the planned 81M architecture and smaller vocabulary head for this bounded pilot. Both candidates reach requested size; small handcrafted development slices cannot select a production tokenizer.',
        limitations='Tokenizer training contains reference prose only; dialogue/slang/tool/product breadth remains open. No validation/test text entered BPE training.')
    write(root/'tokenizer-freeze.json',freeze)
    prepared=build_shards(release,tokenizer,root/'tokens','foundation',context_length=1024,max_positions=2000000)
    mixture=build_mixture([dict(id='context_prose',path=str(root/'tokens'),dataset_hash=prepared['dataset_hash'],
        weight=1,max_passes=2,max_positions=1048576)],tokenizer,root/'mixture',objective='foundation',
        budget=1048576,minimum=1000000,group_cap=32768,seed='foundation-smoke-20261019-v1',max_batches=10000)
    recipe=Recipe(lr=.001,warmup_tokens=32768,beta1=.9,beta2=.95,eps=1e-8,decay=.1,clip=1.,
        accumulation_steps=1,loss_implementation='legacy-logsumexp-minus-target-v1',embedding_implementation='dense-onehot-v1')
    spec=dict(version=1,scope='language_pilot',config=config.to_dict(),recipe=asdict(recipe),seed=20261019,
        tokenizer=str(tokenizer),releases={sha(release/'manifest.json'):str(release)},
        data=dict(kind='mixture',path=str(root/'mixture'),fingerprint=mixture['dataset_hash'],bindings={'context_prose':str(root/'tokens')}),
        limits=dict(updates=2048,processed_positions=1048576),checkpoint=dict(every_updates=128,keep=2))
    write(root/'pilot.json',spec)
    inputs=Inputs(spec)
    try:
        report=dict(creator='Navneet Prabhakar',tokenizer_freeze=freeze,token_preparation=prepared,mixture=mixture,
            preflight_plan_hash=inputs.identity,research_limits=inputs.research_limits,pilot_spec_sha256=sha(root/'pilot.json'),
            script_sha256=sha(__file__),public_data_model_updates=0,new_teacher_launches=0,cloud_jobs=0,
            scope='Actual-data preparation and checked pilot preflight; no trained checkpoint or capability claim.')
        write(root/'preparation.json',report);write(Path('reports/milestone-thirty-nine-pilot-preparation.json'),report)
        print(json.dumps(dict(plan_hash=inputs.identity,tokenizer_vocab=bpe.vocab_size,
            prepared_positions=prepared['processed_prediction_positions'],scheduled_positions=mixture['planned_processed_positions'],
            max_passes=2),indent=2))
    finally:inputs.close()


if __name__=='__main__':main()
