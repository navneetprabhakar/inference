"""Finite foundation tokens with exact per-document source and position lineage."""
# Creator: Navneet Prabhakar
import json
import os
from pathlib import Path
import shutil
import tempfile

from slm.common.tokenizer import BPE
from slm.data.prose_research import open_research, require
from slm.data.schema import digest
from slm.data.tokenized import INDEX, ShardBatches, Writer, document_tokens, sha
from slm.train import verify_leaf


def verify_tokens(tokens, release, tokenizer, policy_hash):
    tokens, release, tokenizer = map(Path, (tokens, release, tokenizer))
    with open_research(release, policy_hash) as approved, ShardBatches(tokens, tokenizer) as batches:
        manifest = batches.manifest
        require(manifest['builder_sha256'] == sha(__file__)
                and manifest['research_policy_file_sha256'] == policy_hash
                and manifest['release_manifest_sha256'] == sha(release / 'manifest.json')
                and manifest['objective'] == 'foundation', 'Pinned prose-token origin differs')
        verify_leaf(batches, approved, BPE.load(tokenizer))
        count = offset = 0
        with (tokens / 'lineage.jsonl').open() as handle:
            for line in handle:
                record = json.loads(line); row = approved[record['example_id']]
                require(record['upstream_document'] == approved.prose_metadata[row['parent_group_id']]
                        and record['raw_record_sha256'] == row['validation_results']['prose_research_admission']['raw_record_sha256']
                        and record['prediction_offset_start'] == offset
                        and record['prediction_offset_end'] == offset + record['prediction_positions'], 'Prose metadata or target-position lineage differs')
                offset += record['prediction_positions']; count += 1
        require(count == len(approved) and offset == batches.manifest['processed_tokens'], 'Complete one-pass prose lineage required')
        return dict(records=count, prediction_positions=offset, batches=len(batches))


def build_tokens(release, tokenizer, output, policy_hash, *, context_length=1024,
                 shard_positions=262144, max_positions=2000000):
    release, tokenizer, output = map(Path, (release, tokenizer, output))
    if output.exists(): raise FileExistsError(output)
    require(all(type(v) is int and v > 0 for v in (context_length, shard_positions, max_positions))
            and shard_positions >= context_length, 'Positive bounded preparation settings required')
    bpe = BPE.load(tokenizer); tokenizer_hash = sha(tokenizer / 'manifest.json')
    release_hash = sha(release / 'manifest.json'); implementation_hash = sha(__file__)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.prose-research-tokens-', dir=output.parent)); writer = None
    try:
        with open_research(release, policy_hash) as approved:
            limits = approved.research_limits
            require(context_length <= limits['max_context'] and max_positions <= limits['physical_data_positions'], 'Preparation exceeds research policy')
            writer = Writer(temp, shard_positions, max_positions)
            encoded = count = prediction_offset = 0; buffer = []
            with (temp / 'lineage.jsonl').open('w') as lineage:
                for row in approved.values():
                    result, reason = document_tokens(bpe, row, 'foundation', context_length)
                    require(reason is None, 'Complete prose document required')
                    tokens, _ = result
                    contribution = len(tokens) - int(count == 0)
                    entry = dict(example_id=row['example_id'], record_sha256=digest(row),
                        content_sha256=digest(row['messages']), source=row['source'], source_revision=row['source_revision'],
                        parent_group_id=row['parent_group_id'], split_group=row['validation_results']['split_group'],
                        split='train', encoded_positions=len(tokens), prediction_positions=contribution,
                        supervised_positions=contribution, prediction_offset_start=prediction_offset,
                        prediction_offset_end=prediction_offset + contribution,
                        upstream_document=approved.prose_metadata[row['parent_group_id']],
                        raw_record_sha256=row['validation_results']['prose_research_admission']['raw_record_sha256'])
                    lineage.write(json.dumps(entry, sort_keys=True) + '\n')
                    prediction_offset += contribution; encoded += len(tokens); count += 1
                    buffer.extend(tokens); start = 0
                    while len(buffer) - start > context_length:
                        chunk = buffer[start:start + context_length + 1]
                        writer.add(chunk[:-1], chunk[1:], [1] * context_length); start += context_length
                    buffer = buffer[start:]
            if len(buffer) > 1: writer.add(buffer[:-1], buffer[1:], [1] * (len(buffer) - 1))
            writer.flush(); writer.close()
            require(count == len(approved) and count > 0 and prediction_offset == writer.processed == writer.supervised,
                    'Exact complete foundation accounting required')
        report = dict(objective='foundation', split='train', retained_records=count, retained_groups=count,
                      one_pass_encoded_positions=encoded, processed_prediction_positions=writer.processed,
                      supervised_positions=writer.supervised, batches=writer.batches, shards=len(writer.shards),
                      explicit_passes=1, implicit_wraparound=False, truncation=False, cross_document_attention=True,
                      policy_file_sha256=policy_hash,
                      scope='All train prose followed by EOS, packed into causal foundation contexts. Source documents and target offsets retained; no assistant-role supervision, gradient or experiment-launch acceptance.')
        (temp / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
        manifest = dict(version=1, message_format='plain-dialogue-v1', kind='portable-token-shards-v1',
                        objective='foundation', split='train', context_length=context_length,
                        vocab_size=bpe.vocab_size, batch_size=1, tokenizer_hash=tokenizer_hash,
                        release_manifest_sha256=release_hash, research_policy_file_sha256=policy_hash,
                        lineage_schema='record-content-spans-v2', builder_sha256=implementation_hash,
                        supervision_contract_sha256=sha(Path(__file__).parents[1] / 'common/supervision.py'),
                        structured_serializer_sha256=sha(Path(__file__).parents[1] / 'common/tool_serialization.py'),
                        serializer_sha256=sha(Path(__file__).parents[1] / 'common/tokenizer.py'),
                        allowed_categories=['unreviewed'], allowed_sources=['HuggingFaceFW/fineweb-edu'],
                        batches=writer.batches, processed_tokens=writer.processed, supervised_tokens=writer.supervised,
                        index_dtype=INDEX.descr, shards=writer.shards,
                        files={str(p.relative_to(temp)): sha(p) for p in sorted(temp.rglob('*')) if p.is_file()})
        (temp / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        verify_tokens(temp, release, tokenizer, policy_hash)
        require(sha(release / 'manifest.json') == release_hash and sha(tokenizer / 'manifest.json') == tokenizer_hash
                and sha(__file__) == implementation_hash, 'Preparation origin changed')
        os.rename(temp, output)
        return dict(dataset_hash=sha(output / 'manifest.json'), **report)
    except BaseException:
        if writer is not None: writer.close()
        shutil.rmtree(temp, ignore_errors=True)
        raise
