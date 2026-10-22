"""Conservative eligibility flags for visible extraction gaps, never text repair.

Flags are evidence to reject a candidate, not a factual or fluency classifier.
Whitespace alone is deliberately insufficient evidence.
"""
import re

VERSION = 'visible-extraction-gaps-v1'
RULES = (
    ('empty_parenthetical', re.compile(r'\(\s*[,;:]?\s*\)')),
    ('unfilled_placeholder', re.compile(r'_{3,}|\[\s*(?:TODO|TBD|INSERT[^\]]*)\s*\]', re.I)),
    ('missing_prepositional_object', re.compile(r'\b(?:of|at|by|from|to|with)\s+[,.;](?=\s|$)|\b(?:area|territory|length|width|height|depth)\s+of\s+(?=(?:at an elevation|and is|and was)\b)', re.I)),
    ('missing_quantity', re.compile(r'\b(?:area|length|width|height|depth|speed|tonnages?|population|aperture|range)(?: of [^\n.;:]{1,60})?\s+(?:was|were|is|are|of|to)\s+(?:and\s+)?[.,;]', re.I)),
    ('blank_population_field', re.compile(r'\b(?:current\s+)?population\s*:\s*(?=[A-Z][a-z]+\b|$)', re.M)),
    ('missing_named_subject', re.compile(r'\b(?:the|a|an)\s+[.,;](?=\s|$)', re.I)),
    ('unfilled_citation_transition', re.compile(r'\bcitation\s+for[^\n]{0,150}reads\s+as\s+follows\s*:\s*\n\s*\n(?=[A-Za-z])', re.I)),
)

def find_gaps(text):
    if not isinstance(text, str):
        raise TypeError('Expected source text')
    findings=[]
    for rule,pattern in RULES:
        for match in pattern.finditer(text):
            findings.append({'rule':rule,'start':match.start(),'end':match.end(),
                             'matched_text':match.group(),
                             'context':text[max(0,match.start()-45):min(len(text),match.end()+70)]})
    return sorted(findings,key=lambda x:(x['start'],x['rule']))
