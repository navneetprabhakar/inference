"""Bounded boolean equivalent of Shield.reasons for text-only user messages.

No corpus or protected-file reads. Callers provide already constructed shields.
Limits raise rather than treating an unscanned document as clear. The caller must
still bound total wall time/RSS externally; these are per-document work bounds.
"""
from collections import Counter, defaultdict
from itertools import chain

from protect_split import STOPS, shape, words


class OverlapLimitError(RuntimeError):
    pass


class TextOverlapIndex:
    def __init__(self, shields, *, max_text_chars=100_000, max_posting_visits=5_000_000):
        if type(max_text_chars) is not int or max_text_chars <= 0:
            raise ValueError('max_text_chars must be positive')
        if type(max_posting_visits) is not int or max_posting_visits <= 0:
            raise ValueError('max_posting_visits must be positive')
        self.max_text_chars=max_text_chars
        self.max_posting_visits=max_posting_visits
        self.exact=set();self.shapes=set();self.grams=set()
        distinct=set()
        for shield in shields:
            self.exact.update(shield.exact)
            self.shapes.update(shield.shapes)
            self.grams.update(shield.grams)
            # Fewer than four anchors can never meet either overlap condition.
            distinct.update(frozenset(a) for a in shield.anchor_sets if len(a)>=4)
        # Stable ordering makes diagnostics/reproduction independent of hash seed.
        self.anchor_sizes=[]
        self.postings=defaultdict(list)
        for terms in sorted(distinct,key=lambda a:tuple(sorted(a))):
            index=len(self.anchor_sizes);self.anchor_sizes.append(len(terms))
            for term in terms:self.postings[term].append(index)
        self.postings=dict(self.postings)

    def matches(self, text):
        if not isinstance(text,str):raise ValueError('text must be a string')
        if len(text)>self.max_text_chars:
            raise OverlapLimitError('candidate exceeds maximum text characters')
        # One tokenization supplies exact, shingle and lexical-anchor checks.
        # Prompt shape deliberately retains the original separate normalization.
        tokens=words(text)
        if tuple(tokens) in self.exact:return True
        if self.grams:
            for start in range(len(tokens)-7):
                if tuple(tokens[start:start+8]) in self.grams:return True
        if len(tokens)>=5 and self.shapes and shape(text) in self.shapes:return True
        anchors=frozenset(t for t in tokens if t not in STOPS and not t.isdigit())
        if len(anchors)<4 or not self.anchor_sizes:return False
        lists=[self.postings[t] for t in anchors if t in self.postings]
        visits=sum(map(len,lists))
        if visits>self.max_posting_visits:
            raise OverlapLimitError('candidate exceeds maximum anchor posting visits')
        intersections=Counter(chain.from_iterable(lists))
        na=len(anchors)
        for index,common in intersections.items():
            if common<4:continue
            nb=self.anchor_sizes[index]
            # Identical conditions/order of arithmetic to Shield.reasons.
            if (common/(na+nb-common)>=.65
                    or common/min(na,nb)>=.9 and common>=5):
                return True
        return False

    def matches_history(self, history):
        history=tuple(history)
        # Validate the complete input before an early positive can hide a call
        # or unsupported role in a later message.
        for message in history:
            if (not isinstance(message,dict) or message.get('role')!='user'
                    or not isinstance(message.get('text'),str) or 'call' in message):
                raise ValueError('only text-only user histories are supported')
        return any(self.matches(message['text']) for message in history)

    def statistics(self):
        return dict(exact_strings=len(self.exact),prompt_shapes=len(self.shapes),
                    eight_word_windows=len(self.grams),anchor_sets=len(self.anchor_sizes),
                    anchor_terms=len(self.postings),posting_entries=sum(map(len,self.postings.values())),
                    max_text_chars=self.max_text_chars,max_posting_visits=self.max_posting_visits)
