"""Wikipedia pilot prose eligibility; preserves exact source substrings and end matter."""
import hashlib
import re
from urllib.parse import urlsplit
from slm.restart.edu_filter import normalized

VERSION = 'wikipedia-pilot-prose-v1'
END_HEADINGS = frozenset({'references', 'external links', 'see also', 'further reading',
    'bibliography', 'selected bibliography', 'key publications', 'publications',
    'selected publications', 'gallery', 'notes', 'sources'})

def transform(row):
    original = row.get('text')
    if not isinstance(original, str) or not original.strip():
        return None, ['empty'], [], ''
    reasons = []
    title = row.get('title', '')
    url = urlsplit(row.get('url', ''))
    if url.hostname != 'en.wikipedia.org' or not url.path.startswith('/wiki/'):
        reasons.append('unexpected_page_url')
    if not str(row.get('id', '')).isdigit():
        reasons.append('missing_page_identity')
    if re.match(r'(?i)^(list of|lists of|outline of|index of|timeline of)\b', title):
        reasons.append('list_page')
    if '(disambiguation)' in title.lower() or re.search(r'(?i)\bmay (?:also )?refer to\s*:', original[:600]):
        reasons.append('disambiguation')
    # Only exact standalone headings define a boundary. Do not delete arbitrary
    # matched words from prose, fill missing sentences, or discard licensing metadata.
    offset = 0
    cut = len(original)
    heading = None
    for line in original.splitlines(keepends=True):
        if line.strip().casefold() in END_HEADINGS:
            cut = offset
            heading = line.strip()
            break
        offset += len(line)
    text = original[:cut].rstrip()
    # Include whitespace before the heading so concatenation exactly reconstructs input.
    removed = original[len(text):]
    edits = []
    if removed:
        edits.append({'operation': 'retain_prefix_before_exact_end_heading' if heading else 'trim_trailing_whitespace',
                      'heading': heading, 'kept_characters': len(text),
                      'removed_sha256': hashlib.sha256(removed.encode()).hexdigest(),
                      'removed_characters': len(removed)})
    words = normalized(text).split()
    if not 150 <= len(words) <= 1800:
        reasons.append('word_length_outside_150_1800')
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if len(lines) < 2:
        reasons.append('insufficient_paragraph_structure')
    if '\ufffd' in text or any(ord(c)<32 and c not in '\n\r\t' for c in text):
        reasons.append('encoding_or_control')
    if re.search(r'<[^>]+>|\{\{|\}\}|\[\[|\]\]|\\(?:frac|begin|end)\b', text):
        reasons.append('markup_or_formula_residue')
    if re.search(r'(?i)\[citation needed\]|\[edit\]|\bISBN\b|\bdoi\s*:', text):
        reasons.append('editorial_or_bibliography_residue')
    if text and text[-1] not in '.!?\"\u201d\u2019)':
        reasons.append('unfinished_or_category_ending')
    prose = sum(len(x.split()) for x in lines if len(x.split())>=8 and x[-1] in '.!?\"\u201d\u2019)')
    if prose/max(1,len(text.split())) < .85:
        reasons.append('low_sentence_prose_fraction')
    if len(words)>4:
        grams=[tuple(words[i:i+5]) for i in range(len(words)-4)]
        if 1-len(set(grams))/len(grams)>.12:
            reasons.append('repetitive_fivegrams')
    return text, sorted(set(reasons)), edits, removed
