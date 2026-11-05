"""Low-risk short human writing requests; preserve original responses and verify easy count constraints."""
import re
from compact import EXCLUDE
NUM={'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'twelve':12}
def eligible(r):
    if r['category']!='Generation' or len(r['history'])!=2:return False
    q,a=[m['text'] for m in r['history']]
    if not re.search(r'\bpoem\b',q,re.I) or EXCLUDE.search(q+' '+a):return False
    if len(q.split())>40 or len(a.split())>90 or len(a.splitlines())<2:return False
    if re.search(r'\b(?:haiku|syllabl\w*|limerick|acrostic|sonnet|rhym\w*|couplet|stanza\w*|verse|rap|ballad|lyrics|scheme|religio\w*|style|death|passed away|disorder|deceas\w*|depress\w*|named|name is|inspired by|about me|war|shakespeare|prince|king|queen|for my|from my|as if|birthday|suicide|relationship|anxiety|race|politic\w*|drugs?|slavery|newspaper|I lost|died|grief|bereav\w*|poetic devices|alliteration|simile|metaphor|\d+ (?:words|syllables))\b',q,re.I):return False
    if re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b',q):return False
    constraint=re.search(r'\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve)[- ]lines?\b',q,re.I)
    if constraint:
        x=constraint[1].lower();n=int(x) if x.isdigit() else NUM[x]
        if sum(bool(s.strip()) for s in a.splitlines())!=n:return False
    return True
