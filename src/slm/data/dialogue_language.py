"""Conversation-aware language evidence; never certify English or admit training."""
# Creator: Navneet Prabhakar
import re
from slm.data.schema import digest

RULE=dict(version=2,kind='dialogue-language-evidence-v2',minimum_alphabetic_characters=80,
          minimum_non_english_top_score=.8,
          short_or_uncertain='review_attention_not_automatic_rejection',
          code='review_attention_not_language_judgment',
          premise='Caller separately requires publisher-declared English on every included node.',
          limitations='A lack of strong non-English evidence does not verify English, coherence, privacy or correctness. Thresholds are exploratory, not probability calibration or a population error bound.')
CODE=re.compile(r'(?m)^\s*(?:from \w.* import |import \w|def \w+\(|class \w|[\[\]{}])')


def assess(messages,windows):
    coverage=[0]*len(messages);observations=[]
    for w in windows:
        i,start,end=w.get('message'),w.get('start'),w.get('end')
        if (type(i) is not int or not 0<=i<len(messages) or type(start) is not int or type(end) is not int
            or start!=coverage[i] or not start<end<=len(messages[i]['content']) or end-start>2048):
            raise ValueError('Language evidence window coverage differs')
        coverage[i]=end;text=messages[i]['content'][start:end];top=w.get('top_scores')
        if top:
            if any(type(p.get('score')) not in (int,float) or not 0<=p['score']<=1.001 for p in top):raise ValueError('Invalid language evidence score')
            if any(not isinstance(p.get('language'),str) or not p['language'] for p in top):raise ValueError('Invalid language label')
            if len(top)>2 or (len(top)==2 and (top[0]['language']==top[1]['language'] or top[0]['score']<top[1]['score'])):
                raise ValueError('Unordered language evidence')
        if '```' in messages[i]['content'] or CODE.search(messages[i]['content']):status='code_review_attention'
        elif w.get('status')!='scored' or not top or len(top)!=2:status='missing_or_unscored_review_attention'
        elif sum(c.isalpha() for c in text)<RULE['minimum_alphabetic_characters']:status='short_review_attention'
        elif top[0]['language']!='en' and top[0]['score']>=RULE['minimum_non_english_top_score']:status='strong_non_english_attention'
        elif top[0]['language']!='en' or top[0]['score']<.8:status='uncertain_review_attention'
        else:status='no_strong_non_english_evidence'
        observations.append(dict(message=i,start=start,end=end,status=status))
    if coverage!=[len(m['content']) for m in messages]:raise ValueError('Incomplete language evidence coverage')
    strong=any(o['status']=='strong_non_english_attention' for o in observations)
    attention=any(o['status']!='no_strong_non_english_evidence' for o in observations)
    return dict(status='strong_non_english_attention' if strong else 'review_attention' if attention else 'no_strong_non_english_evidence',
                hard_attention=strong,windows=observations,rule_sha256=digest(RULE),english_certified=False)


def checked_policy(policy):
    from slm.data.dialogue_screen import checked,FIELDS
    expected=FIELDS|{'language_rule_sha256'}
    if set(policy)!=expected or policy.get('version')!=2 or type(policy['version']) is not int or policy.get('kind')!='oasst-research-screen-v2':
        raise ValueError('Explicit v2 conversation screening policy required')
    legacy={k:v for k,v in policy.items() if k!='language_rule_sha256'}
    legacy.update(version=1,kind='oasst-research-screen-v1');checked(legacy)
    if policy['language_rule_sha256']!=digest(RULE):raise ValueError('Pinned conversation language rule differs')


def reasons(record,audit,minimum_score):
    from slm.data.dialogue_screen import reasons as legacy_reasons
    flags=legacy_reasons(record,audit,minimum_score)
    if 'not_current_dialogue_candidate' in flags:return flags
    evidence=assess(record['messages'],audit['signals']['language_windows'])
    flags-= {'language_score_attention','language_unscored_or_incomplete'}
    if evidence['hard_attention']:flags.add('strong_non_english_attention')
    return flags
