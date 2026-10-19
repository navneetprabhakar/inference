"""Non-mutating prose candidate screening, never source or training approval."""
# Creator: Navneet Prabhakar
from collections import Counter
import re
import unicodedata

from slm.data.quality_audit import PATTERNS
from slm.data.schema import digest

RULE = dict(version=1, min_words=50, max_characters=200000,
            minimum_source_english_score=0.8, minimum_window_english_score=0.8,
            window_characters=1024, minimum_window_letters=40,
            repeated_line_minimum_lines=8, maximum_duplicate_line_fraction=0.3,
            maximum_single_word_fraction=0.15)


def word_key(text):
    return ' '.join(re.findall(r'\w+', unicodedata.normalize('NFKC', text).casefold()))


class RequestGuard:
    """Whole request word sequences, including when embedded in prose.

    Case, Unicode compatibility, punctuation and whitespace variations are
    normalized. Arbitrary paraphrases or unseen family variants are not detected.
    """
    def __init__(self, requests):
        keys = {word_key(text) for text in requests}
        if not keys or any(len(k) < 16 or len(k.split()) < 4 for k in keys):
            raise ValueError('Complete nontrivial protected request text required')
        self.requests = tuple(sorted(keys))
        self.fingerprint = digest(self.requests)

    def matches(self, text):
        body = ' ' + word_key(text) + ' '
        return [digest(k) for k in self.requests if ' ' + k + ' ' in body]


def windows(text):
    """All fixed windows with enough letters; no prefix-only language check."""
    result = []
    for start in range(0, len(text), RULE['window_characters']):
        part = text[start:start + RULE['window_characters']]
        if sum(c.isalpha() for c in part) >= RULE['minimum_window_letters']:
            result.append(dict(start=start, end=start + len(part), text=part))
    return result


def screen(row, language_predictions, guard, known_judgment=None, frozen_partition=None):
    text = row['text']
    if not isinstance(text, str): raise ValueError('Raw text required')
    parts = windows(text)
    if len(parts) != len(language_predictions):
        raise ValueError('Complete language-window coverage required')
    reasons = []
    words = re.findall(r'\w+', text.casefold())
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not RULE['min_words'] <= len(words) or len(text) > RULE['max_characters']:
        reasons.append('length_scope')
    if '\ufffd' in text or any(unicodedata.category(c) == 'Cc' and c not in '\n\t\r' for c in text):
        reasons.append('encoding_or_controls')
    if row.get('language') != 'en' or not isinstance(row.get('language_score'), (int, float)) or not RULE['minimum_source_english_score'] <= row['language_score'] <= 1.001:
        reasons.append('source_english_signal')
    if not parts or any(not scores or scores[0]['language'] != 'en' or not RULE['minimum_window_english_score'] <= scores[0]['score'] <= 1.001 for scores in language_predictions):
        reasons.append('window_english_signal')
    if len(lines) >= RULE['repeated_line_minimum_lines'] and (len(lines) - len(set(lines))) / len(lines) > RULE['maximum_duplicate_line_fraction']:
        reasons.append('duplicate_line_signal')
    if words and max(Counter(words).values()) / len(words) > RULE['maximum_single_word_fraction']:
        reasons.append('single_word_repetition_signal')
    privacy = {name: len(pattern.findall(text)) for name, pattern in PATTERNS.items() if pattern.search(text)}
    if privacy: reasons.append('privacy_or_secret_pattern')
    protected = guard.matches(text)
    if protected or re.search(r'eval-(?:tools-)?v1/', text, re.I):
        reasons.append('protected_evaluation_request_or_id')
    if known_judgment in ('exclude', 'defer'):
        reasons.append('prior_direct_' + known_judgment)
    elif known_judgment not in (None, 'consider'):
        raise ValueError('Unknown direct judgment')
    if frozen_partition not in (None, 'validation', 'test'):
        raise ValueError('Only ancestral heldout partitions accepted')
    if frozen_partition: reasons.append('ancestral_heldout')
    return dict(candidate=not reasons, reasons=reasons, word_count=len(words),
                language_windows=len(parts), privacy_pattern_counts=privacy,
                protected_request_hashes=protected, original_frozen_partition=frozen_partition,
                prior_direct_judgment=known_judgment, raw_record_sha256=digest(row),
                training_approved=False, factual_accuracy_verified=False,
                privacy_verified=False, content_category='unreviewed')
