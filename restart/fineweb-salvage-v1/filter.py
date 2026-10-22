"""Conservative unchanged-text salvage, no model or training dependencies."""
import re
RULES={
 'medical_advice_or_claims':r'\b(?:patient\w*|diagnos\w*|treatments?|symptoms?|supplements?|diseases?|cancer|insulin|therap\w*|medications?|health benefits|mental health|weight loss|brain health|brain function)\b',
 'commercial_or_signup':r'\b(?:buy|purchase|shop|sale|discount|customers?|clients?|book now|booking|registration|register|subscribe|contact us|sign up|refund|shipping|our services|our products|our team|free trial|get in touch|order now|click|download|donate|pricing|price|costs?|fees?|tickets?)\b|[$€₹£]',
 'link_markup_or_encoding':r'https?://|www\.|\[/?\w+[^\]]*\]|<[^>]+>|â€|Ã.|Â.|�|\|',
 'exercise_or_missing_media':r'\b(?:antonyms?|synonyms?|fill in the blank|multiple choice|answer key|worksheet|watch (?:the|this)|video|pictured|image above|image below|photo above|photo below|read more|learn more|see below|see above|figure \d|table \d)\b',
 'boilerplate':r'\b(?:all rights reserved|privacy|cookies|terms and conditions|copyright|leave a reply|posted by|related articles|share this|follow us|newsletter|posted on)\b',
}
def reasons(text,tokens):
 out=[]
 # Conservative standalone prose slice compatible with proposed 512 context, not all recoverable FineWeb.
 if not 120<=tokens<=480:out.append('outside_short_prose_slice_120_480_tokens')
 ls=[x.strip() for x in text.splitlines() if x.strip()]
 if not 2<=len(ls)<=12:out.append('paragraph_count')
 # No guessing how missing headings and list markers should be reconstructed.
 if any(len(re.findall(r"\b[\w'-]+\b",l))<8 for l in ls):out.append('short_heading_or_fragment')
 if any(re.match(r'^\s*(?:[-*•]|\d+[.)])\s',l) for l in ls):out.append('list_layout')
 if any(not re.search(r'[.!?][\s\"\'”’)]*$',l) for l in ls):out.append('unfinished_paragraph')
 if len(re.findall(r'[.!?](?:\s|[\"”])',text))<3:out.append('too_few_sentences')
 for name,pat in RULES.items():
  if re.search(pat,text,re.I):out.append(name)
 return sorted(set(out))
