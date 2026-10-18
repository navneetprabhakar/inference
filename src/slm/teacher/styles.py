"""Versioned rendering guidance and non-authorizing teacher diagnostics."""
import re
from jsonschema import Draft202012Validator,ValidationError
from slm.data.schema import digest
from slm.teacher.workflow import check_scenario
from slm.teacher.scenarios import output_schema,validate

VERSION='five-styles-v1'
GUIDES={
 'professional':'Use concise complete sentences, neutral precise wording and a professional tone. Avoid ceremonial greetings and filler.',
 'casual':'Use relaxed everyday English and natural conversational phrasing; contractions are welcome where natural. Avoid forced slang.',
 'terse':'Use the shortest clear answer or compact fragments. Keep essential facts, units, negation and any needed question; remove filler.',
 'humorous':'Give the useful answer with brief light wordplay or a clearly non-factual aside. Never invent facts, outcomes or amounts for a joke; avoid insults.',
 'caveman':'Use intelligible telegraphic English: short clipped clauses or fragments, with articles/copulas omitted where clear. A normal complete sentence with changed punctuation is insufficient. Do not impersonate an identity or add animal noises.'}
INVARIANTS=('Render only reply in the requested style; preserve the structured facts, action, tool result and content setting. '
 'Preserve quantities, units, references, corrections, negation, uncertainty and user constraints. '
 'A clarification must ask for the missing information, never guess it. '
 'Style must change diction or syntax, not just numeric grouping or punctuation. '
 'Do not add facts or omit essential meaning to make styles look different. '
 'For short answers, distinguish phrasing using the requested style without padding the answer. '
 'The style field is a label, not evidence that reply realizes it.')


def instructions():
    return ('Style rendering contract '+VERSION+'. '+INVARIANTS+'\n'
        +'\n'.join(name+': '+GUIDES[name] for name in sorted(GUIDES)))


# Only valid grouped positive integers normalize here. Digit lists such as "1,2"
# and decimals stay untouched. This is an observation, not semantic parsing.
GROUPED=re.compile(r'(?<![\w.,])\d{1,3}(?:,\d{3})+(?![\w,]|\.\d)')
NUMBERS=re.compile(r'(?<![\w.,])-?\d+(?:\.\d+)?(?![\w,]|\.\d)')
NEGATION=re.compile(r"\b(?:no|not|never|without|cannot|can't|don't|doesn't|isn't|won't)\b",re.I)


def surface(text):
    return ' '.join(GROUPED.sub(lambda m:m.group().replace(',',''),text).casefold().split())


def integers(value):
    if type(value) is int:return {value}
    if isinstance(value,dict):return set().union(*(integers(v) for v in value.values())) if value else set()
    if isinstance(value,list):return set().union(*(integers(v) for v in value)) if value else set()
    return set()


def assess(scenario,candidate):
    check_scenario(scenario)
    try:Draft202012Validator(output_schema(scenario)).validate(candidate)
    except ValidationError:
        return {'version':VERSION,'schema_passed':False,'structured_checks':{},'structured_passed':False,
            'meaning_verified':False,'style_verified':False,'training_eligible':False,'human_attestation':False}
    checks=validate(scenario,candidate);reply=candidate['reply'];normalized=surface(reply)
    allowed=integers(scenario['facts'])|integers(candidate['tool_result'])
    observed=[m.group() for m in NUMBERS.finditer(normalized)]
    parsed={int(v) for v in observed if '.' not in v}
    return {'version':VERSION,'schema_passed':True,'structured_checks':checks,'structured_passed':all(checks.values()),
        'reply_sha256':digest(reply),'requested_style':scenario['style'],'style_guide':GUIDES[scenario['style']],
        'surface_observations':{'word_count':len(reply.split()),'character_count':len(reply),
            'numeric_literals':observed,'oracle_integer_values':sorted(allowed),
            'integer_literals_outside_oracle':sorted(parsed-allowed),'negation_marker_present':bool(NEGATION.search(reply))},
        'meaning_verified':False,'style_verified':False,'human_attestation':False,'training_eligible':False,
        'limitations':'Numeric literals and negation are review cues only: words, units, scope, references and truth are not verified; no cue grants or denies semantic/style approval'}


def compare(left_scenario,left_candidate,right_scenario,right_candidate):
    check_scenario(left_scenario);check_scenario(right_scenario)
    fields=('family_id','split','task','content_category','parents','context','facts','expected_action')
    if any(digest(left_scenario[k])!=digest(right_scenario[k]) for k in fields):
        raise ValueError('Style comparison requires the same context, family and semantic scenario')
    if left_scenario['style']==right_scenario['style']:raise ValueError('Two different requested styles required')
    left=assess(left_scenario,left_candidate);right=assess(right_scenario,right_candidate)
    valid=left['schema_passed'] and right['schema_passed']
    identical=None;metadata_equal=False
    if valid:
        identical=surface(left_candidate['reply'])==surface(right_candidate['reply'])
        metadata_equal=all(digest(left_candidate[k])==digest(right_candidate[k]) for k in ('facts','action','tool_result','content_category'))
    return {'version':VERSION,'left':left,'right':right,'structured_fields_equal':metadata_equal,
        'replies_equal_ignoring_case_whitespace_numeric_grouping':identical,
        'style_nonseparation_cue':identical,'meaning_equivalence_verified':False,'style_separation_verified':False,
        'human_attestation':False,'training_eligible':False,
        'review_required':['Compare quantities, units, negation, references, corrections and final tool outcome in the actual replies.',
            'Apply each requested style guide to diction and syntax; different text alone is not style adherence.',
            'Review content setting independently of style.'],
        'scope':'Structured oracle equality plus surface observations; no automatic free-text meaning/style judgment or training approval'}
