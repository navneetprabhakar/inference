"""Versioned narrower candidate scope after the retained failed64-dialogue review."""
# Creator: Navneet Prabhakar
import re

def constraints(user,answer):
    reasons=[]
    for quant,number,unit in re.findall(r'(exactly|at least|less than)\s+(\d+)\s+(sentences?|bullet points?|words?|paragraphs?|placeholders?)',user,re.I):
        n=int(number);unit=unit.lower()
        if unit.startswith('sentence'):actual=len(re.findall(r'[.!?](?:[\s\"\]]|$)',answer))
        elif unit.startswith('bullet'):actual=len(re.findall(r'^\s*\*\s+',answer,re.M))
        elif unit.startswith('word'):actual=len(answer.split())
        elif unit.startswith('paragraph'):actual=len(re.split(r'\n\s*\*\*\*\s*\n',answer))
        else:actual=len(re.findall(r'\[[^\[\]\n]+\]',answer))
        if not {'exactly':actual==n,'at least':actual>=n,'less than':actual<n}[quant.lower()]:reasons.append('explicit_count')
    if 'all lowercase' in user.lower() and answer!=answer.lower():reasons.append('lowercase')
    if 'double angular brackets' in user.lower() and not re.search(r'<<[^<>]+>>',answer):reasons.append('title')
    for phrase in re.findall(r'(?:include keywords|Include keywords)\s+\[([^\]]+)\]',user):
        if any(k.strip().lower() not in answer.lower() for k in phrase.split(',')):reasons.append('keyword')
    for word,n in re.findall(r'the word \[([^\]]+)\] should appear at least (\d+) times',user,re.I):
        if len(re.findall(r'\b'+re.escape(word)+r'\b',answer,re.I))<int(n):reasons.append('word_count')
    for letter,n in re.findall(r'the letter ([a-z]) should appear at least (\d+) times',user,re.I):
        if answer.lower().count(letter.lower())<int(n):reasons.append('letter_count')
    for phrase in re.findall(r'finish your response with this exact phrase\s*(?:\[([^\]]+)\]|"([^"]+)")',user,re.I):
        end=next(v for v in phrase if v)
        if end.lower()=='ender':
            match=re.search(r'\[ender\] is "([^"]+)"',user,re.I)
            if not match:reasons.append('unresolved_ending');continue
            end=match.group(1)
        if not answer.rstrip().endswith(end):reasons.append('exact_ending')
    if 'postscript starting with' in user.lower():
        token=re.search(r'postscript starting with\s*\[?([Pp.]+[Ss.]+)',user)
        if token and token.group(1) not in answer:reasons.append('postscript')
    return reasons

def scope(row):
    messages=row['messages'];source=row['source'];text='\n'.join(m['content'] for m in messages);why=[]
    if source=='smol-summarize-5k':return ['mixed_roleplay_and_refusal_constituent_deferred']
    if source=='everyday-conversations':return ['unverified_advice_and_current_claim_constituent_deferred']
    if source=='smollm-rewrite-30k':
        if not messages[0]['content'].startswith("You're an AI assistant for text re-writing. Rewrite the input text to make it more professional and formal"):why.append('only_formal_rewrite_subscope')
    if source=='smol-magpie-ultra-short':
        first=next(m['content'] for m in messages if m['role']=='user')
        if not re.search(r'\b(?:write|rewrite|revise|edit|improve|story|poem|paragraph)\b',first,re.I):why.append('only_grounded_writing_or_creative_subscope')
        if re.search(r'\d|[=^<>]|\b(?:math\w*|calculat\w*|fraction\w*|percent\w*|domain|binary|triangle|circum\w*|hurricane|forecast|Spanish|etymolog\w*)\b',text,re.I):why.append('quantitative_or_niche_subscope_deferred')
    for i,m in enumerate(messages):
        if m['role']!='assistant':continue
        user=messages[i-1]['content'];system=messages[0]['content'] if messages[0]['role']=='system' else ''
        if source=='smol-contraints':why.extend(constraints(user,m['content']))
        if source.startswith(('smol-summarize-20k','smollm-rewrite-30k')):
            # Grounded transformation must preserve all stated numeric tokens and avoid new numbers.
            if not set(re.findall(r'\d+(?:[.:]\d+)*',m['content']))<=set(re.findall(r'\d+(?:[.:]\d+)*',user)):why.append('introduced_number')
        if source=='smol-summarize-20k':
            if 'without using second or third person pronouns' in system and re.search(r'\b(?:you|your|yours|he|she|it|they|him|her|his|its|them|their|theirs|hers)\b',m['content'],re.I):why.append('summary_prohibited_pronoun')
            if 'one very short sentence' in system and (len(m['content'].split())>35 or len(re.findall(r'[.!?](?:\s|$)',m['content']))!=1):why.append('summary_sentence_length')
        if re.search(r'\b(?:current(?:ly)?|this year|today|forecast|health|hygiene|watering|pet.safe|climate|medical|clinical|ALS|scripture|biblical)\b',text,re.I):why.append('new_observed_scope_risk')
    return sorted(set(why))
