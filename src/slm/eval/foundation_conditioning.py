"""Data-only reconstruction of foundation framing and assistant context exposure."""
# Creator: Navneet Prabhakar
import argparse
from collections import Counter
import json
from pathlib import Path
import time
import numpy as np
from slm.common.tokenizer import BPE, STRUCTURAL, OFFSET
from slm.data.schema import digest
from slm.data.tokenized import ShardBatches, sha
from slm.data.review_stream import open_checked
from slm.data.mixture import SCHEDULE
from slm.inference.greedy import prompt_ids


FIELDS = ('assistant_content', 'user_content', 'system_content', 'tool_content',
          'structural', 'assistant_with_full_last_user',
          'assistant_with_full_document_prefix', 'assistant_with_role_visible',
          'assistant_without_prior_user', 'document_start_targets')


def document(bpe, messages, offset, context, counts):
    """Count prediction targets, using actual fixed-window input start positions."""
    tokens = [STRUCTURAL['bos']]
    last_user = None
    prefix_checks = 0

    def add(field, positions, threshold=None):
        positions = np.asarray(positions, dtype=np.int64)
        positions = positions[positions > 0]  # Global first BOS has no prediction.
        batch = (positions - 1) // context
        if threshold is not None:
            batch = batch[batch * context <= threshold]
        if len(batch):
            values = np.bincount(batch, minlength=len(counts))
            if len(values) > len(counts):
                raise ValueError('Document exceeds prepared position count')
            counts[:, FIELDS.index(field)] += values

    add('structural', [offset])
    add('document_start_targets', [offset])
    for i, message in enumerate(messages):
        role = message['role']
        role_position = offset + len(tokens)
        payload = bpe.encode(message['content'])
        if role == 'user':
            last_user = role_position
        if role == 'assistant' and i and messages[i-1]['role'] in ('user', 'tool'):
            if prompt_ids(bpe, messages[:i]) != tokens + [STRUCTURAL['assistant']]:
                raise ValueError('Training/inference conversation prefix differs')
            prefix_checks += 1
        add(role + '_content', np.arange(role_position+1, role_position+1+len(payload)))
        add('structural', [role_position, role_position+1+len(payload)])
        if role == 'assistant':
            positions = np.arange(role_position+1, role_position+1+len(payload))
            add('assistant_with_full_document_prefix', positions, offset)
            add('assistant_with_role_visible', positions, role_position)
            if last_user is None:
                add('assistant_without_prior_user', positions)
            else:
                add('assistant_with_full_last_user', positions, last_user)
        tokens.extend([STRUCTURAL[role], *payload, STRUCTURAL['message_end']])
    add('structural', [offset+len(tokens)])
    tokens.append(STRUCTURAL['eos'])
    x, y, _ = bpe.serialize(messages, objective='all')
    if tokens != x + [y[-1]]:
        raise ValueError('Independent framing reconstruction differs')
    return tokens, prefix_checks


def verify_batches(data, stream, counts):
    cursor = 0
    for i in range(len(data)):
        x, y, mask = data[i]
        n = x.size
        if (x.shape != y.shape or x.shape != mask.shape or x.ndim != 2 or x.shape[0] != 1
                or not np.array_equal(x[0], stream[cursor:cursor+n])
                or not np.array_equal(y[0], stream[cursor+1:cursor+n+1])
                or not np.all(mask == 1)):
            raise ValueError('Actual prepared tokens or masks differ from reconstruction')
        if sum(counts[i, :5]) != n:
            raise ValueError('Role target accounting differs from actual batch')
        cursor += n
    if cursor != len(stream)-1:
        raise ValueError('Prepared batches do not cover reconstructed corpus')


def summarize(counts):
    totals = {k: int(v) for k, v in zip(FIELDS, counts.sum(axis=0))}
    total = sum(totals[k] for k in FIELDS[:5])
    assistant = totals['assistant_content']
    return dict(targets=totals, prediction_positions=total,
                assistant_content_fraction=assistant/total if total else None,
                full_last_user_fraction_of_assistant_content=(
                    totals['assistant_with_full_last_user']/assistant if assistant else None),
                full_document_prefix_fraction_of_assistant_content=(
                    totals['assistant_with_full_document_prefix']/assistant if assistant else None),
                visible_assistant_role_fraction_of_assistant_content=(
                    totals['assistant_with_role_visible']/assistant if assistant else None))


def audit(release, tokenizer, prepared, schedule):
    started = time.monotonic()
    release, tokenizer, prepared, schedule = map(Path, (release, tokenizer, prepared, schedule))
    bpe = BPE.load(tokenizer)
    with ShardBatches(prepared, tokenizer) as data:
        m = data.manifest
        if (m['objective'] != 'foundation' or m['release_manifest_sha256'] != sha(release/'manifest.json')
                or m['message_format'] != 'plain-dialogue-v1'):
            raise ValueError('Exact foundation release/tokenizer binding required')
        counts = np.zeros((len(data), len(FIELDS)), dtype=np.int64)
        chunks = []
        offset = checks = fit = fit_targets = 0
        sources = Counter()
        lineage = iter((prepared/'lineage.jsonl').read_text().splitlines())
        with open_checked(release) as index:
            for row in index.values():
                bound = json.loads(next(lineage))
                if (bound['example_id'] != row['example_id'] or bound['record_sha256'] != digest(row)
                        or bound['content_sha256'] != digest(row['messages'])):
                    raise ValueError('Prepared lineage/order differs from actual source')
                tokens, n = document(bpe, row['messages'], offset, m['context_length'], counts)
                if len(tokens) != bound['encoded_positions']:
                    raise ValueError('Prepared document length differs')
                _, _, assistant_mask = bpe.serialize(row['messages'], objective='assistant')
                if len(tokens)-1 <= m['context_length']:
                    fit += 1
                    fit_targets += sum(assistant_mask)
                chunks.append(np.asarray(tokens, dtype=np.uint32))
                offset += len(tokens)
                checks += n
                sources[row['source']] += 1
            if next(lineage, None) is not None:
                raise ValueError('Extra prepared lineage')
        stream = np.concatenate(chunks)
        verify_batches(data, stream, counts)
        sm = json.loads((schedule/'manifest.json').read_text())
        if (sm['components'] != [dict(id='foundation', dataset_hash=data.fingerprint,
                                      max_passes=2, max_positions=sm['budget'], weight=1)]
                or sm['objective'] != 'foundation' or sm['tokenizer_hash'] != data.tokenizer_hash):
            raise ValueError('Expected frozen single-leaf foundation schedule')
        for name, checksum in sm['files'].items():
            if sha(schedule/name) != checksum:
                raise ValueError('Schedule checksum differs')
        rows = np.fromfile(schedule/'schedule.bin', dtype=SCHEDULE)
        if len(rows) != sm['batches'] or np.any(rows['component'] != 0):
            raise ValueError('Schedule coverage/component differs')
        scheduled = np.zeros((len(rows), len(FIELDS)), dtype=np.int64)
        for i, row in enumerate(rows):
            batch = int(row['batch'])
            if (not 0 <= batch < len(data) or int(row['length']) != data[batch][0].size
                    or int(row['supervised']) != int(row['length'])):
                raise ValueError('Scheduled batch accounting differs')
            scheduled[i] = counts[batch]
        if summarize(scheduled)['prediction_positions'] != sm['processed_tokens']:
            raise ValueError('Schedule position totals differ')
        return dict(creator='Navneet Prabhakar', version=1, implementation_sha256=sha(__file__),
                    release_manifest_sha256=sha(release/'manifest.json'),
                    tokenizer_manifest_sha256=sha(tokenizer/'manifest.json'),
                    prepared_manifest_sha256=data.fingerprint, schedule_manifest_sha256=sha(schedule/'manifest.json'),
                    records=sum(sources.values()), sources=dict(sources),
                    actual_inference_prefixes_equal=checks, actual_prepared_batches_equal=len(data),
                    one_prepared_pass=summarize(counts), selected_training_chain=summarize(scheduled),
                    whole_dialogues_fitting_training_context=fit,
                    potential_assistant_mask_targets_in_fitting_dialogues=fit_targets,
                    elapsed_seconds=time.monotonic()-started, new_model_updates=0,
                    scope='Data-only diagnostic, no SFT admission or causal proof. Full-last-user availability means its role and complete message are in this fixed input window; full-document-prefix availability is stricter. Assistant-content counts exclude structural ends; potential SFT mask counts include assistant ends/EOS. Schedule counts cover the selected chain, excluding the discarded screen. Cross-document attention remains present. No new student generation, teacher or cloud action.')


def main():
    p = argparse.ArgumentParser()
    for name in ('release', 'tokenizer', 'prepared', 'schedule', 'output'):
        p.add_argument('--'+name, required=True)
    a = p.parse_args()
    out = Path(a.output)
    if out.exists():
        raise FileExistsError(out)
    result = audit(a.release, a.tokenizer, a.prepared, a.schedule)
    with out.open('x') as f:
        f.write(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
