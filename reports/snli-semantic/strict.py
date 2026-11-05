"""Optional conservative semantic subcohorts. Filters select published labels; never relabel a pair."""
import re
from build import norm
STOP=set('a an the is are was were some in on at of for with to by their his her they she he has have be being and there this that it as from one who while man men woman women person people guy lady child children boy girl young old two three group wearing wear doing does do thing things someone another outside outdoors outdoor inside indoors indoor'.split())
ALIASES={'riding':'ride','rides':'ride','rode':'ride','biking':'bicycle','bike':'bicycle','biker':'cyclist','bicycling':'bicycle','standing':'stand','stands':'stand','sitting':'sit','sits':'sit','seated':'sit','walking':'walk','walks':'walk','running':'run','runs':'run','playing':'play','plays':'play','lifting':'lift','holds':'hold','holding':'hold','jumping':'jump','jumps':'jump','skating':'skate','dogs':'dog','shirts':'shirt','jersey':'shirt','hats':'hat','kids':'children','child':'children','boy':'children','girl':'children','male':'man','female':'woman','outside':'outdoors','outdoor':'outdoors','inside':'indoors','indoor':'indoors'}
def units(s):
    return {ALIASES.get(w,w) for w in norm(s).split() if w not in STOP}
def narrow(r):
    p,h=r['premise'],r['hypothesis'];P,H=units(p),units(h);c=r['label']
    if c=='entailment':
        # Remove clauses/modifiers or use independently spelled aliases. Keep a substantive event/object.
        return bool(H) and not H-P and not re.search(r"\b(not|no|never|most|all|every|only|always|first|last|likes?|enjoys?|loves?|because|future|tomorrow)\b",h,re.I)
    if c=='contradiction':
        # Explicit incompatible status/location only when the human has assigned contradiction;
        # require shared concrete action/object plus natural subjects.
        if len(P&H)<1:return False
        neg=re.search(r"\b(?:not|never|no|nobody|no one|isn't|aren't|without)\b",h,re.I)
        if neg:return not re.search(r"\b(?:no|not|never|without|no one)\b",p,re.I)
        pp=set(norm(p).split());hh=set(norm(h).split())
        states=[({'sleeping','asleep'},{'running','jogging','walking','racing','jumping','playing','dancing'}),
                ({'standing','stands'},{'sitting','seated'}),({'inside','indoors'},{'outside','outdoors'}),
                ({'empty'},{'crowded','packed'})]
        return any((pp&l and hh&rr) or (pp&rr and hh&l) for l,rr in states)
    # Scope neutral examples to an explicit, unmentioned property anchoring a common event/object.
    properties=set('red blue green yellow orange purple pink silver striped plaid checkered leather woolen wool wooden plastic steel cotton round square triangular large small big tiny striped long short new old expensive inexpensive nearby wooden polyester silk denim woolen leather matching identical different favorite favourite birthday concert competition practice tournament lesson vacation Saturday Sunday Friday Monday Tuesday Wednesday Thursday morning afternoon evening'.casefold().split())
    return bool(P&H and ((H-P)&properties))
