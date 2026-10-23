"""CPU-only audit of existing artifacts; no model construction or inference.

Reads our saved checkpoint tensors and tokenizer, never imports a trainer,
creates new model weights, calls a teacher, or changes frozen experiment files.
"""
import collections
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent
BASE = ROOT.parents[1]
STAGE = BASE / 'restart/foundation-stage3-v1'
PREVIOUS = BASE / 'restart/foundation-stage2-v1'
UPSTREAM = BASE / 'restart/mac15m-feasibility-v1/upstream'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def passes(row):
    return (sum(row['scores']) >= 8 and min(row['scores']) > 0
            and not row['contradiction'] and not row['incoherent_sentence'])


def kappa(a, b):
    assert len(a) == len(b) and a
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return dict(agreement=observed, kappa=(observed - expected) / (1 - expected),
                a_positive=sum(a), b_positive=sum(b),
                intersection=sum(x and y for x, y in zip(a, b)))


def main():
    assert not read(STAGE / 'contract.json')['current_stage_training_authorized']
    sys.path.insert(0, str(UPSTREAM))
    from tokenizer import Tokenizer
    tokenizer = Tokenizer(str(UPSTREAM / 'tokenizer.model'))
    packet = read(STAGE / 'packet.json')
    tokenization = {}
    for kind in ['grammar', 'grounded']:
        counts = collections.Counter()
        example = None
        for case in packet[kind]:
            prefix = tokenizer.encode(case['prefix'], bos=True, eos=False)
            joint_lengths = []
            for option in case['options']:
                separate = prefix + tokenizer.encode(option, bos=False, eos=False)
                joint = tokenizer.encode(case['prefix'] + option, bos=True, eos=False)
                counts['candidates'] += 1
                counts['separate_vs_joint_mismatch'] += separate != joint
                counts['joint_prefix_unchanged'] += joint[:len(prefix)] == prefix
                counts['exactly_one_extra_token'] += len(separate) == len(joint) + 1
                counts['double_space_in_actual_decoding'] += '  ' in tokenizer.decode(separate)
                joint_lengths.append(len(joint) - len(prefix))
                if example is None:
                    example = dict(id=case['id'], prefix=case['prefix'], option=option,
                                   actual_decoded=tokenizer.decode(separate),
                                   intended_decoded=tokenizer.decode(joint),
                                   actual_suffix_ids=separate[len(prefix):],
                                   intended_suffix_ids=joint[len(prefix):])
            counts['joint_equal_length_case'] += len(set(joint_lengths)) == 1
        assert counts['candidates'] == (200 if kind == 'grammar' else 400)
        assert all(counts[k] == counts['candidates'] for k in [
            'separate_vs_joint_mismatch', 'joint_prefix_unchanged',
            'exactly_one_extra_token', 'double_space_in_actual_decoding'])
        assert counts['joint_equal_length_case'] == 100
        tokenization[kind] = dict(counts=counts, example=example)

    groups = collections.defaultdict(dict)
    mapping = read(STAGE / 'teacher-blind-map.json')
    for row in read(STAGE / 'teacher-review.json')['reviews']:
        entry = mapping[row['id']]
        groups[entry['stage']][entry['id']] = row
    dimensions = ['grammar', 'topic', 'entity_reference', 'causal_temporal', 'local_coherence']
    teacher = {}
    for stage, rows_by_id in groups.items():
        rows = list(rows_by_id.values())
        teacher[stage] = dict(
            dimension_means={d:sum(v['scores'][i] for v in rows)/len(rows)
                             for i,d in enumerate(dimensions)},
            mean_total=sum(sum(v['scores']) for v in rows)/len(rows),
            incoherent_sentences=sum(v['incoherent_sentence'] for v in rows),
            contradictions=sum(v['contradiction'] for v in rows),
            binary_pass=sum(passes(v) for v in rows))
    primary = {v['id']:v for v in read(STAGE / 'primary-review.json')['reviews']}
    ids = sorted(primary)
    agreement = kappa([primary[i]['coherent'] for i in ids],
                      [passes(groups['current'][i]) for i in ids])

    ground = {}
    grammar = {}
    for name, path in [('prior', PREVIOUS/'stage2-evaluation/option-scores.json'),
                       ('current', STAGE/'stage3-evaluation/option-scores.json')]:
        rows = read(path)
        subgroups = collections.defaultdict(list)
        for row in rows:
            if row['kind'] == 'grounded':
                subgroups[row['family']].append(row)
        ground[name] = {}
        for family, items in subgroups.items():
            predictions = [max(range(4),key=lambda i:v['scores'][i]) for v in items]
            ground[name][family] = dict(cases=len(items),correct=sum(v['correct'] for v in items),
                                        predicted_answer_counts=dict(collections.Counter(predictions)))
        grammar_rows=[v for v in rows if v['kind']=='grammar']
        unique={(v['prefix'],tuple(sorted(v['options']))):v for v in grammar_rows}
        grammar[name]=dict(rendered_cases=len(grammar_rows),rendered_correct=sum(v['correct'] for v in grammar_rows),
                           unique_pairs=len(unique),unique_correct=sum(v['correct'] for v in unique.values()))

    updates=[json.loads(v) for v in (STAGE/'updates.jsonl').read_text().splitlines()]
    checkpoint_path=STAGE/'stage3-checkpoint.pt'
    checkpoint=torch.load(checkpoint_path,map_location='cpu',weights_only=False)
    embedding=checkpoint['model']['tok_embeddings.weight'].numel()
    body=sum(v.numel() for k,v in checkpoint['model'].items()
             if k not in ['tok_embeddings.weight','output.weight'])
    assert embedding+body==15191712
    assert all(int(v['step'])==2889 for v in checkpoint['optimizer']['state'].values())
    pins=read(STAGE/'source-pins.json')
    assert all(sha(STAGE/name)==digest for name,digest in pins.items())
    assert sha(checkpoint_path)==read(STAGE/'stage3-checkpoint.json')['sha256']
    out=dict(
        status='READ_ONLY_CPU_AUDIT_COMPLETE_TRAINING_PAUSED',epoch=time.time(),
        training_updates=0,model_forward_passes=0,new_weights_initialized=False,
        teacher_requests=0,frozen_sources_modified=False,checkpoint_unchanged=True,
        tokenization=tokenization,
        tokenization_interpretation='All candidate strings contain an extra whitespace token. Its direct logprob term is common to options, but it changes their conditioning. Corrected inference is needed to quantify accuracy effects; no corrected scores are claimed.',
        teacher=teacher,primary_vs_teacher=agreement,grammar=grammar,
        grounded_historical_malformed_input_scores=ground,
        schedule=dict(total_updates=2889,configured_updates=100000,
                      configured_schedule_fraction=2889/100000,
                      total_targets=378667008,configured_targets=13107200000,
                      native_corpus_positions=1004262627,
                      approximate_corpus_passes=378667008/1004262627,
                      warmup_updates=1000,warmup_targets=131072000,
                      warmup_fraction_of_completed_updates=1000/2889,
                      final_lr=updates[-1]['lr'],peak_lr=.0005,
                      final_lr_fraction_of_peak=updates[-1]['lr']/.0005,
                      configured_horizon_is_not_a_proven_minimum=True),
        learning=dict(first100_stage3_mean_loss=sum(v['loss'] for v in updates[:100])/100,
                      last100_stage3_mean_loss=sum(v['loss'] for v in updates[-100:])/100,
                      all_stage3_losses_and_norms_finite=all(math.isfinite(v['loss']) and math.isfinite(v['gradient_norm']) for v in updates),
                      stage3_updates_with_gradient_norm_above1=sum(v['gradient_norm']>1 for v in updates)),
        architecture=dict(total_parameters=embedding+body,embedding_parameters=embedding,
                          transformer_and_norm_parameters=body,embedding_fraction=embedding/(embedding+body),
                          layers=6,width=288,vocabulary=32000,context=256,
                          same_size_published_reference_exists=True,capacity_failure_not_proven=True),
        throughput=dict(final30_targets_per_second=10498.897562400542,
                        billion_target_training_hours=1e9/10498.897562400542/3600,
                        remaining_configured_training_days=(13107200000-378667008)/10498.897562400542/86400,
                        overhead_included=False,projection_not_a_run_proposal=True),
        independent_checkpoint_parity='NOT_VERIFIED_VERIFIER_CLOCK_KEY_FAILURE',
        limitations=['No causal optimization or data ablation executed.',
                     'No corrected model scoring or new generation executed.',
                     'Native validation leakage remains unresolved.',
                     'TinyStories does not establish broad conversation or tool capability.'],
        source_sha256={str(p.relative_to(BASE)):sha(p) for p in [
            STAGE/'worker.py',STAGE/'engine.py',STAGE/'engine_support.py',
            STAGE/'packet.json',STAGE/'teacher-review.json',STAGE/'primary-review.json',checkpoint_path]})
    (ROOT/'audit.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out,indent=2))


if __name__=='__main__':
    main()
