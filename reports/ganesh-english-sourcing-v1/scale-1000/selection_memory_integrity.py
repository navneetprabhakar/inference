"""Read-only, fail-closed binding of memory credit to reviewed exact content.

Every selected row requires memory_evidence_receipt={path,sha256}, explicit
memory_probe_credit, and recall_probe (canonical object or null). The receipt
contains entries with group, messages_sha256, credit, recall_probe,
original_generated_annotation, reason, and source_receipts. Never infer credit
from a family label, a non-null annotation, or a nonmemory review's N/A flag.
"""
import hashlib
import json
from pathlib import Path


class MemoryIntegrityError(ValueError):
    pass


def _require(ok, reason):
    if not ok:
        raise MemoryIntegrityError(reason)


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _load(ref, root):
    _require(isinstance(ref, dict) and isinstance(ref.get('path'), str), 'Missing receipt path')
    expected = ref.get('sha256')
    _require(isinstance(expected, str) and len(expected) == 64, 'Missing receipt SHA-256')
    path = (root / ref['path']).resolve()
    _require(path.is_relative_to(root), 'Receipt outside workspace root')
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise MemoryIntegrityError('Missing receipt: ' + ref['path']) from exc
    _require(hashlib.sha256(data).hexdigest() == expected, 'Stale receipt hash: ' + ref['path'])
    try:
        return json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise MemoryIntegrityError('Receipt is not JSON: ' + ref['path']) from exc


def _canonical(value):
    if value is None:
        return None
    _require(isinstance(value, dict) and set(value) == {'support_turn', 'probe_turn', 'focus'},
             'Probe must have exactly support_turn, probe_turn, focus')
    _require(type(value['support_turn']) is int and type(value['probe_turn']) is int,
             'Probe indices must be integers, not booleans')
    _require(isinstance(value['focus'], str) and value['focus'].strip(), 'Probe focus is empty')
    return dict(value)


def _probe_from(record):
    """Normalize known annotation schemas; return None if no explicit focus binding."""
    if not isinstance(record, dict):
        return None
    for key in ('recall_probe', 'recall'):
        if isinstance(record.get(key), dict):
            return _probe_from(record[key])
    support = next((record[k] for k in ('support_turn', 'last_support_turn',
                   'last_supporting_turn', 'latest_support_turn', 'actual_last_supporting_turn') if k in record), None)
    probe = record.get('probe_turn')
    focus = next((record[k] for k in ('focus', 'narrow_focus', 'focused_fact', 'probe_focus') if k in record), None)
    if type(support) is not int or type(probe) is not int or not isinstance(focus, str) or not focus.strip():
        return None
    return {'support_turn': support, 'probe_turn': probe, 'focus': focus}


def _records(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    found = []
    for key in ('reviews', 'entries', 'annotation_decisions'):
        if isinstance(data.get(key), list):
            found.extend(data[key])
    return found or [data]


def _valid_memory(record):
    if record.get('decision') in ('fail', 'reject', 'exclude', 'revise'):
        return False
    if record.get('dialogue_selected') is False:
        return False
    if isinstance(record.get('recall'), dict):
        return record['recall'].get('valid') is True
    # `credit` alone deliberately does not authorize itself as source evidence.
    return any(record.get(k) is True for k in ('valid', 'annotation_valid', 'memory_annotation_valid'))


def _supports(data, group, message_hash, probe, explicit):
    for record in _records(data):
        if not isinstance(record, dict) or record.get('group') != group:
            continue
        bound = record.get('messages_sha256', record.get('content_sha256', record.get('messages_hash')))
        if bound != message_hash or not _valid_memory(record):
            continue
        supplied = _probe_from(record)
        if supplied is not None and supplied == probe:
            return True
        # Unchanged generated probes may use their cold review's memory-valid
        # verdict. Corrected/new probes need the explicit complete tuple.
        if not explicit and supplied is None and record.get('memory_annotation_valid') is True:
            return True
    return False


def _legacy_original(row, root, message_hash):
    selection = _load(row['fresh_selection_receipt'], root)
    _require(isinstance(selection, dict), 'Legacy selection receipt must be an object')
    matches = [e for e in selection.get('entries', []) if e.get('group') == row['group']]
    _require(len(matches) == 1 and matches[0].get('decision') == 'accept' and
             matches[0].get('messages_sha256') == message_hash, 'Legacy selection does not accept exact content')
    snapshot = selection.get('source_snapshot')
    expected = selection.get('source_payload_sha256')
    _require(isinstance(snapshot, str) and isinstance(expected, str), 'Missing bound legacy source snapshot')
    path = (root / snapshot).resolve()
    _require(path.is_relative_to(root), 'Legacy snapshot outside workspace root')
    try:
        payload = path.read_bytes()
        _require(hashlib.sha256(payload).hexdigest() == expected, 'Stale legacy source snapshot')
        baseline = [json.loads(line) for line in payload.splitlines() if line.strip()]
    except (OSError, ValueError, UnicodeError) as exc:
        raise MemoryIntegrityError('Unreadable legacy source snapshot') from exc
    old = [r for r in baseline if r.get('group') == row['group']]
    _require(len(old) == 1 and old[0].get('messages') == row['messages'], 'Legacy source content mismatch')
    annotations = [a for a in selection.get('annotation_decisions', []) if a.get('group') == row['group']]
    _require(len(annotations) <= 1, 'Duplicate legacy annotation decisions')
    if annotations:
        annotation = annotations[0]
        _require(annotation.get('messages_sha256') == message_hash, 'Legacy annotation content mismatch')
        _require('original_annotation' in annotation, 'Missing legacy original annotation')
        return annotation['original_annotation'], annotation
    return old[0].get('recall_probe'), None


def _generated_original(row, root):
    generation = row.get('generation')
    _require(isinstance(generation, dict), 'Missing generation provenance for new row')
    data = _load({'path': generation.get('raw_artifact'), 'sha256': generation.get('raw_sha256')}, root)
    candidates = [c for c in data.get('conversations', []) if c.get('group') == row['group']]
    _require(len(candidates) == 1, 'Raw generation group missing or duplicated')
    candidate = candidates[0]
    try:
        generated_messages = [{'role': role, 'content': turn[role]}
                              for turn in candidate['turns'] for role in ('user', 'assistant')]
    except (KeyError, TypeError) as exc:
        raise MemoryIntegrityError('Malformed generated dialogue') from exc
    _require(generated_messages == row['messages'], 'Raw generation content mismatch')
    _require('recall_probe' in candidate, 'Raw generation lacks explicit annotation')
    return candidate['recall_probe']


def verify_memory(row, root):
    """Validate a selected row and return its bound evidence entry; no writes."""
    root = Path(root).resolve()
    _require(isinstance(row.get('group'), str) and isinstance(row.get('messages'), list), 'Invalid row identity')
    message_hash = _digest(row['messages'])
    evidence = _load(row.get('memory_evidence_receipt'), root)
    _require(isinstance(evidence, dict) and isinstance(evidence.get('entries'), list), 'Invalid memory evidence packet')
    entries = [e for e in evidence['entries'] if isinstance(e, dict) and e.get('group') == row['group']]
    _require(len(entries) == 1, 'Memory evidence entry missing or duplicated')
    entry = entries[0]
    required = {'group', 'messages_sha256', 'credit', 'recall_probe',
                'original_generated_annotation', 'reason', 'source_receipts'}
    _require(required <= set(entry), 'Memory evidence entry missing required fields')
    _require(entry['messages_sha256'] == message_hash, 'Memory evidence content mismatch')
    _require(type(entry['credit']) is bool and type(row.get('memory_probe_credit')) is bool,
             'Explicit boolean memory credit required')
    _require(row['memory_probe_credit'] == entry['credit'], 'Memory credit differs from receipt')
    _require('recall_probe' in row, 'Explicit selected probe or null required')
    probe = _canonical(entry['recall_probe'])
    _require(_canonical(row['recall_probe']) == probe, 'Selected probe differs from receipt')
    _require(isinstance(entry['reason'], str) and entry['reason'].strip(), 'Memory decision reason required')
    _require(isinstance(entry['source_receipts'], list), 'Memory source receipts must be a list')
    sources = [_load(ref, root) for ref in entry['source_receipts']]
    legacy_annotation = None
    if 'fresh_selection_receipt' in row:
        original, legacy_annotation = _legacy_original(row, root, message_hash)
    else:
        original = _generated_original(row, root)
    _require(entry['original_generated_annotation'] == original, 'Original annotation differs from bound source')
    if not entry['credit']:
        _require(probe is None, 'Uncredited probe must be null')
        return entry
    _require(probe is not None, 'Credited probe is missing')
    n = sum(m.get('role') == 'assistant' for m in row['messages'])
    _require(1 <= probe['support_turn'] < probe['probe_turn'] <= n, 'Probe indices outside dialogue')
    _require(probe['probe_turn'] - probe['support_turn'] - 1 >= 2, 'Insufficient complete intervening pairs')
    if 'fresh_selection_receipt' in row:
        _require(legacy_annotation is not None and legacy_annotation.get('valid') is True and
                 legacy_annotation.get('dialogue_selected') is True, 'Legacy selection gives no valid memory credit')
        _require(_probe_from(legacy_annotation) == probe, 'Legacy probe differs from pinned annotation decision')
    corrected = _probe_from(original) != probe
    _require(sources, 'Memory credit requires hash-bound review evidence')
    _require(any(_supports(data, row['group'], message_hash, probe, corrected) for data in sources),
             'Corrected probe lacks explicit valid annotation evidence' if corrected else
             'Probe lacks matching valid memory review evidence')
    return entry
