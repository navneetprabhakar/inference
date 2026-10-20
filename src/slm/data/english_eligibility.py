"""Conservative finite recovery-corpus eligibility; no factual certification."""
# Creator: Navneet Prabhakar
import re
from slm.data.quality_audit import PATTERNS
RULE=dict(min_characters=300,max_characters=12000,minimum_words=80,maximum_ellipsis=1)
JUNK=re.compile(r'(?i)must be logged in|reply to this topic|coursework writing|did you find this review helpful|more on journey|test your knowledge|\b(?:subscribe|buy now|add to cart)\b')
CLINICAL=re.compile(r'(?i)\b(?:pharmacotherapy|antifungal|chemotherapy|treatment plan|treating depression|diagnostic criteria|dsm-5|prescribed|dosage|cure the infection)\b')
PHONE=re.compile(r'(?<!\d)(?:\(\d{3}\)\s*\d{3}[- ]\d{4}|\+\d[\d ()-]{8,16}\d)(?!\d)')
BIOGRAPHY=re.compile(r'(?i)\b(?:born|biography|biographical|early years and education|professional milestones)\b')
CITATION=re.compile(r'(?i)\bet al\.,?\s*\(?\d{4}|\baccording to (?:gartner|statista)|\brecent research (?:indicates|shows|suggests)')
def reasons(record):
 t=record['texts']['content'];r=[];s=record['ingredient']
 if not RULE['min_characters']<=len(t)<=RULE['max_characters'] or len(t.split())<RULE['minimum_words']:r.append('bounded_coherent_prose_length')
 if t.count('...')+t.count('…')>RULE['maximum_ellipsis']:r.append('search_excerpt_ellipsis')
 if not re.search(r'[.!?][\s\"\u201d\u2019\)\]]*$',t):r.append('incomplete_terminal')
 if JUNK.search(t):r.append('navigation_spam_promotion')
 if CLINICAL.search(t):r.append('clinical_treatment_scope')
 if PHONE.search(t) or any(p.search(t) for p in PATTERNS.values()):r.append('privacy_contact_credential_signal')
 if s=='explanatory' and BIOGRAPHY.search(t):r.append('synthetic_biography_uncertainty')
 if s=='explanatory' and CITATION.search(t):r.append('synthetic_attribution_uncertainty')
 return r
