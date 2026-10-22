"""Role-aware development delta; review holds never authorize cropping or book rejection."""
import hashlib,importlib.util,json,re
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'pressbooks-structural-repair-preparation-v2/policy.py'
s=importlib.util.spec_from_file_location('frozen_structural_v2',P);v2=importlib.util.module_from_spec(s);s.loader.exec_module(v2)
MAX_EVENTS=5000
MAX_RECEIPT=2000000
ASSESS=re.compile(r'(?mi)^[ \t]*(?:(?:Section\s+[\d.]+\s*:\s*)?(?:Chapter\s+\w+\s+)?Self[- ]Test|Self[- ]Check(?:\s*:[^\n]*)?|Knowledge Check|Check Your Knowledge)\s*$')
BOUNDARY=re.compile(r'(?mi)^[ \t]*(?:Licenses and Attributions(?: for[^\n]*)?|References|Works Cited|Image Attributions|Attributions|Show Glossary|Discussion Questions|Further Reading)\s*$')
BOILER=re.compile('(?:'+'|'.join(v2.BOILERPLATE+[r'You[’\']ll have more success on the Self[- ]Check,? if you[’\']ve completed the [A-Za-z0-9 -]+ Readings? in this section\.',r'Complete the (?:activity|quiz|test) below to check your knowledge\.'])+')',re.I)
PROMPT=re.compile(r'\?|\b(?:choose|select|identify|explain|which|what|why|how|calculate|determine|complete|match|fill)\b',re.I)
WALL='This content is password protected. To view it please enter your password below:'
COPYRIGHT=re.compile(r'^.+ Copyright © \d{4} by .+ is licensed under a Creative Commons .+License, except where otherwise noted\.$')
PDF=re.compile(r'Read the attached document, [^\n]{1,180}\.pdf\)\.',re.I)
READER=re.compile(r'You will need Adobe Acrobat Reader to access this file\s*\.?\s*\d*\s*\.?',re.I)
RESOURCE_HEADING=re.compile(r'(?:\d+\s+)?(?:Readings and Resources|Readings|Resources|Video|Watch the Video|An? Infographic|Overview: An? Infographic)',re.I)
MEDIA_INSTRUCTION=re.compile(r'(?:Watch|View|Listen to) the (?:following|attached|video below|infographic below|video|infographic|PDF|document)(?: video| infographic)?[.!?]?',re.I)
DEPENDENCY=re.compile(r'(?i)(?:\b(?:required|use|using|derive|determine|compare|consider|interpret|examine|refer to|shown in|see from)\b[^\n.!?]{0,180}\b(?:figure|table|diagram|chart|headshots|lightcurves?|image|photograph)s?\b[^\n.!?]{0,80}|\b(?:figure|table|diagram|chart|infographic|video|playlist)\b[^\n.!?]{0,100}\b(?:below|following|shows|illustrates)\b[^\n.!?]{0,100}|\b(?:following|below)\b[^\n.!?]{0,100}\b(?:video|playlist|infographic|diagram)s?\b[^\n.!?]{0,100})')
def assess(text):
 prior=v2.assess(text);raw=text.encode('utf8');mask=v2.code_mask(text);bs=v2.base.offsets(text);holds=[];queue=[]
 def emit(target,reason,a,b,detail):
  if len(holds)+len(queue)>=MAX_EVENTS:raise ValueError('v3_event_cap_no_truncation')
  target.append({'reason':reason,'char_start':a,'char_end':b,'byte_start':bs[a],'byte_end':bs[b],'source_span_SHA256':hashlib.sha256(raw[bs[a]:bs[b]]).hexdigest(),'detail':detail,'disposition':'SCOPED_REPRESENTATION_REVIEW_HOLD' if target is holds else 'PENDING_DEPENDENCY_REVIEW_ONLY'})
 # Exact wall grammar, plus wholly recognized navigation/password/footer context.
 a=mask.find(WALL)
 if a>=0:
  before=mask[:a].strip();after=mask[a+len(WALL):].strip().splitlines();nav=before.splitlines()
  navok=(not before) or (len(nav)>=2 and nav[0]=='Primary Navigation' and nav[1]=='Book Contents Navigation' and len(nav)<=300 and all(len(z)<=120 and not re.search(r'[!?]|(?<!\d)\.(?!\d)',re.sub(r'^\d+\.\s*','',z)) for z in nav[2:]))
  afterok=bool(after) and after[0]=='Password:' and all(z=='Previous/next navigation' or COPYRIGHT.fullmatch(z) for z in after[1:])
  if navok and afterok:emit(holds,'EXACT_ACCESS_WALL_WITHOUT_CAPTURED_BODY',a,a+len(WALL),{'recognized_navigation_only':True,'unknown_authored_text_prevents_rule':True,'not_a_book_rejection':True})
  else:emit(queue,'ACCESS_WALL_MENTION_CONTEXT_UNRESOLVED',a,a+len(WALL),{'unknown_content_or_example_prevents_automatic_hold':True})
 # Resource-only role requires every nonempty line be known access grammar.
 lines=[];off=0
 for line in mask.splitlines(keepends=True):
  t=line.strip()
  if t:lines.append((off,off+len(line),t))
  off+=len(line)
 resource_count=0;unknown=[]
 for a,b,t in lines:
  if RESOURCE_HEADING.fullmatch(t):continue
  if PDF.fullmatch(t) or READER.fullmatch(t) or MEDIA_INSTRUCTION.fullmatch(t):resource_count+=1
  else:unknown.append((a,b))
 if resource_count and not unknown:emit(holds,'RESOURCE_ACCESS_ONLY_NO_SUBSTANTIVE_CAPTURED_BODY',0,len(text),{'all_nonempty_lines_recognized':True,'unknown_meaningful_text_prevents_rule':True,'does_not_prove_external_resource_missing_or_book_unusable':True})
 # Explicit assessment block ends only at a recognized source heading or EOF.
 for m in ASSESS.finditer(mask):
  nxt=BOUNDARY.search(mask,m.end());end=nxt.start() if nxt else len(mask);tail=mask[m.end():end];pos=0;count=0
  while True:
   z=tail[pos:];pos+=len(z)-len(z.lstrip());mm=BOILER.match(tail,pos)
   if not mm:break
   count+=1;pos=mm.end()
  if not tail[pos:].strip():
   emit(holds,'EXPLICIT_EMPTY_ASSESSMENT_BLOCK',m.start(),end,{'recognized_boilerplate_sentences':count,'following_boundary':nxt.group().strip() if nxt else 'EOF','unknown_intervening_content_prevents_rule':True})
  else:emit(queue,'ASSESSMENT_BLOCK_CONTENT_ROLE_UNRESOLVED',m.start(),end,{'unknown_content_preserved':True,'does_not_assert_questions_absent':True})
 # A Practice block with only bare options and Show Answer lacks a captured prompt.
 for m in re.finditer(r'(?mi)^Practice\s*$',mask):
  ender=re.search(r'(?mi)^Show Answer\s*$',mask[m.end():])
  if not ender:continue
  show_start=m.end()+ender.start();show_end=m.end()+ender.end();options=[z.strip() for z in mask[m.end():show_start].splitlines() if z.strip()]
  nexthead=BOUNDARY.search(mask,show_end);end=nexthead.start() if nexthead else len(mask);answer=mask[show_end:end].strip()
  previous=mask[:m.start()].rstrip().split('\n')[-1:]
  bare=2<=len(options)<=12 and all(re.fullmatch(r'(?:[-*•]|[a-lA-L][.)])\s+[^\n]{1,120}',z) and not PROMPT.search(z) for z in options)
  answerok=bool(re.fullmatch(r'[a-lA-L](?:[.)])?',answer))
  if bare and answerok and not any(PROMPT.search(z) for z in previous):emit(holds,'PRACTICE_OPTIONS_AND_ANSWER_WITHOUT_CAPTURED_PROMPT',m.start(),end,{'bare_option_count':len(options),'preceding_prompt_cue_prevents_rule':True,'no_reconstruction_or_crop':True})
  else:emit(queue,'PRACTICE_PROMPT_RELATION_UNRESOLVED',m.start(),end,{'unknown_or_possible_prompt_preserved':True})
 for m in DEPENDENCY.finditer(mask):emit(queue,'NAMED_MEDIA_COMPARISON_OR_REQUIRED_CONTEXT_REVIEW',m.start(),m.end(),{'presence_absence_or_necessity_not_proven':True,'not_an_automatic_hold':True,'same_source_family_preserved':True})
 result={'status':'DEVELOPMENT_STRUCTURAL_V3_NOT_ACCEPTANCE','source_SHA256':prior['source_SHA256'],'source_UTF8_bytes':len(raw),'prior_v2':prior,'delta_representation_review_holds':holds,'pending_dependency_queue':queue,'decision':'HOLD_REPRESENTATION_REVIEW' if holds or prior['decision']=='HOLD_REPRESENTATION_REVIEW' else 'RAW_CANDIDATE_UNCHANGED_PENDING_ALL_GATES','raw_unchanged':True,'source_bytes_removed':0,'rights_generation_family_status':'UNASSESSED_SEPARATE_COMPONENT_INTERFACE','new_admissions':0}
 if len(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode())>MAX_RECEIPT:raise ValueError('v3_receipt_cap_no_partial_success')
 return result
