"""Synthetic-reviewed exact-span development segmentation, not an eligibility classifier."""
import hashlib,re
MAX_BYTES=200000;MAX_GROUPS=1000
SPEAKER=r'(?:Lord|Baroness|Earl|Viscount|Countess|Bishop|The (?:Earl|Countess|Marquess|Duke|Lord Bishop|Lord Speaker|Chairman of Committees))[^:\n]{0,180}'
ATTR=re.compile(r'^('+SPEAKER+r'):[ \t]*(.*)$')
ASKED=re.compile(r'^('+SPEAKER+r') (asked\b.*)$')
# Exact observed source-authored department labels, not fuzzy named-entity guesses.
DEPARTMENTS=frozenset({'Home Office','Ministry of Justice'})
QUESTION=re.compile(r'^(?:To ask|asked)\b')
def speech(line):
 m=ATTR.fullmatch(line.strip()) or ASKED.fullmatch(line.strip())
 return (m.group(1),m.group(2)) if m else None
def heading(line):
 s=line.strip()
 if not s or len(s)>200 or speech(s) or '\t' in s or s[-1] in '.?!;,' or re.search(r'[0-9]',s):return False
 words=re.findall(r'[A-Za-z]+',s)
 return bool(words) and all(w[0].isupper() or w in {'of','the','and','for','in','on','to','at','a','an'} for w in words)
def segment(text):
 raw=text.encode('utf-8')
 if len(raw)>MAX_BYTES:raise ValueError('source_byte_cap')
 if '\r' in text or '\x00' in text:raise ValueError('unsupported_line_control')
 lines=text.splitlines(keepends=True);offsets=[];pos=0
 for line in lines:offsets.append(pos);pos+=len(line)
 questions=[];answers=[]
 for i,line in enumerate(lines):
  s=speech(line.rstrip('\n'))
  if s:
   (questions if QUESTION.match(s[1]) else answers).append((offsets[i],i,s[0]))
 if len(questions)>MAX_GROUPS:raise ValueError('question_count_cap')
 starts=[];ambiguous=[];departments=[];has_answer=False;lastq=None
 for q,line,speaker in questions:
  if lastq is not None:has_answer=any(lastq<a<q for a,_,_ in answers)
  if lastq is None or has_answer:
   j=line-1
   while j>=0 and not lines[j].strip():j-=1
   start=q
   if j>=0 and not speech(lines[j].rstrip('\n')) and lines[j].strip() and (j==0 or not lines[j-1].strip()):
    if heading(lines[j]) and ':' in lines[j]:start=offsets[j]
    elif len(lines[j].strip())<=200 and lines[j].strip()[-1] not in '.?!;,' and '\t' not in lines[j]:ambiguous.append((offsets[j],q))
   # A department is recognized only as a standalone blank-delimited line,
   # immediately before the question or its single colon-topic heading.
   k=j
   if j>=0 and heading(lines[j]) and ':' in lines[j]:
    k=j-1
    while k>=0 and not lines[k].strip():k-=1
   if k>=0 and lines[k].strip() in DEPARTMENTS and (k==0 or not lines[k-1].strip()) and k+1<len(lines) and not lines[k+1].strip():
    departments.append((offsets[k],start,lines[k].strip()))
    ambiguous=[(x,y) for x,y in ambiguous if x!=offsets[k]]
   starts.append(start)
  lastq=q
 boundaries={0,len(text),*starts}
 for a,z in ambiguous:boundaries.update([a,z])
 for a,z,label in departments:boundaries.update([a,z])
 bs=sorted(boundaries);parts=[];current=None
 for a,z in zip(bs,bs[1:]):
  if a==z:continue
  if any(a>=x and z<=y for x,y,_ in departments):kind='DEPARTMENT_CONTEXT_SIDECAR'
  elif any(a>=x and z<=y for x,y in ambiguous):kind='HELD_AMBIGUOUS_HEADING_OWNERSHIP'
  elif a in starts:kind='QUESTION_ANSWER_GROUP';current=a
  elif current is None:kind='HELD_ORPHAN_PREFIX'
  else:kind='QUESTION_ANSWER_GROUP'
  if parts and parts[-1]['kind']==kind=='QUESTION_ANSWER_GROUP' and a not in starts:parts[-1]['char_end']=z
  else:parts.append({'kind':kind,'char_start':a,'char_end':z,'holds':[]})
 # All component text remains inside exact raw partition; no arbitrary sentence crop.
 bytepos=0;active_department=None
 for n,p in enumerate(parts):
  a,z=p['char_start'],p['char_end'];s=text[a:z];qb=[q for q in questions if a<=q[0]<z];ab=[x for x in answers if a<=x[0]<z]
  p.update({'part_ordinal':n,'UTF8_start':bytepos,'UTF8_end':bytepos+len(s.encode()),'raw_SHA256':hashlib.sha256(s.encode()).hexdigest(),'question_turns':len(qb),'answer_turns':len(ab),'question_speakers':[q[2] for q in qb],'answer_speakers':[x[2] for x in ab],'raw_text':s,'context_flags':[],'new_group_eligibility':'UNCLEARED_REQUIRES_NEW_LANGUAGE_COUNT_QUALITY_RIGHTS_FAMILY_CUSTODY','parent_representation_holds_are_provenance_not_inferred_daughter_verdict':True});bytepos=p['UTF8_end']
  if p['kind']=='DEPARTMENT_CONTEXT_SIDECAR':
   active_department={'label':s.strip(),'part_ordinal':n,'char_span':[a,z],'UTF8_span':[p['UTF8_start'],p['UTF8_end']],'raw_SHA256':p['raw_SHA256']}
   p['context_flags'].append('OBSERVED_DEPARTMENT_LABEL_CONTEXT_NOT_ANSWER_PROSE')
  p['department_context']=dict(active_department) if active_department else None
  if p['kind']!='QUESTION_ANSWER_GROUP':p['holds'].append(p['kind'])
  elif not qb or not ab:p['holds'].append('QUESTION_WITHOUT_SUPPORTED_ANSWER')
  elif any(x[0]<qb[0][0] for x in ab):p['holds'].append('ANSWER_BEFORE_QUESTION')
  if len(set(x[2] for x in ab))>1:p['holds'].append('MULTIPLE_ANSWER_SPEAKERS_REVIEW')
  if ab:
   answer=s[ab[0][0]-a:];body=answer.split(':',1)[-1].strip()
   if not body:p['holds'].append('EMPTY_SUPPORTED_ANSWER_REVIEW')
   if len(body)<650 and re.match(r'(?:I refer\b|Please see\b|See\b)',body):p['holds'].append('POSSIBLE_REFERENCE_ONLY_REQUIRED_CONTEXT_REVIEW')
  if re.search(r'\b(?:attached|attachment|Excel|SpreadSheet|\.xlsx?\b)',s,re.I):p['context_flags'].append('ATTACHMENT_REFERENCE_REVIEW_NOT_AUTOMATIC_MISSING_CONTENT')
  if '\t' in s:p['context_flags'].append('RAW_LAYOUT_TABS_RETAINED_NOT_AUTOMATIC_TABLE_FAILURE')
  if re.search(r'\b(?:earlier|previous|Written Answer|Library|Official Report)\b',s):p['context_flags'].append('SUPPLEMENTAL_OR_PRIOR_REFERENCE_RETAINED')
 for p in parts:
  if p['kind']=='DEPARTMENT_CONTEXT_SIDECAR':
   p['following_group_parts']=[q['part_ordinal'] for q in parts if q['kind']=='QUESTION_ANSWER_GROUP' and q['department_context'] and q['department_context']['part_ordinal']==p['part_ordinal']]
 if bytepos!=len(raw) or ''.join(p['raw_text'] for p in parts)!=text or any(p['char_end']!=q['char_start'] for p,q in zip(parts,parts[1:])):raise ValueError('exact_partition_inverse')
 return parts
