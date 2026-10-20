"""Freeze a source-balanced correction, retaining discarded work and strict gates."""
# Creator: Navneet Prabhakar
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import sqlite3
from slm.data.english_corpus import lines, save, build_tokens, verify_tokens
from slm.data.english_foundation_adapter import build_mixture, build_curriculum
from slm.common.training import Recipe
from slm.common.tokenizer import BPE
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.english_learning import compare_learning

OLD = Path('data/english-recovery-experiment-v1')
CORPUS = Path('data/english-recovery-corpus-v1')
TOK = Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
OUT = Path('data/english-balanced-preliminary-v2')
ROOT = Path('data/english-balanced-experiment-v2')


def read(path): return json.loads(Path(path).read_text())


def main():
    if OUT.exists() or ROOT.exists(): raise FileExistsError('Preserve previous balanced preparation')
    terminal = read('data/english-local-continuation-v1/supervisor-terminal.json')
    if terminal.get('complete') is not False: raise ValueError('Retained failed first handoff required')
    old_plan = read(OLD/'plan.json')
    for path, expected in old_plan['inputs'].items():
        if sha(path) != expected: raise ValueError('Original frozen dependency differs')
    failure = compare_learning(read(OLD/'common-nll.json'), read(OLD/'mlx-nll.json'), .02)
    if failure['passed'] or failure['source_improvements_nats']['general'] >= -.1:
        raise ValueError('Actual retained general-source regression required')
    prior_path = OLD/'physical.sqlite'
    db = sqlite3.connect('file:'+str(prior_path.resolve())+'?mode=ro', uri=True)
    charges = db.execute('SELECT phase,cursor,positions,status FROM charges ORDER BY cursor').fetchall(); db.close()
    if charges != [('common' if i<32 else 'mlx', i*8, 8192, 'complete') for i in range(96)]:
        raise ValueError('All original physical work must be sealed and retained')
    prior = dict(path=str(prior_path), sha256=sha(prior_path), positions=786432, preliminary_positions=786432)
    rows = {r['sid']:r for r in lines(CORPUS/'train.jsonl')}
    prelim = list(lines(CORPUS/'preliminary/lineage.jsonl'))
    retention = list(lines(CORPUS/'reserved-replay/lineage.jsonl'))
    pools = {}
    for source in ('general','narrative'):
        pools['common-'+source] = [r['source_sid'] for r in prelim
                                  if r['source']==source and r['prediction_offset_end']<=786432]
    pools['arm-general'] = [r['source_sid'] for r in retention if r['source']=='general']
    pools['arm-narrative'] = [r['source_sid'] for r in prelim
                             if r['source']=='narrative' and r['prediction_offset_start']>=786432]
    chosen = {}; seen = set()
    for name, ids in pools.items():
        target = 132000 if name.startswith('common-') else 232000
        ordered = sorted(ids, key=lambda sid:digest(['balanced-correction-v2',name,rows[sid]['example_id']]))
        selected = []; positions = 0
        for sid in ordered:
            if sid in seen: raise ValueError('Balanced common/arm families overlap')
            selected.append(rows[sid]); seen.add(sid)
            positions += rows[sid]['original_content_tokens']+1
            if positions>=target: break
        if positions<target: raise ValueError('Insufficient whole-family balanced preliminary supply')
        chosen[name] = selected
    if len({r['split_group'] for rr in chosen.values() for r in rr})!=len(seen):
        raise ValueError('One intact train record per isolated source family required')
    # Explicit finite reallocation; the original retention bytes are never edited.
    moved = {r['sid'] for r in chosen['arm-general']}
    remaining_retention = [rows[r['source_sid']] for r in retention if r['source_sid'] not in moved]
    old_common = read(OLD/'common-nll.json'); old_end = read(OLD/'mlx-nll.json')
    OUT.mkdir(); ROOT.mkdir()
    policy = dict(creator='Navneet Prabhakar', authority='delegated_expert', human_attestation=False,
                  training_approved=True, original_admission_sha256=sha(CORPUS/'admission.json'),
                  scope='Same finite private foundation research, revised preliminary pools only; no new source/category/rights clearance',
                  cause='Original preliminary order is602190general positions then narrative; common reference is general-only. Source-order retention hypothesis, not isolated causal proof.',
                  changes='Balanced50/50common replay of fully exposed families once; balanced resumed arms use previously untouched families. General arm families move out of later retention. Smaller arm exposure fits unchanged cumulative2Mpreliminary cap.',
                  previous_attempt_retained=True, failed_quality=failure, prior_physical_ledger=prior,
                  maximum_family_physical_passes_across_attempts=2,
                  common_pool_prior_passes=1,common_pool_new_maximum_passes=1,
                  arm_pool_prior_passes=0,arm_pool_new_maximum_passes=2,
                  source_text_rewrite=False,selected_source_sids={k:[r['sid'] for r in v] for k,v in chosen.items()},
                  moved_retention_general_families=len(moved),remaining_retention_families=len(remaining_retention),
                  remaining_retention_encoded_positions=sum(r['original_content_tokens']+1 for r in remaining_retention),
                  maximum_new_common_positions=262144,maximum_new_each_arm_positions=458752,
                  maximum_all_preliminary_positions_including_old=1966080,
                  baseline_measured_again=False, baseline_reuse='Identical own foundation/tokenizer/500documents/100prefixes; retain original measurement bytes',
                  inputs={str(p):sha(p) for p in [CORPUS/'manifest.json',CORPUS/'admission.json',CORPUS/'preliminary/lineage.jsonl',CORPUS/'reserved-replay/lineage.jsonl',OLD/'plan.json',OLD/'common-nll.json',OLD/'mlx-nll.json',prior_path,__file__]})
    save(OUT/'policy.json',policy)
    with (OUT/'remaining-retention.jsonl').open('x') as f:
        for r in remaining_retention:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    bpe=BPE.load(TOK); prepared={}
    for name, rr in chosen.items():
        prepared[name]=build_tokens(rr,bpe,OUT/name,sha(CORPUS/'manifest.json'),sha(TOK/'manifest.json'),sha(OUT/'policy.json'))
        if verify_tokens(rr,bpe,OUT/name,TOK)!=prepared[name]['processed_positions']:
            raise ValueError('Balanced full numeric token/source reconstruction differs')
    mixtures={}; stages=[];bindings={}
    for stage,budget,minimum in [('common',262144,260000),('arm',458752,456000)]:
        parts={s:str(OUT/(stage+'-'+s)) for s in ('general','narrative')}
        specs=[dict(id=s,path=path,dataset_hash=sha(Path(path)/'manifest.json'),weight=50,max_passes=1,
                    max_positions=prepared[stage+'-'+s]['processed_positions']) for s,path in parts.items()]
        mix=OUT/(stage+'-mixture')
        mixtures[stage]=build_mixture(specs,TOK,mix,objective='foundation',budget=budget,minimum=minimum,
                                     group_cap=100000,seed='balanced-'+stage+'-v2',allowed_categories=('unreviewed',))
        total=mixtures[stage]['planned_processed_positions']
        schedule=dict(lr=.0003,warmup_tokens=total if stage=='common' else 0,
                      cooldown_tokens=0,final_lr_fraction=1,accumulation_steps=8)
        stages.append(dict(id=stage,path=str(mix),components=parts,dataset_hash=sha(mix/'manifest.json'),schedule=schedule))
        bindings[stage]=dict(path=str(mix),components=parts)
    recipe=Recipe(**old_plan['recipe'])
    curriculum=build_curriculum(stages,TOK,OUT/'curriculum',recipe=recipe,family_processed_cap=100000)
    common=curriculum['stages'][0];arm=curriculum['stages'][1]
    cumulative=786432+common['processed_positions']+2*arm['processed_positions']
    if cumulative>1966080 or cumulative>2000000: raise ValueError('No discarded-work budget reset')
    save(OUT/'manifest.json',dict(creator='Navneet Prabhakar',complete=True,policy_sha256=sha(OUT/'policy.json'),
                                prepared=prepared,mixtures=mixtures,curriculum=curriculum,
                                cumulative_preliminary_physical_positions=cumulative,
                                files={str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}))
    shutil.copytree(OLD/'curriculum',ROOT/'curriculum')
    for name in ('baseline-nll.json','baseline-prose.jsonl'):
        shutil.copyfile(OLD/name,ROOT/name)
    p=dict(old_plan)
    p.update(kind='balanced-english-experiment-v2',prior_physical_ledger=prior,
             preliminary=str(OUT),preliminary_bindings=bindings,
             preliminary_curriculum_sha256=sha(OUT/'curriculum/manifest.json'),
             initial_optimizer='Explicit fresh own-foundation optimizer for a separately frozen corrected common phase. Both resumed arms preserve exact common weights/moments/counters; main transition remains explicitly fresh.',
             paired={**old_plan['paired'], 'common_updates':common['optimizer_updates'],
                     'continuation_updates':arm['optimizer_updates'],
                     'new_common_physical_positions':common['processed_positions'],
                     'new_each_arm_physical_positions':arm['processed_positions'],
                     'total_physical_positions':common['processed_positions']+2*arm['processed_positions'],
                     'cumulative_preliminary_including_discarded':cumulative},
             failed_prior_attempt=dict(root=str(OLD),quality=failure,retention_threshold_unchanged=True),
             baseline_reused_from=str(OLD),cloud_ready=False)
    additional=[OUT/'manifest.json',OUT/'policy.json',OUT/'curriculum/manifest.json',prior_path,
                OLD/'plan.json',OLD/'common-nll.json',OLD/'mlx-nll.json',__file__,
                'src/slm/english_budget_v2.py','src/slm/english_language_v2.py',
                'scripts/run-english-learning-v2.py','scripts/package-english-cloud-v2.py',
                'scripts/english-cloud-worker-v2.sh','reports/english-budget-carry-v2-tests.xml']
    p['inputs']={**old_plan['inputs'],**{str(x):sha(x) for x in additional}}
    p['inputs'].pop(str(OLD/'curriculum/manifest.json'))
    p['inputs'][str(ROOT/'curriculum/manifest.json')]=sha(ROOT/'curriculum/manifest.json')
    p['paired']['common_plus_each_arm_maximum_positions']=common['processed_positions']+arm['processed_positions']
    save(ROOT/'plan.json',p)
    report=dict(creator='Navneet Prabhakar',complete=True,plan_sha256=sha(ROOT/'plan.json'),
                prior_failed_comparison=failure,balanced_policy_sha256=sha(OUT/'policy.json'),
                cumulative_preliminary_physical_positions=cumulative,
                corrected_common=common,corrected_each_arm=arm,remaining_retention_families=len(remaining_retention),
                remaining_retention_encoded_positions=policy['remaining_retention_encoded_positions'],
                no_new_student_gradients_by_preparation=True,cloud_resources_created=0)
    save(OUT/'report.json',report);save('reports/english-balanced-preliminary-v2.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
