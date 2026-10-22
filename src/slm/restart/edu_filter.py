"""Frozen Edu pilot prose-cohort v1. Eligibility is not semantic admission."""
import re,hashlib,unicodedata
from urllib.parse import urlsplit

VERSION='edu-pilot-prose-v1'
TAILS={'take a look:','have your say:','speak to a journalist on:','share this article:','share this post:'}
def normalized(text):return ' '.join(re.findall(r'\w+',unicodedata.normalize('NFKC',text).casefold()))
def transform(row):
    original=row.get('text');reasons=[];edits=[]
    if not isinstance(original,str) or not original.strip():return None,['empty'],edits
    if row.get('language')!='en' or row.get('language_score',0)<.9:reasons.append('language_metadata')
    if row.get('score',0)<4.0:reasons.append('educational_score_below_4')
    path=urlsplit(row.get('url','')).path.lower()
    if re.search(r'/(?:profiles?|authors?|tags?|categories|search)(?:/|$)',path):reasons.append('index_or_profile_url')
    if original.lower().count('part of the book:')>=2:reasons.append('concatenated_book_blurbs')
    lines=original.splitlines();cut=None
    for i,line in enumerate(lines):
        if line.strip().lower() in TAILS and i>=len(lines)*.75:
            cut=i;break
    text=original
    if cut is not None:
        text='\n'.join(lines[:cut]).rstrip();edits.append({'operation':'remove_exact_trailing_media_contact_block','first_line':cut,'removed_lines':len(lines)-cut})
    if '\ufffd' in text or any(ord(c)<32 and c not in '\n\r\t' for c in text):reasons.append('encoding_or_control')
    if re.search(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|-----BEGIN .*PRIVATE KEY|\bAKIA[A-Z0-9]{16}\b',text):reasons.append('contact_or_secret_signal')
    if len(re.findall(r'<[^>]{1,100}>',text))>=3:reasons.append('markup')
    if re.search(r'(?i)cookie policy|subscribe to our newsletter|add to cart|book (?:an|your) appointment|all rights reserved',text):reasons.append('promotional_or_navigation_residue')
    words=normalized(text).split()
    if not 150<=len(words)<=1800:reasons.append('word_length_outside_150_1800')
    nonempty=[x.strip() for x in text.splitlines() if x.strip()]
    if len(nonempty)<2:reasons.append('single_block')
    if nonempty and len(nonempty[-1].split())<6:reasons.append('dangling_last_line')
    if text.rstrip() and text.rstrip()[-1] not in '.!?\"\u201d\u2019)':reasons.append('unfinished_ending')
    prose_words=sum(len(x.split()) for x in nonempty if len(x.split())>=8 and x[-1] in '.!?\"\u201d\u2019)')
    if prose_words/max(1,len(text.split()))<.75:reasons.append('low_sentence_prose_fraction')
    if len(words)>4:
        shingles=[tuple(words[i:i+5]) for i in range(len(words)-4)]
        if 1-len(set(shingles))/len(shingles)>.12:reasons.append('repetitive_fivegrams')
    if len(nonempty)>=4 and len(set(nonempty))/len(nonempty)<.9:reasons.append('repeated_lines')
    return text,sorted(set(reasons)),edits
