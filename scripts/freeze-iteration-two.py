#!/usr/bin/env python3
"""Freeze optimizer ablation, physical exposure and validation before updates."""
# Creator: Navneet Prabhakar
from dataclasses import asdict
import json
from pathlib import Path
from slm.common.config import Config
from slm.common.training import Recipe
from slm.common.tokenizer import BPE
from slm.data.mixture import build_mixture,MixtureBatches
from slm.data.review_stream import open_checked
from slm.data.tokenized import sha
from slm.data.schema import digest
from slm.eval.iteration_two import select,SEED
from slm.train import Inputs


def write(path,value):
    with path.open('x') as out:out.write(json.dumps(value,indent=2,sort_keys=True)+'\n')


def main():
    root=Path('data/iteration-two-experiment-v1').resolve()
    if root.exists():raise FileExistsError(root)
    root.mkdir()
    release=Path('data/iteration-two-foundation-research-v1').resolve()
    tokenizer=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384').resolve()
    tokens=Path('data/iteration-two-foundation-prepared-v1/tokens').resolve()
    prepared=json.loads(Path('reports/milestone-forty-seven-token-preparation.json').read_text())
    if prepared['token_preparation']['dataset_hash']!=sha(tokens/'manifest.json'):raise ValueError('Frozen prepared tokens differ')
    budget=10485760;screen_positions=262144;main_budget=budget-screen_positions
    mixture=build_mixture([dict(id='foundation',path=str(tokens),dataset_hash=sha(tokens/'manifest.json'),weight=1,max_passes=2,max_positions=main_budget)],
        tokenizer,root/'schedule',objective='foundation',budget=main_budget,minimum=10000000,group_cap=32768,
        seed='iteration-two-foundation-20261019-v1',max_batches=16000,allow_mixed_sources=True)
    with MixtureBatches(root/'schedule',{'foundation':str(tokens)},tokenizer) as schedule:
        if schedule.counts(256)!=(screen_positions,screen_positions):raise ValueError('Screens require identical 256 full 1024-position batches')
    config=Config(**json.loads(Path('configs/target-81m.json').read_text()));plans={};specs={}
    for trial,rate in [('lr-0003',.0003),('lr-0010',.001)]:
        recipe=Recipe(lr=rate,warmup_tokens=32768,beta1=.9,beta2=.95,eps=1e-8,decay=.1,clip=1.,accumulation_steps=1,
            embedding_implementation='dense-onehot-v1',loss_implementation='legacy-logsumexp-minus-target-v1')
        spec=dict(version=1,scope='language_pilot',config=config.to_dict(),recipe=asdict(recipe),seed=20261019,tokenizer=str(tokenizer),
            releases={sha(release/'manifest.json'):str(release)},data=dict(kind='mixture',path=str(root/'schedule'),fingerprint=mixture['dataset_hash'],bindings={'foundation':str(tokens)}),
            limits=dict(updates=12288,processed_positions=main_budget),checkpoint=dict(every_updates=128,keep=2))
        write(root/(trial+'.json'),spec);specs[trial]=dict(spec_file_sha256=sha(root/(trial+'.json')),learning_rate=rate)
        inputs=Inputs(spec)
        try:plans[trial]=inputs.identity
        finally:inputs.close()
    with open_checked(release) as index:groups=select(index,BPE.load(tokenizer))
    protocol=dict(version=1,creator='Navneet Prabhakar',scope='iteration_two_local_foundation_research',
        release_manifest_sha256=sha(release/'manifest.json'),tokenizer_manifest_sha256=sha(tokenizer/'manifest.json'),
        schedule_manifest_sha256=mixture['dataset_hash'],specs=specs,plan_hashes=plans,seed=20261019,selection_seed=SEED,
        groups=groups,groups_sha256=digest(groups),
        validation='32 SHA-ranked distinct eligible validation groups per source, one canonical full conversation per group; at most 1024 positions and at least 16 assistant targets. No truncation. Equal-source mean of per-group mean NLL.',
        optimizer_choice='After both complete 256-update screens: lower source-balanced full-foundation NLL wins; choose 3e-4 when its NLL is within 0.01 nats of 1e-3. Assistant-target NLL is secondary and cannot replace the declared selection metric. No test-set model scores.',
        smoke='After selected terminal schedule: compare canonical-random and final source-balanced group NLL; require finite values, mean foundation improvement >=0.1 nats and positive lower 95% source-stratified group bootstrap bound (10000 draws, seed 20261019). Report assistant-target changes separately. No capability acceptance inferred.',
        exposure=dict(cumulative_physical_position_ceiling=budget,screen_updates_each=256,screen_positions_each=screen_positions,
            selected_chain_position_ceiling=main_budget,planned_selected_chain_positions=mixture['planned_processed_positions'],
            max_planned_physical_positions=mixture['planned_processed_positions']+screen_positions,
            discarded_screen_max_positions=screen_positions,max_passes_per_selected_chain=2,
            max_physical_exposures_per_prepared_batch_across_both_chains=3,
            accounting='Both screens start from identical random weights and consume the same schedule prefix. Resume only the selected chain under its unchanged plan. Selected screen work is included in selected-chain totals, not counted twice. Discarded screen work adds physical exposure. No third trial, replay update or fresh restart is budgeted. Failure reservations remain consumed until actual work is reconciled; no automatic retries.'),
        invocation=dict(screen_soft_wall_seconds=1800,continuation_soft_wall_seconds=21600,
            checkpoint_every_updates=128,screen_order=['lr-0003','lr-0010'],concurrency=1),
        comparison_limitations='Single seed and small validation subset: exploratory optimizer choice, not confidence in broad conversation quality. Full-source test token sizing was disclosed previously but test losses are not used. Frozen task families remain protected. This is a foundation stage; later admitted assistant-target SFT and actual conversations are still required.',
        source_sha256={p:sha(p) for p in ['scripts/freeze-iteration-two.py','src/slm/eval/iteration_two.py','src/slm/data/mixture.py']},
        model_updates_before_freeze=0,model_scores_observed_before_freeze=0)
    write(root/'protocol.json',protocol)
    receipt={k:v for k,v in protocol.items() if k!='groups'}
    receipt.update(protocol_sha256=sha(root/'protocol.json'),mixture=mixture,selected_validation_groups=len(groups),
        group_source_counts={s:sum(g['source']==s for g in groups) for s in sorted({g['source'] for g in groups})})
    write(Path('reports/milestone-forty-eight-experiment-freeze.json'),receipt)
    print(json.dumps(dict(plans=plans,exposure=protocol['exposure'],groups=len(groups)),indent=2),flush=True)


if __name__=='__main__':main()
