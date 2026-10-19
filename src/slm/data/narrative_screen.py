"""Non-mutating narrative signals without invented publisher confidence scores."""
# Creator: Navneet Prabhakar
from collections import Counter
import re
import unicodedata
from slm.data.prose_screen import RULE, windows, word_key
from slm.data.quality_audit import PATTERNS
from slm.data.schema import digest


def screen(text, scores, prior_guard, upstream_guard, heldout_keys, judgment=None):
    if not isinstance(text,str):raise ValueError('Original story text required')
    parts=windows(text)
    if len(parts)!=len(scores):raise ValueError('Complete narrative language coverage required')
    reasons=[];words=re.findall(r'\w+',text.casefold());lines=[s.strip() for s in text.splitlines() if s.strip()]
    if len(words)<RULE['min_words'] or len(text)>RULE['max_characters']:reasons.append('length_scope')
    if '\ufffd' in text or any(unicodedata.category(c)=='Cc' and c not in '\n\t\r' for c in text):reasons.append('encoding_or_controls')
    if not parts or any(not s or s[0]['language']!='en' or not RULE['minimum_window_english_score']<=s[0]['score']<=1.001 for s in scores):reasons.append('window_english_signal')
    if len(lines)>=RULE['repeated_line_minimum_lines'] and (len(lines)-len(set(lines)))/len(lines)>RULE['maximum_duplicate_line_fraction']:reasons.append('duplicate_line_signal')
    if words and max(Counter(words).values())/len(words)>RULE['maximum_single_word_fraction']:reasons.append('single_word_repetition_signal')
    privacy={k:len(p.findall(text)) for k,p in PATTERNS.items() if p.search(text)}
    if privacy:reasons.append('privacy_or_secret_pattern')
    prior=prior_guard.matches(text);upstream=upstream_guard.matches(text);normalized=digest(word_key(text))
    if prior or re.search(r'eval-(?:tools-)?v1/',text,re.I):reasons.append('prior_evaluation_text_or_id')
    if upstream:reasons.append('upstream_evaluation_prefix')
    if normalized in heldout_keys:reasons.append('official_validation_exact')
    if judgment in ('exclude','defer'):reasons.append('prior_direct_'+judgment)
    elif judgment not in (None,'consider'):raise ValueError('Unknown narrative judgment')
    return dict(candidate=not reasons,reasons=reasons,word_count=len(words),language_windows=len(parts),
        normalized_text_sha256=normalized,privacy_pattern_counts=privacy,prior_evaluation_hits=prior,
        upstream_evaluation_hits=upstream,prior_direct_judgment=judgment,source_language_evidence='English source card only; no per-row publisher score available or invented.',
        training_approved=False,privacy_verified=False,factual_accuracy_verified=False,content_category='unreviewed')
