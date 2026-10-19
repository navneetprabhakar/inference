"""Exact FineWeb excerpt spans in Cosmopedia prompts; no inferred document ID."""
# Creator: Navneet Prabhakar
import re
from slm.data.schema import digest

HEADER = re.compile(r'\AHere is an extract from a webpage:\s*"')
BOUNDARY = re.compile(r'"\.?\r?\n\r?\n(?=(?:Write|Create|Think)\b)')


def extract(row):
    """Ambiguity fails. Character offsets reproduce the original excerpt.

    Same quoted excerpt under different instructions gets the same family. A
    different excerpt of the same document remains unresolved, never guessed.
    """
    if row.get('seed_data') != 'fineweb':
        raise ValueError('FineWeb prompt profile only; other constituent seeds unresolved')
    prompt = row.get('prompt')
    if not isinstance(prompt, str) or not 1 <= len(prompt) <= 40000:
        raise ValueError('Bounded original generation prompt required')
    header = HEADER.match(prompt)
    if header is None: raise ValueError('Unknown web-extract prompt header')
    ends = list(BOUNDARY.finditer(prompt, header.end()))
    if len(ends) != 1: raise ValueError('Unique seed/instruction boundary required')
    end = ends[0]; seed = prompt[header.end():end.start()]
    if len(seed) < 80 or len(re.findall(r'\w+', seed)) < 8:
        raise ValueError('Nontrivial complete published seed excerpt required')
    return dict(seed_excerpt=seed, seed_start=header.end(), seed_end=end.start(),
                instruction_start=end.end(), prompt_sha256=digest(prompt), seed_excerpt_sha256=digest(seed),
                proposed_exact_seed_family='HuggingFaceTB/smollm-corpus:cosmopedia-v2:seed:' + digest(seed),
                underlying_document_id_verified=False,
                scope='Exact quoted excerpt only; no document URL/identity, semantic-family or cross-source contamination guarantee.')
