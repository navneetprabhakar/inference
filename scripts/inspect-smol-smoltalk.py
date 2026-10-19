#!/usr/bin/env python3
"""Register a pinned source and inspect only a bounded 200-row train prefix."""
# Creator: Navneet Prabhakar
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from slm.data.acquire import register, sample
from slm.data.tokenized import sha
from slm.common.tokenizer import BPE


ROOT = Path('data/smol-smoltalk-audit-v1')
REVISION = 'f73fe857d519ff6ac5af2ea67c4d3834da7b8bcc'


def main():
    if ROOT.exists(): raise FileExistsError(ROOT)
    source = register('HuggingFaceTB/smol-smoltalk', 'apache-2.0', ROOT/'source',
                      revision=REVISION, upstream_origins=('https://huggingface.co/datasets/HuggingFaceTB/smoltalk',))
    acquired = sample(source, 'default', 'train', ROOT/'sample', count=200)
    rows = [json.loads(v) for v in (ROOT/'sample/rows.jsonl').read_text().splitlines()]
    if len(rows) != 200: raise ValueError('Complete bounded 200-row prefix required')
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    labels = Counter(); shapes = Counter(); lengths = Counter(); issues = Counter()
    processed = supervised = 0
    for row in rows:
        labels[str(row.get('source'))] += 1
        messages = row.get('messages')
        if (not isinstance(messages, list) or not messages
                or any(not isinstance(m, dict) or set(m) != {'role', 'content'}
                       or not isinstance(m['content'], str) for m in messages)):
            issues['unsupported_message_shape'] += 1; continue
        shapes['/'.join(m['role'] for m in messages)] += 1
        if messages[-1]['role'] != 'assistant': issues['not_assistant_ended'] += 1; continue
        try: x, _, mask = bpe.serialize(messages)
        except ValueError:
            issues['unsupported_serializer'] += 1; continue
        processed += len(x); supervised += sum(mask)
        for limit in (512, 1024, 2048):
            if len(x) <= limit: lengths[str(limit)] += 1
    result = dict(creator='Navneet Prabhakar', version=1, source=asdict(source), acquisition=acquired,
        source_descriptor_sha256=sha(ROOT/'source/source.json'), script_sha256=sha(__file__),
        tokenizer_manifest_sha256=sha('data/iteration-two-foundation-tokenizers-v1/vocab-16384/manifest.json'),
        prefix_source_labels=dict(labels), message_role_shapes=dict(shapes), complete_dialogues_fitting_context=dict(lengths),
        serialized_prediction_positions=processed, hypothetical_assistant_targets=supervised, issues=dict(issues),
        training_eligible=False, full_content_reviews=0, new_model_updates=0, new_teacher_calls=0, new_cloud_jobs=0,
        scope='Pinned source/schema/sizing probe only, first 200 train rows, not a representative quality estimate or source/corpus approval. Published Apache-2.0 card does not independently settle every constituent synthetic-generation term. Preserve test split, constituent provenance and source review before any bulk intake/admission. No pretrained weights, teacher generation, model training or paid launch.')
    (ROOT/'inspection.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    Path('reports/milestone-fifty-six-smol-source-inspection.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
