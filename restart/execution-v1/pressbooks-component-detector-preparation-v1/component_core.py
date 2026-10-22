"""Bounded, non-transforming review signals. No rights, humanity or admission verdict."""
import hashlib
import json
import re

VERSION = 'component-review-v1'
MAX_TEXT_BYTES = 2_196_000
MAX_FLAGS = 256
MAX_NOTICE_CHARS = 1024
MAX_RESULT_BYTES = 512_000
CONTEXT_CHARS = 192
_HEX = re.compile(r'[0-9a-f]{64}\Z')
# Explicit separator variants only; no lossy Unicode or entity normalization.
_SEP = r'[\s\-\u2010-\u2015_]*'
_PATTERNS = (
 ('NC_LICENSE_TOKEN', re.compile(r'(?<!\w)CC'+_SEP+r'BY'+_SEP+r'NC(?:'+_SEP+r'(?:SA|ND))?(?!\w)|https?://creativecommons\.org/licenses/by-nc(?:-sa|-nd)?/[0-9.]+/?|\bCreative\s+Commons\b[^\n.]{0,96}\bNon[\s-]?Commercial\b', re.I)),
 ('FDL_LICENSE_TOKEN', re.compile(r'\bGNU\s+Free\s+Documentation\s+Licen[cs]e(?:\s*,?\s*Version\s+[0-9.]+)?|(?<!\w)(?:GFDL|FDL)(?:\s*[vV]?\s*[0-9]+(?:\.[0-9]+)*)?(?!\w)', re.I)),
 ('GENERATION_PHRASE', re.compile(r'\b(?:created|generated|written|authored|produced)\s+(?:entirely\s+|partly\s+)?by\s+(?:Chat\s*GPT|generative\s+AI|artificial\s+intelligence|an?\s+AI(?:\s+model)?)\b|\b(?:I|we)\s+(?:created|generated|wrote|authored|produced)\b[^\n.!?]{0,96}\b(?:using|with)\s+(?:Chat\s*GPT|generative\s+AI)\b', re.I)),
 ('AI_ASSISTANCE_PHRASE', re.compile(r'\b(?:edited|proofread|brainstormed|revised)\b[^\n.!?]{0,64}\b(?:using|with|by)\s+(?:Chat\s*GPT|generative\s+AI)\b', re.I)),
 ('TRANSLATION_PHRASE', re.compile(r'\btranslated\s+(?:into\s+English\s+)?by\b[^\n.!?]{0,96}|\b(?:English\s+)?translation\b[^\n.!?]{0,96}\b(?:made|by)\b[^\n.!?]{0,96}|\b(?:direct|taken)\s+from\b[^\n.!?]{0,128}\btranslation\b', re.I)),
 ('REPUBLICATION_PHRASE', re.compile(r'\b(?:adapted|republished|reprinted|reproduced|excerpted)\s+(?:here\s+)?from\b[^\n.!?]{0,160}', re.I)),
 ('SOURCE_URL_NOTICE', re.compile(r'\bSource\s*:\s*https?://[^\s<>"\u201c\u201d]+', re.I)),
)
_GRANT = re.compile(r'\blicen[cs]ed?\s+(?:under|as)\b|\bterms\s+of\b|\blicen[cs]e\s*[:\-]|\bpermission\s+is\s+granted\b', re.I)
_EXAMPLE = re.compile(r'\b(?:example|hypothetical|sample\s+notice|phrase|e\.g\.)\b', re.I)
_NEGATED = re.compile(r"\b(?:not|never|no\s+longer|wasn[’']t|isn[’']t|weren[’']t)\b[^\n.!?]{0,32}\b(?:created|generated|written|authored|produced|licen[cs]ed)\b", re.I)
_MODAL = re.compile(r"\b(?:could|might|would|should|may|can|will)\s+(?:have\s+been\s+|be\s+)?(?:created|generated|written|authored|produced|licen[cs]ed)\b", re.I)

class DetectionLimitError(ValueError):
    """Caller must retain explicit incomplete-diagnostic status; never silently skip."""


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _local_statement(text, a, b):
    # This is evidence context, NOT the inferred extent of an adapted/generated work.
    lo = max(0, a - CONTEXT_CHARS)
    hi = min(len(text), b + CONTEXT_CHARS)
    left = text.rfind('\n', lo, a)
    if left >= lo:
        lo = left + 1
    right = text.find('\n', b, hi)
    if right >= 0:
        hi = right
    return lo, hi


def _classification(pattern, statement):
    example = bool(_EXAMPLE.search(statement))
    negated = bool(_NEGATED.search(statement))
    conditional = bool(_MODAL.search(statement))
    caveat = ('QUOTED_OR_EXAMPLE' if example else 'NEGATED' if negated else
              'CONDITIONAL_OR_PLANNED' if conditional else 'ASSERTED_LITERAL_NOTICE')
    if pattern in ('NC_LICENSE_TOKEN', 'FDL_LICENSE_TOKEN'):
        return ('COMPONENT_GRANT_NOTICE' if _GRANT.search(statement) else
                'LICENSE_MENTION'), caveat
    if pattern == 'GENERATION_PHRASE':
        return ('EXPLICIT_GENERATION_ATTRIBUTION' if not (example or negated or conditional)
                else 'GENERATION_LANGUAGE_MENTION'), caveat
    if pattern == 'AI_ASSISTANCE_PHRASE':
        return 'AI_ASSISTANCE_DISCLOSURE_NOT_FULL_AUTHORSHIP', caveat
    if pattern == 'TRANSLATION_PHRASE':
        return 'TRANSLATION_ANCESTRY_NOTICE', caveat
    if pattern == 'REPUBLICATION_PHRASE':
        return 'REPUBLICATION_OR_ADAPTATION_ANCESTRY_LEAD', caveat
    return 'EXPLICIT_SOURCE_URL_LEAD', caveat


def detect_components(text, identity):
    """Identity requires source_id, ordinal, text_SHA256 and source_JSON_SHA256.

    Return exact notice and bounded evidence spans only. A notice's component extent,
    retained generated content, rights compatibility and underlying work identity stay
    UNKNOWN until separately established. No body deletion or candidate exclusion.
    """
    if not isinstance(text, str) or not isinstance(identity, dict):
        raise ValueError('text_or_identity_type')
    for k in ('source_id', 'ordinal'):
        if type(identity.get(k)) is not int or identity[k] <= 0:
            raise ValueError('invalid_source_identity')
    for k in ('text_SHA256', 'source_JSON_SHA256'):
        if not isinstance(identity.get(k), str) or not _HEX.fullmatch(identity[k]):
            raise ValueError('invalid_source_hash')
    raw_text = text.encode('utf-8', 'strict')
    if len(raw_text) > MAX_TEXT_BYTES:
        raise DetectionLimitError('text_byte_cap')
    if _sha(raw_text) != identity['text_SHA256']:
        raise ValueError('source_text_hash_mismatch')
    hits = []
    for pattern, regex in _PATTERNS:
        for m in regex.finditer(text):
            if len(hits) >= MAX_FLAGS:
                raise DetectionLimitError('component_flag_cap_no_partial_success')
            a, b = m.span()
            if b - a > MAX_NOTICE_CHARS:
                raise DetectionLimitError('notice_char_cap_no_partial_success')
            ca, cb = _local_statement(text, a, b)
            kind, assertion = _classification(pattern, text[ca:cb])
            hits.append({'pattern': pattern, 'kind': kind, 'assertion_context': assertion,
                         'char_span': [a, b], 'context_char_span': [ca, cb]})
    hits.sort(key=lambda h: (h['char_span'], h['pattern']))
    # Exact UTF8 endpoint mapping in one ascending pass, no full per-character index.
    ends = sorted({p for x in hits for k in ('char_span', 'context_char_span') for p in x[k]})
    byte_pos = {}; prev = n = 0
    for pos in ends:
        n += len(text[prev:pos].encode('utf-8'))
        byte_pos[pos] = n
        prev = pos
    for x in hits:
        a, b = x['char_span']; ca, cb = x['context_char_span']
        x.update({'UTF8_span': [byte_pos[a], byte_pos[b]],
                  'raw': text[a:b], 'raw_SHA256': _sha(text[a:b].encode('utf-8')),
                  'context_UTF8_span': [byte_pos[ca], byte_pos[cb]],
                  'context_raw': text[ca:cb],
                  'context_SHA256': _sha(text[ca:cb].encode('utf-8')),
                  'disposition': 'SCOPED_REVIEW_FLAG_ONLY',
                  'component_extent': 'UNKNOWN_NOT_THE_NOTICE_SPAN',
                  'automatic_candidate_exclusion': False,
                  'confirms_generated_retained_body': False})
        assert raw_text[x['UTF8_span'][0]:x['UTF8_span'][1]].decode() == x['raw']
    result = {'version': VERSION,
              'identity': {k: identity[k] for k in ('source_id', 'ordinal', 'text_SHA256', 'source_JSON_SHA256')},
              'UTF8_bytes': len(raw_text), 'characters': len(text), 'flags': hits,
              'diagnostic_complete_under_frozen_rules': True,
              'unmarked_rights_and_human_authorship': 'UNASSESSED_NOT_CLEARED',
              'automatic_candidate_exclusion': False, 'new_admission': False,
              'source_text_unchanged': True}
    if len(json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode()) > MAX_RESULT_BYTES:
        raise DetectionLimitError('component_result_byte_cap_no_partial_success')
    return result
