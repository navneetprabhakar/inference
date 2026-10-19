"""Reconcile source/genre supply without promoting screened text to admission."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
from slm.data.schema import digest
from slm.data.tokenized import sha

root=Path('data/cosmopedia-candidate-intake-v1')
cosmo=json.loads((root/'report.json').read_text());counts=Counter();tokens=Counter()
for item in cosmo['files']:
    path=root/'cache'/(digest(item['rows_cache_key'])+'.bin')
    assert sha(path)==item['rows_sha256']
    for line in path.read_bytes().splitlines():
        row=json.loads(line)
        if row['provisional_quality_pass']:
            genre=row['row']['format'];counts[genre]+=1;tokens[genre]+=row['actual_student_bpe_text_tokens']
assert sum(counts.values())==cosmo['provisional_quality_pass']
assert sum(tokens.values())==cosmo['provisional_pass_text_tokens']
fine=json.loads(Path('reports/fineweb-candidate-intake-check.json').read_text())
narrative=json.loads(Path('reports/tinystories-quality-check.json').read_text())
assert fine['passed'] is True and narrative['passed'] is True
paths=['scripts/measure-provisional-corpus-supply.py','reports/fineweb-candidate-intake-check.json','data/cosmopedia-candidate-intake-v1/report.json','reports/tinystories-quality-check.json']
explanatory=sum(tokens[k] for k in ('textbook','textbook_unconditionned_topic'))
result=dict(creator='Navneet Prabhakar',kind='actual-provisional-source-genre-supply-v1',
    input_bindings={p:sha(p) for p in paths},cosmopedia_formats={k:dict(rows=counts[k],tokens=tokens[k]) for k in sorted(counts)},
    source_screened_token_occurrences=dict(general=fine['provisional_pass_text_tokens'],explanatory_textbook_formats=explanatory,narrative=narrative['provisional_pass_tokens']),
    three_source_provisional_token_occurrences=fine['provisional_pass_text_tokens']+sum(tokens.values())+narrative['provisional_pass_tokens'],
    proposed_genre_limited_token_occurrences=fine['provisional_pass_text_tokens']+explanatory+narrative['provisional_pass_tokens'],
    training_approved=False,model_updates=0,teacher_calls=0,cloud_spend=0,
    scope='Actual source metadata and retained BPE totals. Two textbook format names are a proposed explanatory subset, not genre-quality verification/admission. Dialogue/story/wikihow tokens are not silently counted as explanatory. Counts precede cross-source exact/near/seed/ancestral grouping, new heldouts and finite exposure schedule; no claimed unique train tokens or completed60/20/20 mixture.')
Path('reports/provisional-corpus-supply.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result,indent=2))
