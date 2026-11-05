"""Final source-safety checks and transparent, task-specific relation admission strata."""
import re
from strict import narrow,units
UNSAFE=re.compile(r'\b(?:tribal|in drag|children are in a cage|kids are in a cage|shirtless|deceased|Amish|Mormon|Hindu|Jewish|Mennonite|Arab|terrorist|insuranc\w*|gang of|in a gang|God|nuns?|monks?|mental illness|skin\s+colou?r|ethnic\w*|anorex\w*|suicid\w*|slum\w*|spank\w*|orphan\w*|sacrific\w*|bruise\w*|assault\w*|forced to|gangster|afro|nipple\w*|topless|buttocks|brawl\w*|humping|missing (?:a |one |both )?(?:arm|leg|limb)s?|no (?:arms|legs|limbs)|(?:wooden|prosthetic|amputated|artificial) (?:arm|leg|limb)|smack\w*|punch\w*|slap\w*|kicking (?:a|another|the) (?:man|woman|child|kid|boy|girl)|burying a younger person|cathedral|chapel|missionary|blood\w*|smuggl\w*|obscene|wheel ?chair|skinny|scantily clad|dark.complected|light.complected|race of people|gay pride|worship\w*)\b',re.I)
COLOR_PERSON=re.compile(r'\b(?:black|white|brown)\s+(?!(?:and|or|with|in|on|stripe\w*|check\w*|shirt\w*|t-?shirt\w*|sleeve\w*|shorts?|jeans|denim|cow|cat\w*|dog\w*|pupp\w*|bird\w*|horse\w*|spots?|jacket\w*|coat\w*|pant\w*|skirt\w*|collar\w*|trouser\w*|uniform\w*|suit\w*|vest\w*|shoe\w*|sneaker\w*|dress\w*|garment\w*|sweater\w*|tie\w*|glove\w*|helm\w*|hat\w*|cap\w*|sock\w*|outfit\w*|cloth\w*|fabric|bag\w*|purse\w*|sunglass\w*|backpack\w*|belt\w*|tank|top\w*|car\w*|truck\w*|bike\w*|bicycl\w*|background|board\w*|paper\w*|table\w*|wall\w*|fence\w*|ball\w*|field|floor\w*|sneaker\w*|hair\w*|poodle|lab\w*|shepherd|umbrella|paint\w*|water|square|sofa|wood\w*)\b)\w+',re.I)
PERSON_NAME=re.compile(r'(?<!^)(?<!\. )\b[A-Z][a-z]+ [A-Z][a-z]+\b')
def safe(r):
    s=r['premise']+' '+r['hypothesis']
    return not (UNSAFE.search(s) or COLOR_PERSON.search(s) or PERSON_NAME.search(s))
def final_stratum(r):
    if not safe(r) or re.search(r'\.[A-Za-z]',r['premise']+' '+r['hypothesis']):return None
    tier=r['annotation_tier'];c=r['label']
    if tier=='multi-unanimous' and c in ('entailment','neutral'):return tier+'/'+c
    if not narrow(r):return None
    if c=='contradiction':
        p,h=r['premise'].casefold(),r['hypothesis'].casefold()
        for lhs,rhs in ((r'\b(man|men|boy|boys|male)\b',r'\b(woman|women|girl|girls|female)\b'),(r'\b(woman|women|girl|girls|female)\b',r'\b(man|men|boy|boys|male)\b')):
            if re.search(lhs,p) and not re.search(rhs,p) and re.search(rhs,h) and not re.search(lhs,h):return None
    if c=='contradiction' and tier=='single-recorded':
        h=r['hypothesis'].casefold()
        if not re.search(r"\b(?:not|no|never|nobody|none|no one|isn't|aren't|without)\b",h):return None
        neg={'not','no','never','nobody','none','without',"isn't","aren't",'any','anything','anyone','anybody','single'}
        P,H=units(r['premise']),units(r['hypothesis'])-neg
        if not H or H-P:return None
    if c=='neutral' and tier=='single-recorded':
        props=set('red green yellow blue purple orange pink silver striped plaid checkered leather woolen wooden plastic cotton metal denim silk'.split())
        P,H=units(r['premise']),units(r['hypothesis'])
        if len(P&H)<2 or not H-P or not (H-P)<=props:return None
    return tier+'/'+c
