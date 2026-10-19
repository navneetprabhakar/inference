"""One-pass whole-dialogue SFT tokens through the separate pinned research reader."""
# Creator: Navneet Prabhakar
import json
import os
from pathlib import Path
import shutil
import tempfile

from slm.common.tokenizer import BPE
from slm.data.schema import digest
from slm.data.sft_research import open_research
from slm.data.oasst_sft_screen import RULE
from slm.data.tokenized import Writer, INDEX, ShardBatches, document_tokens, sha
from slm.train import verify_leaf


def build_tokens(release, tokenizer, output, policy_hash, *, objective='sft', context_length=2048,
                 shard_positions=262144, max_positions=1048576):
    release, tokenizer, output = map(Path, (release, tokenizer, output))
    if output.exists():
        raise FileExistsError(output)
    if objective != 'sft':
        raise ValueError('Bounded SFT research supports only assistant-target SFT')
    if any(type(v) is not int or v < 1 for v in (context_length, shard_positions, max_positions)) or shard_positions < context_length:
        raise ValueError('Explicit positive context/shard/position limits required')
    bpe = BPE.load(tokenizer)
    tokenizer_hash = sha(tokenizer/'manifest.json')
    release_hash = sha(release/'manifest.json')
    implementation_hash = sha(__file__)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.sft-research-tokens-', dir=output.parent))
    writer = None
    try:
        with open_research(release, policy_hash) as reviewed:
            limits = reviewed.research_limits
            measured = json.loads((release/'candidate-report.json').read_text())
            if measured['tokenizer_manifest_sha256'] != tokenizer_hash:
                raise ValueError('Original candidate tokenizer required')
            if context_length > limits['max_context'] or max_positions > limits['physical_data_positions']:
                raise ValueError('Requested preparation exceeds research policy')
            writer = Writer(temp, shard_positions, max_positions)
            records = encoded = 0
            with (temp/'lineage.jsonl').open('w') as lineage:
                for row in reviewed.values():
                    if row['content_category'] != 'sfw' or row['source'] != 'OpenAssistant/oasst2':
                        raise ValueError('Research source/category proxy differs')
                    result, reason = document_tokens(bpe, row, 'sft', context_length)
                    if reason:
                        raise ValueError('Whole-dialogue preparation refuses filtering/truncation: '+reason)
                    tokens, mask = result
                    if sum(mask[1:]) < RULE['minimum_assistant_targets']:
                        raise ValueError('Candidate assistant-target floor differs')
                    records += 1
                    encoded += len(tokens)
                    lineage.write(json.dumps(dict(example_id=row['example_id'], record_sha256=digest(row),
                        content_sha256=digest(row['messages']), source=row['source'], source_revision=row['source_revision'],
                        parent_group_id=row['parent_group_id'], split_group=row['validation_results']['split_group'],
                        split='train', encoded_positions=len(tokens), prediction_positions=len(tokens)-1,
                        supervised_positions=sum(mask[1:])), sort_keys=True)+'\n')
                    writer.add(tokens[:-1], tokens[1:], mask[1:])
            writer.flush()
            writer.close()
            if records != len(reviewed) or records == 0:
                raise ValueError('Complete admitted train stream required')
            report = dict(objective='sft', split='train', message_format='plain-dialogue-v1', token_shard_version=1,
                retained_records=records, retained_groups=records, excluded_records={},
                one_pass_encoded_positions=encoded, processed_prediction_positions=writer.processed,
                supervised_positions=writer.supervised, batches=writer.batches, shards=len(writer.shards),
                explicit_passes=1, implicit_wraparound=False, cross_document_attention=False, truncation=False,
                policy_file_sha256=policy_hash, scope='Bounded SFT research data only; no new model updates or capability acceptance.')
        (temp/'report.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
        manifest = dict(version=1, message_format='plain-dialogue-v1', kind='portable-token-shards-v1', split='train',
            objective='sft', context_length=context_length, vocab_size=bpe.vocab_size, batch_size=1,
            tokenizer_hash=tokenizer_hash, release_manifest_sha256=release_hash,
            research_policy_file_sha256=policy_hash, lineage_schema='record-content-spans-v2',
            supervision_contract_sha256=sha(Path(__file__).parents[1]/'common/supervision.py'),
            structured_serializer_sha256=sha(Path(__file__).parents[1]/'common/tool_serialization.py'),
            builder_sha256=implementation_hash, serializer_sha256=sha(Path(__file__).parents[1]/'common/tokenizer.py'),
            allowed_categories=['sfw'], allowed_sources=['OpenAssistant/oasst2'], batches=writer.batches,
            processed_tokens=writer.processed, supervised_tokens=writer.supervised,
            index_dtype=INDEX.descr, shards=writer.shards,
            files={str(p.relative_to(temp)): sha(p) for p in sorted(temp.rglob('*')) if p.is_file()})
        (temp/'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
        with open_research(release, policy_hash) as reviewed, ShardBatches(temp, tokenizer) as batches:
            verify_leaf(batches, reviewed, bpe)
        if (sha(tokenizer/'manifest.json') != tokenizer_hash or sha(release/'manifest.json') != release_hash
                or sha(__file__) != implementation_hash):
            raise ValueError('Preparation inputs or implementation changed')
        os.rename(temp, output)
        return dict(dataset_hash=sha(output/'manifest.json'), **report)
    except BaseException:
        if writer is not None:
            writer.close()
        shutil.rmtree(temp, ignore_errors=True)
        raise
