"""Conservative structural exclusions; never repairs text or certifies facts."""
import re
from urllib.parse import urlsplit, parse_qs
VERSION = 'edu-institutional-structure-v3'
NUMBERS = {w:i for i,w in enumerate(('zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve'))}
NUMBER = r'(?:[2-9]|1[0-2]|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)'
ANNOUNCEMENT = re.compile(r'\b(?:following|includes?|identifies?|contains?|consists? of|are)\s+(?:the\s+)?('+NUMBER+r')\b[^\n:]{0,100}:\s*$',re.I)
BULLET = re.compile(r'^\s*(?:[-*•]|\d+[.)])\s+\S')

def reasons(row):
    text=row['text']; u=urlsplit(row['url']); path=u.path.lower()
    query={k.lower() for k in parse_qs(u.query,keep_blank_values=True)}
    found=[]
    if re.search(r'(?:^|/)(?:sources-search|search|categories?|tags?|archives?)(?:/|$)',path) or query.intersection({'cat','category','search','search_text_zotero_tags','field_zotero_collections'}):
        found.append('search_or_archive_url')
    if re.search(r'(?im)^\s*displaying\s+\d+\s*[-–]\s*\d+\s+of\s+\d+',text):
        found.append('result_list_payload')
    if re.search(r'(?i)questions? for (?:photo|figure|image)|(?:figures|objects) are label[l]?ed|continue with the analysis of the (?:painting|image)|these PDFs provide|tables also indicate',text):
        found.append('required_missing_visual_or_table')
    if re.search(r'(?i)(?:explore|visit) (?:the )?(?:links|websites|sites) below',text):
        found.append('missing_resource_landing_page')
    if re.search(r'(?i)(?:image below shows you where|click on the picture|in this video you will learn|second article below|2nd article below)',text):
        found.append('visual_interface_tutorial')
    if re.search(r'(?im)(?:located at|looks like this)\s*:\s*(?:\.|\n|$)',text) or re.search(r'(?im)\bby\s*\n\s*in the\b',text):
        found.append('empty_instruction_argument')
    lines=text.splitlines()
    for i,line in enumerate(lines):
        m=ANNOUNCEMENT.search(line)
        if not m:continue
        value=m.group(1).lower();expected=int(value) if value.isdigit() else NUMBERS[value]
        actual=0
        for following in lines[i+1:]:
            if not following.strip() and actual==0:continue
            if BULLET.match(following):actual+=1
            else:break
        if actual!=expected:
            found.append('unverified_announced_list_completeness')
    return sorted(set(found))
