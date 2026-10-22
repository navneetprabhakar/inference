"""Strict source-bound chapter candidates; no automatic semantic completeness.
Reuses standalone canonical-numeral chapter sequence from reviewed PG chapter
partition. No arbitrary sentence/word crops, whitespace edits or note deletion.
"""
import re,hashlib
sha=lambda b:hashlib.sha256(b).hexdigest()
LINE_START=rb'(?:\A|(?<=[\r\n]))'
HEAD=rb'(?mi)'+LINE_START+rb'[ \t]*CHAPTER[ \t]+([IVXLCDM]+|[0-9]{1,4})\.?[ \t]*(?:\r\n|\n|\r|$)'
LIKE=rb'(?mi)'+LINE_START+rb'[ \t]*CHAPTER\b[^\r\n]{0,160}'
STRUCT=rb'(?mi)'+LINE_START+rb'[ \t]*(CONTENTS|TABLE OF CONTENTS|LIST OF ILLUSTRATIONS|PREFACE|INTRODUCTION|EPILOGUE|FOOTNOTES|NOTES|TRANSCRIBER(?:\x27S|\xe2\x80\x99S)? NOTE|AUTHOR(?:\x27S|\xe2\x80\x99S)? NOTE|BOOK[ \t]+[IVXLCDM0-9]+|PART[ \t]+[IVXLCDM0-9]+)\.?[ \t]*(?:\r\n|\n|\r|$)'
END=rb'(?mi)'+LINE_START+rb'[ \t]*THE END\.?[ \t]*(?:\r\n|\n|\r|$)'
def need(v,m):
 if not v:raise ValueError(m)
def roman(n):
 out=''
 for v,k in [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]:
  while n>=v:out+=k;n-=v
 return out
def number(label):
 s=label.decode().upper()
 if s.isdigit():
  n=int(s);need(n>=1 and str(n)==s,'noncanonical_arabic_chapter_label');return n,'arabic'
 n=0;i=0;v={'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}
 while i<len(s):
  if i+1<len(s) and v[s[i]]<v[s[i+1]]:n+=v[s[i+1]]-v[s[i]];i+=2
  else:n+=v[s[i]];i+=1
 need(0<n<=4999 and roman(n)==s,'noncanonical_roman_chapter_label');return n,'roman'
def span(raw,a,b,role):return {'role':role,'start_byte':a,'end_byte':b,'bytes':b-a,'SHA256':sha(raw[a:b])}
def discover(raw,envelope,eid):
 need(type(raw) is bytes and 0<len(raw)<=2400000,'raw_bound');raw.decode('utf8','strict');a,z=envelope['start_byte'],envelope['end_byte'];need(0<=a<z<=len(raw) and z-a==envelope['bytes'] and sha(raw[a:z])==envelope['SHA256'],'exact_envelope_binding');body=raw[a:z];raw_digest=sha(raw)
 heads=[];holds=[];unsupported=[];struct=[];ends=[]
 for m in re.finditer(HEAD,body):
  need(len(heads)<1024,'chapter_header_cap')
  try:n,style=number(m[1]);error=None
  except ValueError as exc:n,style,error=None,None,str(exc)
  heads.append({**span(raw,a+m.start(),a+m.end(),'chapter_heading_candidate'),'source_label':m[1].decode(),'number':n,'number_style':style,'label_error':error})
 for m in re.finditer(STRUCT,body):
  need(len(struct)<4096,'structure_hint_cap');struct.append({**span(raw,a+m.start(),a+m.end(),'structure_heading_hint'),'label_exact':m[1].decode('utf8')})
 starts={h['start_byte'] for h in heads}
 for m in re.finditer(LIKE,body):
  if a+m.start() not in starts:
   need(len(unsupported)<4096,'unsupported_heading_hint_cap');unsupported.append(span(raw,a+m.start(),a+m.end(),'unsupported_or_prose_chapter_like_line'))
 for m in re.finditer(END,body):
  need(len(ends)<64,'ending_hint_cap');ends.append(span(raw,a+m.start(),a+m.end(),'literal_the_end_candidate'))
 if len(heads)<2:holds.append('fewer_than_two_supported_chapter_boundaries')
 if any(h['label_error'] for h in heads):holds.append('invalid_or_ambiguous_numeral')
 if heads and [h['number'] for h in heads]!=list(range(1,len(heads)+1)):holds.append('noncontinuous_repeated_or_missing_chapter_sequence')
 if len({h['number_style'] for h in heads})>1:holds.append('mixed_chapter_number_styles')
 if heads:
  first=heads[0]['start_byte']
  if any(h['start_byte']>=first for h in unsupported):holds.append('unsupported_chapter_like_line_within_sequence')
  if any(h['start_byte']>=first and re.fullmatch(r'(?:BOOK|PART)\s+[IVXLCDM0-9]+',h['label_exact'],re.I) for h in struct):holds.append('hierarchy_requires_distinct_policy')
  # A bare title list without any nonheading content cannot stand in for chapters.
  for i,h in enumerate(heads):
   end=heads[i+1]['start_byte'] if i+1<len(heads) else z
   if not raw[h['end_byte']:end].strip():holds.append('empty_chapter_interval_not_authored_unit');break
 if heads:
  table_only=True
  for i,h in enumerate(heads):
   stop=heads[i+1]['start_byte'] if i+1<len(heads) else z
   lines=[line.strip() for line in raw[h['end_byte']:stop].splitlines() if line.strip()]
   if not lines or not all(re.fullmatch(rb'[^\r\n]*\.{2,}[ \t]*[0-9ivxlcdmIVXLCDM]+',line) for line in lines):table_only=False
  if table_only:holds.append('chapter_intervals_are_page_locator_table_candidates')
 parts=[];units=[]
 if holds:
  parts=[span(raw,0,a,'PG_header_and_start_marker'),span(raw,a,z,'whole_envelope_unsegmented_fallback'),span(raw,z,len(raw),'PG_end_marker_and_footer')]
  units=[{**parts[1],'unit_ID':f'pg{eid}:{raw_digest}:{a}-{z}','structural_status':'WHOLE_ENVELOPE_FALLBACK_NOT_CHAPTER_AUDIT_UNIT','semantic_completeness':'UNASSESSED','context_holds':list(holds),'whole_book_family_lineage_required':True}]
 else:
  parts=[span(raw,0,a,'PG_header_and_start_marker'),span(raw,a,heads[0]['start_byte'],'unclassified_print_frontmatter_preserved')]
  endings=[h for h in ends if h['start_byte']>=heads[-1]['end_byte']]
  last_end=endings[0]['end_byte'] if len(endings)==1 else z
  for i,h in enumerate(heads):
   end=heads[i+1]['start_byte'] if i+1<len(heads) else last_end
   part=span(raw,h['start_byte'],end,'chapter_structural_candidate');parts.append(part)
   flags=['semantic_self_containment_and_dependency_review_pending']
   if i+1==len(heads):flags.append('terminal_authored_ending_review_required' if len(endings)==1 else 'last_unit_includes_unresolved_possible_print_endmatter')
   units.append({**part,'unit_ID':f'pg{eid}:{raw_digest}:{h["start_byte"]}-{end}','chapter_number':h['number'],'heading_span':h,'structural_status':'ORDERED_CONSECUTIVE_CHAPTER_INTERVAL_CANDIDATE_NOT_SEMANTIC_PASS','semantic_completeness':'UNASSESSED','context_holds':flags,'whole_book_family_lineage_required':True})
  if last_end<z:parts.append(span(raw,last_end,z,'unclassified_print_endmatter_preserved'))
  parts.append(span(raw,z,len(raw),'PG_end_marker_and_footer'))
 # Full source partition, including empty prefix/tail, no ignored bytes.
 need(parts[0]['start_byte']==0 and parts[-1]['end_byte']==len(raw) and all(p['end_byte']==q['start_byte'] for p,q in zip(parts,parts[1:])),'contiguous_complete_partition')
 need(b''.join(raw[p['start_byte']:p['end_byte']] for p in parts)==raw,'exact_full_source_inverse')
 cursor=0
 for p in parts:
  p['start_character']=cursor;cursor+=len(raw[p['start_byte']:p['end_byte']].decode('utf8'));p['end_character']=cursor
 for u in units:
  part=next(p for p in parts if (p['start_byte'],p['end_byte'])==(u['start_byte'],u['end_byte']));u['start_character']=part['start_character'];u['end_character']=part['end_character']
 notes=[]
 for m in re.finditer(rb'\[(?:[0-9]{1,5}|Footnote[^\]]{0,4000})\]',body):
  need(len(notes)<4096,'note_hint_cap');aa,bb=a+m.start(),a+m.end();line_start=max(raw.rfind(b'\n',a,aa),raw.rfind(b'\r',a,aa),a-1)+1
  notes.append({**span(raw,aa,bb,'note_marker_or_definition_candidate'),'line_initial_marker':not raw[line_start:aa].strip(),'overlapping_unit_IDs':[u['unit_ID'] for u in units if u['start_byte']<bb and aa<u['end_byte']],'definition_extent_or_reference_resolution_proven':False})
 return {'source_raw_SHA256':raw_digest,'raw_bytes':len(raw),'envelope':envelope,'chapter_heading_candidates':heads,'unsupported_chapter_like_lines':unsupported,'structure_heading_hints':struct,'literal_ending_hints':ends,'chapter_sequence_holds':holds,'parts':parts,'units':units,'note_dependency_hints':notes,'unit_boundaries_semantically_complete_proven':False,'notes_front_endmatter_or_editorial_removed':0,'source_bytes_rewritten':0,'full_inverse_verified':True,'whole_envelope_fallback':bool(holds),'new_admitted_documents':0}
