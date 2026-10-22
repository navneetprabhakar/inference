"""One bounded derivative of seven reviewed whitespace seams; no ML operations."""
import hashlib
import importlib.util
import json
import shutil
import time
from pathlib import Path

from tokenizers import Tokenizer

B = Path(__file__).resolve().parent
P = B / 'm2-intake/gutenberg-seven-join-preparation-v1'
O = B / 'm2-intake/gutenberg-novel-prose-seven-joins-v2'
START = time.monotonic()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def guard():
    require(time.monotonic() - START < 25, '25 second work limit')
    require(shutil.disk_usage(B).free > 54_000_000_000, 'disk reserves')
    if O.exists():
        require(sum(p.stat().st_size for p in O.rglob('*') if p.is_file()) < 8_000_000,
                '8MB output cap')


guard()
recipe_bytes = (P / 'recipe.json').read_bytes()
require(sha(recipe_bytes) == '219d01f90d477fc5485c5b2cf63a8289ffcf3de6b0a01016c6e60c51a19a19a3', 'reviewed recipe')
recipe = json.loads(recipe_bytes)
helper_path = P / 'apply_recipe.py'
require(sha(helper_path.read_bytes()) == '04a1778cb161d3eaa880788856bef63ec0fce798f8b84392b45fa89920a8e681', 'helper pin')
require(sha((B / 'gutenberg-seven-join-audit-v1/review.json').read_bytes()) == '11a5c3fd8ab7f6c25f2d12df702cdb3266939f2427e27d940e6b4360e0748fc3', 'independent audit')
for path, digest in recipe['immutable_input_pins'].items():
    require(sha(Path(path).read_bytes()) == digest, 'source pin: ' + path)
core = B / 'tokenizer-8192/core.json'
require(sha(core.read_bytes()) == '5892586252d16641b38483659dacc1c19a048fb59b3ba381831e4b68515645d9', 'tokenizer core')
require(sha((core.parent / 'manifest.json').read_bytes()) == '577c0f59ffc594931650de802c4630f3171ebde139cc32c742f5f264e7f98812', 'tokenizer manifest')
tokenizer = Tokenizer.from_file(str(core))
spec = importlib.util.spec_from_file_location('exact_join_helper', helper_path)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
patches = {p['chapter_number']: p for p in recipe['patches']}
require(len(patches) == 7, 'exact seven chapters')
source = B / 'gutenberg-novel-prose-v1'
rows = [json.loads(line) for line in (source / 'chapters.jsonl').read_text().splitlines()]
require([r['chapter_number'] for r in rows] == list(range(1, 62)), '61 complete chapters')
O.mkdir(exist_ok=False)
(O / 'chapters').mkdir()
result = []
total_old = total_new = tokens = 0
for row in rows:
    guard()
    number = row['chapter_number']
    data = (source / row['file']).read_bytes()
    require(sha(data) == row['sha256'] and data.decode('utf8') == row['text'], 'old chapter binding')
    patch = patches.get(number)
    new = helper.apply(data, [patch], row['sha256']) if patch else data
    if patch:
        require(sha(new) == patch['prospective_corrected_chapter_sha256'], 'exact expected result')
        a = patch['derivative_start_byte']
        restored = new[:a] + patch['exact_old_whitespace'].encode('ascii') + new[a + 1:]
        require(restored == data, 'exact inverse reconstruction')
    require(b''.join(new.split()) == b''.join(data.split()), 'all nonwhitespace bytes conserved')
    path = O / row['file']
    path.write_bytes(new)
    n_tokens = len(tokenizer.encode(new.decode('utf8'), add_special_tokens=False).ids)
    require(path.read_bytes() == new, 'stored bytes')
    result.append({'chapter_number': number, 'file': row['file'], 'bytes': len(new), 'sha256': sha(new),
                   'content_tokens_existing_M1_BPE': n_tokens, 'source_derivative_file': str(source / row['file']),
                   'source_derivative_sha256': row['sha256'], 'formatting_patch_ID': patch['id'] if patch else None,
                   'family_id': row['family_id'], 'split': None, 'training_admitted': False,
                   'holds': ['semantic_quality_review_pending', 'strict_language_gate_pending_for_changed_text',
                             'original_chapter45_language_failure_preserved', 'cross_new_source_leakage_and_family_gate_pending',
                             'fresh_acceptance_pending', 'M1_tokenizer_counts_provisional_not_M3']})
    total_old += len(data)
    total_new += len(new)
    tokens += n_tokens
require(total_old - total_new == 59 and len(result) == 61, 'exact scope and reduction')
for path, digest in recipe['immutable_input_pins'].items():
    require(sha(Path(path).read_bytes()) == digest, 'original source unchanged')
(O / 'chapters.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in result))
(O / 'formatting-recipe.json').write_bytes(recipe_bytes)
receipt = {'status': 'COMPLETE_SEVEN_REVIEWED_WHITESPACE_JOINS_NO_ADMISSION', 'chapters': 61,
           'changed_chapters': sorted(patches), 'original_bytes': total_old, 'derivative_bytes': total_new,
           'reduction_bytes': 59, 'provisional_M1_content_tokens': tokens, 'exact_inverse_reconstruction': True,
           'all_nonwhitespace_bytes_conserved': True, 'all_original_sources_unchanged': True,
           'all156_prior_removed_spans_retained_in_pinned_original_registry': True,
           'previous_legacy_overlap_result_not_reissued_for_changed_text': True,
           'prior_rights_resolution': str(B / 'm2-intake/gutenberg-original-body-rights-resolution-v1/review.json'),
           'new_admitted_documents': 0, 'new_admitted_tokens': 0, 'network_requests': 0,
           'models_initialized': 0, 'training_updates': 0, 'detector_runs': 0,
           'elapsed_seconds': time.monotonic() - START, 'execution_code_SHA256': sha(Path(__file__).read_bytes())}
(O / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
guard()
manifest = {str(p.relative_to(O)): sha(p.read_bytes()) for p in sorted(O.rglob('*')) if p.is_file()}
(O / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(receipt))
