"""Synthetic-only generic structural delta; whole originals remain immutable.
Signals are representation-review holds, not English/major-corruption verdicts.
No corpus execution or component crop is authorized by this module.
"""
import hashlib,importlib.util,json,re
from pathlib import Path
OLD=Path(__file__).resolve().parents[1]/'pressbooks-raw-unit-filter-preparation-v1/policy.py'
spec=importlib.util.spec_from_file_location('frozen_pb_raw_policy_v1',OLD)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
MAX_EVENTS=5000
MAX_RECEIPT=2000000
RULES={
'UNBALANCED_LATEX_WRAPPER':'A non-code mathematical latex block has missing, nested or extra paired wrapper; never infer missing content.',
'EMPTY_INTRODUCED_MATH_ENDPOINT':'A non-code explicit mathematical expression ends at = or an unfilled opening operator before closing wrapper.',
'EMPTY_INTRODUCED_EQUATION_SLOT':'An explicit equation/formula introduction ends before an immediate where-constants explanation without its introduced expression.',
'EMPTY_REQUIRED_ASSESSMENT_SLOT':'A named assessment section contains only explicit complete-the-test boilerplate, with no captured item or activity. Unknown intervening content prevents this rule.'}
DIAGNOSTICS={
'NAMED_VISUAL_DEPENDENCY_REVIEW':'Explicit comparison/interpretation of named visual content; presence or necessity is not proved by raw strings.',
'ASSESSMENT_DEPENDENCY_REVIEW':'Named assessment heading or an explicit below-question prompt; not automatically missing.',
'AMBIGUOUS_LITERAL_LATEX_TOKEN':'Unbalanced latex token without mathematical context; source/role review only.'}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def require(v,m):
 if not v:raise ValueError(m)
def code_mask(text):
 """Protect explicit fenced/inline literal code only, preserving exact positions."""
 out=list(text);ranges=[];fence=None;start=None;offset=0
 for line in text.splitlines(keepends=True):
  m=re.match(r'^\s*(`{3,}|~{3,})',line)
  if fence is None and m:fence=m.group()[m.group().find(m.group(1)[0]):];start=offset
  elif fence is not None and m and m.group(1)[0]==fence[0] and len(m.group(1))>=len(fence):ranges.append((start,offset+len(line)));fence=None
  offset+=len(line)
 if fence is not None:ranges.append((start,len(text)))
 for a,b in ranges:out[a:b]=' '* (b-a)
 working=''.join(out)
 for m in re.finditer(r'(`+)([^`\n]*?)\1',working):out[m.start():m.end()]=' '*(m.end()-m.start())
 return ''.join(out)
MATH=re.compile(r'[=<>≤≥^]|\\(?:frac|mathrm|displaystyle|leq|geq)\b|\b[Pfp]\s*\(')
HEADING=re.compile(r'(?mi)^(?:(?:Section\s+[\d.]+\s*:\s*)?(?:Chapter\s+\w+\s+)?Self[- ]Test|Self[- ]?\s*Check(?:\s*:[^\n]*)?|Knowledge Check|Check Your Knowledge)\s*$')
# Anchored complete sentences/paragraphs, not a whitelist of arbitrary words.
BOILERPLATE=[
 r'It is a good idea to test your knowledge after you have completed each chapter\.',
 r'This section presents a Self-Test for Chapter [A-Za-z0-9 -]+\.',
 r'Please complete the test now to assess your learning of the ideas inside this chapter\.',
 r'Answer the question\(s\) below to see how well you understand the topics covered in the previous section\.',
 r'This short quiz does not count toward your grade in the class, and you can retake it an unlimited number of times\.',
 r'You[’\']ll have more success on the Self Check if you[’\']ve completed the two Readings in this section\.',
 r'Use this quiz to check your understanding and decide whether to \(1\) study the previous section further or \(2\) move on to the next section\.'
]
BOILERPLATE_RE=re.compile(r'(?:'+ '|'.join(BOILERPLATE)+r')',re.I)
def prior_event_bound(text):
 # Frozen v1 finding-call upper bound, before invoking its allocation-heavy API.
 upper=2
 patterns=[r'\(\s*(?:and|or|,)\s*\)',r'(?is)\[latex\]\s*\[/latex\]|\\\[\s*\\\]',r'(?m)^For the (?:relation|function|equation|matrix|expression)\s*\n(?=[ⓐⓑⓒ]|[a-z][.)]\s)',r'(?i)estimated to be about[ \t]*\n[ \t]*(?=However\b|Therefore\b|Thus\b)',r'\band[.]',r'\b(?:Figure|Fig\.)\s*(?:\([^)\n]*\)|\d[\w.:-]*)?',r'\[/?latex\]|\\\(|\\\[',r'(?mi)^(?:glossary|references|works cited|image attributions|attributions|further reading|key terms|summary)\s*$']
 for pattern in patterns:
  for _ in re.finditer(pattern,text):
   upper+=1;require(upper<=MAX_EVENTS,'prior_event_cap_before_allocation')
 for m in re.finditer(r'[^\n]+',text):
  s=m.group()
  if re.match(r'^\s*//',s) and re.search(r'\bclass\s+[A-Za-z_]\w*\s*\{',s) and re.search(r'\bstatic\s+(?:void|[A-Za-z_]\w*)\s+\w+\s*\(',s) and ';' in s:
   upper+=1;require(upper<=MAX_EVENTS,'prior_event_cap_before_allocation')
 return upper
def assess(text):
 require(isinstance(text,str),'text_type');raw=text.encode('utf8');require(len(raw)<=base.MAX_BYTES,'raw_text_cap')
 # Reuse only reviewed frozen v1 decisions; all additions separate and bounded.
 prior_upper=prior_event_bound(text);prior=base.filter_raw(text);require(len(prior['reasons'])+len(prior['context_only_diagnostics'])<=prior_upper,'prior_bound_mismatch');mask=code_mask(text);bs=base.offsets(text);holds=[];signals=[]
 def finding(target,reason,a,b,detail):
  require(len(holds)+len(signals)<MAX_EVENTS,'delta_event_cap_no_truncation')
  target.append({'reason':reason,'char_start':a,'char_end':b,'byte_start':bs[a],'byte_end':bs[b],'source_span_SHA256':sha(raw[bs[a]:bs[b]]),'detail':detail})
 markers=[]
 for m in re.finditer(r'\[(/?)latex\]',mask,re.I):
  require(len(markers)<MAX_EVENTS,'latex_token_cap_before_list_growth');markers.append(m)
 stack=None
 for m in markers:
  if not m.group(1):
   if stack is not None:
    segment=mask[stack.end():m.start()]
    finding(holds if MATH.search(segment) else signals,'UNBALANCED_LATEX_WRAPPER' if MATH.search(segment) else 'AMBIGUOUS_LITERAL_LATEX_TOKEN',stack.start(),m.end(),{'shape':'nested_open','replacement_inferred':False})
   stack=m
  else:
   if stack is None:
    context=mask[max(0,m.start()-256):m.start()]
    finding(holds if MATH.search(context) else signals,'UNBALANCED_LATEX_WRAPPER' if MATH.search(context) else 'AMBIGUOUS_LITERAL_LATEX_TOKEN',m.start(),m.end(),{'shape':'extra_close','replacement_inferred':False})
   else:
    content=mask[stack.end():m.start()].strip()
    if re.search(r'(?:=\s*|\b[Pfp]\([^)]*)$',content) and MATH.search(content):finding(holds,'EMPTY_INTRODUCED_MATH_ENDPOINT',stack.start(),m.end(),{'shape':'mathematical_rhs_or_parenthesis_endpoint_absent','replacement_inferred':False})
    stack=None
 if stack is not None:
  tail=mask[stack.end():min(len(mask),stack.end()+1024)]
  finding(holds if MATH.search(tail) else signals,'UNBALANCED_LATEX_WRAPPER' if MATH.search(tail) else 'AMBIGUOUS_LITERAL_LATEX_TOKEN',stack.start(),min(len(mask),stack.end()+1024),{'shape':'unclosed_open','replacement_inferred':False})
 for m in re.finditer(r'(?mi)\b(?:The|This)\s+(?:equation|formula)\s+(?:has|takes)\s+the\s+form\s*:\s*\n[ \t]*where\b[^\n]*',mask):finding(holds,'EMPTY_INTRODUCED_EQUATION_SLOT',m.start(),m.end(),{'introduced_object_absent_before_where_clause':True,'replacement_inferred':False})
 for m in HEADING.finditer(mask):
  finding(signals,'ASSESSMENT_DEPENDENCY_REVIEW',m.start(),m.end(),{'automatic_missing_content_claim':False})
  tail=mask[m.end():];consumed=0;count=0
  while True:
   rest=tail[consumed:];ws=len(rest)-len(rest.lstrip());consumed+=ws
   match=BOILERPLATE_RE.match(tail,consumed)
   if match is None:break
   consumed=match.end();count+=1
  if count and not tail[consumed:].strip() and re.search(r'(?i)(?:complete the test now|Answer the question\(s\) below|Use this quiz)',tail):finding(holds,'EMPTY_REQUIRED_ASSESSMENT_SLOT',m.start(),len(mask),{'only_recognized_assessment_instructions_remain':True,'recognized_sentences':count,'unknown_content_prevents_rule':True,'extraction_cause_unknown':True})
 for m in re.finditer(r'(?i)(?:as you can see from[^\n.!?]{0,100}(?:these tables|the (?:figure|chart|diagram))|(?:numbers|ages|values) that label[^\n.!?]{0,100}(?:Figure\s+\d+|diagram)|(?:click on each|consider the headshots)[^\n.!?]{0,120})',mask):finding(signals,'NAMED_VISUAL_DEPENDENCY_REVIEW',m.start(),m.end(),{'automatic_hold':False,'native_or_whole_unit_dependency_review_needed':True,'presence_or_absence_not_proven':True})
 result={'status':'SYNTHETIC_ONLY_STRUCTURAL_REPAIR_V2_NOT_SOURCE_ACCEPTANCE','source_SHA256':sha(raw),'source_UTF8_bytes':len(raw),'source_characters':len(text),'prior_v1':prior,'delta_representation_review_holds':holds,'delta_review_only_signals':signals,'decision':'HOLD_REPRESENTATION_REVIEW' if prior['reasons'] or holds else 'RAW_CANDIDATE_UNCHANGED_PENDING_ALL_GATES','derivative_SHA256':sha(raw),'raw_unchanged':True,'omitted_source_bytes':0,'major_corruption_or_quality_verdict_assigned':False,'rights_generation_family_status':'UNASSESSED_SEPARATE_COMPONENT_INTERFACE','new_admissions':0}
 require(len((json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n').encode())<=MAX_RECEIPT,'receipt_cap_no_truncation')
 return result
