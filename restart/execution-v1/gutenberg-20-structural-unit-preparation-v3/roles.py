"""Synthetic-only lexical/role proposal; no narrative units or clearance emitted."""
import hashlib,re,importlib.util
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'gutenberg-20-structural-unit-preparation-v1/segment.py'
s=importlib.util.spec_from_file_location('frozen_segment_v1',P);old=importlib.util.module_from_spec(s);s.loader.exec_module(old)
ORDINALS=dict(zip(['FIRST','SECOND','THIRD','FOURTH','FIFTH','SIXTH','SEVENTH','EIGHTH','NINTH','TENTH','ELEVENTH','TWELFTH','THIRTEENTH','FOURTEENTH','FIFTEENTH','SIXTEENTH','SEVENTEENTH','EIGHTEENTH','NINETEENTH','TWENTIETH'],range(1,21)))
CARDINALS=dict(zip(['ONE','TWO','THREE','FOUR','FIVE','SIX','SEVEN','EIGHT','NINE','TEN','ELEVEN','TWELVE','THIRTEEN','FOURTEEN','FIFTEEN','SIXTEEN','SEVENTEEN','EIGHTEEN','NINETEEN','TWENTY'],range(1,21)))
MAX_BYTES=2400000;MAX_EVENTS=8192
sha=lambda b:hashlib.sha256(b).hexdigest()
def number(label,words=False):
 if words and label.upper() in CARDINALS:return CARDINALS[label.upper()],'spelled_cardinal'
 if not re.fullmatch(r'[IVXLCDM]+|[0-9]+',label.upper()):raise ValueError('unsupported_numeral')
 return old.number(label.encode())
def title_ok(t):return bool(re.search('[A-Z]',t)) and not re.search('[a-z]',t) and len(t)<=160

def inspect(raw):
 if type(raw) is not bytes or not 0<len(raw)<=MAX_BYTES:raise ValueError('source_bound')
 text=raw.decode('utf8','strict');lines=[];off=0
 for line in raw.splitlines(keepends=True):
  lines.append((off,off+len(line),line.decode('utf8').strip()));off+=len(line)
 events=[]
 def add(i,kind,**extra):
  if len(events)>=MAX_EVENTS:raise ValueError('role_event_cap_no_truncation')
  a,b,t=lines[i];events.append({'kind':kind,'line_index':i,'start_byte':a,'end_byte':b,'raw_SHA256':sha(raw[a:b]),'raw_label':t,'status':'UNRESOLVED_ROLE_CANDIDATE_NOT_A_CHAPTER_PASS',**extra})
 for i,(a,b,t) in enumerate(lines):
  if re.match(r'chapter\s+\d+:.*=.*\breplaced by\b.*=',t):add(i,'editorial_correction_locator_not_chapter');continue
  m=re.fullmatch(r'CHAPTER\s+([A-Za-z0-9]+)(?:([.:—-])\s*(.{0,160}))?',t,re.I)
  if m:
   try:n,style=number(m[1],True)
   except ValueError:add(i,'unsupported_chapter_label');continue
   tail=m[3] or ''
   if tail and not title_ok(tail):
    prev=lines[i-1][2] if i else ''
    add(i,'prose_chapter_reference' if t.startswith('chapter') and prev else 'ambiguous_chapter_reference_or_heading',number=n,number_style=style);continue
   add(i,'chapter_heading_candidate',number=n,number_style=style,title=tail);continue
  # Standalone uppercase Roman labels only, never M.Ver neuil or I.So prose.
  if re.fullmatch(r'[IVXLCDM]+\.?',t):
   try:n,style=number(t.rstrip('.'))
   except ValueError:add(i,'unsupported_bare_numeral');continue
   j=i+1
   while j<len(lines) and not lines[j][2]:j+=1
   after=lines[j][2] if j<len(lines) else '';before=lines[i-1][2] if i else ''
   letter=bool(re.fullmatch(r'FROM\s+.+\s+TO\s+.+',after))
   add(i,'numbered_letter_candidate' if letter else 'bare_roman_candidate',number=n,number_style=style,blank_before=not bool(before),following_literal_label=after[:200],possible_print_year=n>=1000);continue
  m=re.fullmatch(r'(BOOK|PART|VOLUME|VOL\.)\s+(?:THE\s+)?([A-Za-z0-9]+)\.?',t,re.I)
  if m:
   label=m[2].upper()
   try:
    if label in ORDINALS:n,style=ORDINALS[label],'ordinal'
    else:n,style=number(label,True)
   except ValueError:add(i,'unsupported_hierarchy_label');continue
   add(i,'hierarchy_scope_candidate',scope_type=m[1].upper(),number=n,number_style=style);continue
  m=re.fullmatch(r'END OF THE ([A-Z]+) VOLUME\.?',t,re.I)
  if m:
   if m[1].upper() in ORDINALS:add(i,'end_of_volume_typed_tail_candidate',volume_number=ORDINALS[m[1].upper()],all_tail_preserved=True)
   else:add(i,'unsupported_end_volume_ordinal')
   continue
  if re.fullmatch(r'THE END\.?',t,re.I):add(i,'literal_authored_ending_candidate',all_tail_preserved=True);continue
  if re.fullmatch(r'CONTENTS\.?|TABLE OF CONTENTS\.?',t,re.I):add(i,'contents_anchor_candidate');continue
  if re.fullmatch(r'NOTES|FOOTNOTES|TRANSCRIBER[’\']S NOTES?|TYPOGRAPHICAL ERRORS SILENTLY CORRECTED:',t,re.I):add(i,'note_or_editorial_companion_anchor');continue
  if re.fullmatch(r'ADVERTISEMENTS\.?|PRINTED IN (?:GREAT BRITAIN|THE CITY OF LONDON)(?: BY)?|PRINTED BY .+',t,re.I):add(i,'print_tail_anchor_candidate');continue
  if re.match(r'chapter[,;]\s+',t):add(i,'prose_chapter_word_not_heading');continue
  if re.search(r'\b(?:A SEQUEL TO|VOL\.?\s*\d+\s*OF\s*\d+|IN (?:TWO|THREE) VOLUMES)\b',t,re.I):add(i,'work_relation_or_volume_ancestry_lead');continue
  if re.match(r'\{.*(?:Transcribed by|Notes by the transcriber)',t,re.I):add(i,'explicit_transcriber_component_disclosure')
 # Dense contents is classified only under explicit CONTENTS anchor. Never pick
 # a second cleaner numeric sequence merely because the first one conflicts.
 toc=[]
 for anchor in [e for e in events if e['kind']=='contents_anchor_candidate']:
  j=anchor['line_index']+1;count=0;last=j;seen=False
  while j<len(lines):
   t=lines[j][2]
   if not t:last=j+1;j+=1;continue
   pref=re.fullmatch(r'(?:CHAPTER\s+)?([IVXLCDM]+|\d+)(?:\.(?:\s+|$)|\s+|$)(.*)',t)
   hierarchy=re.fullmatch(r'(?:BOOK|PART|VOLUME)\s+[IVXLCDM0-9]+\.?',t)
   if pref:
    try:number(pref[1])
    except ValueError:break
    count+=1;seen=True;last=j+1;j+=1;continue
   if hierarchy or t in ['CHAPTER','CHAP. PAGE','Epigraph'] or (seen and raw[lines[j][0]:lines[j][1]].startswith(b'        ') and title_ok(t)):
    last=j+1;j+=1;continue
   break
  if count>=2:
   a=anchor['start_byte'];z=lines[last-1][1];toc.append({'start_byte':a,'end_byte':z,'raw_SHA256':sha(raw[a:z]),'entry_count':count,'role':'DENSE_EXPLICIT_CONTENTS_CANDIDATE_ALL_BYTES_PRESERVED'})
 edges=sorted({0,len(raw)}|{e[k] for e in events for k in ['start_byte','end_byte']}|{t[k] for t in toc for k in ['start_byte','end_byte']});parts=[{'start_byte':a,'end_byte':b,'SHA256':sha(raw[a:b]),'role':'UNCHANGED_SOURCE_SPAN'} for a,b in zip(edges,edges[1:])]
 if b''.join(raw[p['start_byte']:p['end_byte']] for p in parts)!=raw:raise ValueError('full_inverse')
 return {'status':'SYNTHETIC_ROLE_PROPOSAL_NO_UNITS_EMITTED','source_SHA256':sha(raw),'events':events,'contents_role_candidates':toc,'parts':parts,'source_bytes_removed':0,'chapter_units_emitted':0,'numeric_sequence_selected':False,'quality_rights_admission_cleared':False,'scope_rules':'Future reviewed planner must reconcile everyTOC/body/hierarchy/number reset/unknown, preserveprefix+epigraphs+notes+tails and bind relatedworkoverlay; no longest/last/cleanest sequence selection.'}
