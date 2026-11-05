"""Closed-set supervised typed pattern classifier; numeric slots never come from weights."""
from collections import defaultdict
import re
from fallback_head import parse
from followon_head_v2 import normalized_words

# Ground an anaphor to exactly one record. Reject earlier/multiple references.
REFERENCE = re.compile(r'\b(?:(?:the|this|that|my|our|your)\s+)?(?:(?:just\s+)?(?:previous|last|prior|latest|returned|current|recorded|observed|final)\s+)?(?:result|output|answer|value|total|number)\b|\b(?:that|it)\b',re.I)
FILLER = {'please','now','then','next','just','again','also','andthen'}
UNSUPPORTED = re.compile(r'[^a-z0-9.,?!+\-\s]|\d,|\d[eE][+-]?\d|[!?].+\w',re.I)


def encode(user):
    text=user.casefold().strip()
    if len(text)>240 or UNSUPPORTED.search(text):
        return None, None
    refs=list(REFERENCE.finditer(text))
    if len(refs)!=1:
        return None,None
    ref=refs[0]
    text=text[:ref.start()]+' priorreference '+text[ref.end():]
    words,spans=parse(normalized_words(text), None)
    numbers=[s.value for s in spans if s.kind=='number']
    if len(numbers)!=1 or any(s.kind=='unit' for s in spans):
        return None,None
    return tuple(w for w in words if w not in FILLER),numbers[0]


def fit(rows):
    patterns=defaultdict(set)
    for row in rows:
        key,_=encode(row['user'])
        if key is not None:
            patterns[' '.join(key)].add(row['label'])
    return {key:next(iter(labels)) for key,labels in patterns.items() if len(labels)==1}


def predict(state,user):
    key,value=encode(user)
    return (state.get(' '.join(key)),value) if key else (None,None)
