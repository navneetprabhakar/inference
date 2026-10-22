"""Conservative WHOLE-RAW-UNIT candidate filter; source-bound optional components.
These rules identify representation/role REVIEW HOLDS, never bad-English proof.
"""
import hashlib,json,re
MAX_BYTES=2196000
RULES={
'REPEATED_RESOURCE_CATALOG_FIELDS':'At least two complete resource-description field cycles (license then format), no claim that resource descriptions are bad prose.',
'LINKED_SOURCE_INDEX_WITH_NO_MAIN_EXPOSITION':'After the first nonempty title line, every nonempty line is an explicit Primary/Secondary Source record with a URL. Main explanatory paragraphs prevent this rule.',
'LINE_COMMENT_CONTAINS_FLATTENED_PROGRAM':'A physical // comment line also contains class declaration + static method declaration + statements: code swallowed by lost newlines. Explanatory prose/code examples alone are not excluded.',
'EMPTY_PAIRED_LABELS':'Only explicit both-surfaces enumeration followed by spaced empty labels ( and ) has a representation hold. Unqualified conjunction tokens are context only.',
'UNBOUND_MATH_EXERCISE_INTRO':'A standalone For the relation/function/equation/matrix/expression introducer directly followed by a labeled subquestion has no displayed object in between.',
'INTRODUCED_VALUE_ABSENT_AT_DISCOURSE_BOUNDARY':'An explicit estimated-to-be-about predicate ends before a However/Therefore/Thus boundary without its announced value; no numerical repair.',
'DANGLING_MEASURED_VALUE_CLAUSE':'A measured/given/calculated/defined quantity clause ends in dangling and. or such that.; representation review, not inferred truth.',
'EMPTY_MATH_ELEMENT':'An explicit empty latex/MathJax display has no mathematical content; no inferred replacement.'}
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,reason):
 if not ok:raise ValueError(reason)
def offsets(text):
 out=[0];pos=0
 for c in text:pos+=len(c.encode('utf8'));out.append(pos)
 return out

def filter_raw(text):
 require(isinstance(text,str),'text_type');raw=text.encode();require(len(raw)<=MAX_BYTES,'raw_text_cap')
 bs=offsets(text);reasons=[];diagnostics=[]
 def finding(target,reason,a,b,detail):
  target.append({'reason':reason,'char_start':a,'char_end':b,'byte_start':bs[a],'byte_end':bs[b],'source_span_SHA256':sha(raw[bs[a]:bs[b]]),'detail':detail})
 lines=[(m.start(),m.end(),m.group()) for m in re.finditer(r'[^\n]+',text) if m.group().strip()]
 # A field cycle must contain both anchored metadata fields; no title/subject bans.
 licenses=list(re.finditer(r'(?mi)^licen[cs]e\s*:\s*\S[^\n]*$',text))
 cycles=[]
 for i,m in enumerate(licenses):
  end=licenses[i+1].start() if i+1<len(licenses) else len(text)
  fmt=re.search(r'(?mi)^formats?\s*:\s*\S[^\n]*$',text[m.end():end])
  if fmt:cycles.append((m.start(),m.end()+fmt.end()))
 if len(cycles)>=2 and not re.search(r'[a-z][.!?](?:\s|$)',text[:cycles[0][0]]):
  finding(reasons,'REPEATED_RESOURCE_CATALOG_FIELDS',cycles[0][0],cycles[-1][1],{'complete_field_cycles':len(cycles),'requires_component_review_not_topic_rejection':True})
 ref=re.compile(r'(?i)^(?:primary|secondary) source(?:\s+[^:]+)?\s*:\s*.+https?://\S+')
 if len(lines)>=3 and not re.search(r'[.!?:]\s*$',lines[0][2]) and all(ref.fullmatch(s.strip()) for _,_,s in lines[1:]):
  finding(reasons,'LINKED_SOURCE_INDEX_WITH_NO_MAIN_EXPOSITION',lines[0][0],lines[-1][1],{'explicit_source_records':len(lines)-1,'source_heading_preserved':True})
 for a,b,s in lines:
  if re.match(r'^\s*//',s) and re.search(r'\bclass\s+[A-Za-z_]\w*\s*\{',s) and re.search(r'\bstatic\s+(?:void|[A-Za-z_]\w*)\s+\w+\s*\(',s) and ';' in s:
   finding(reasons,'LINE_COMMENT_CONTAINS_FLATTENED_PROGRAM',a,b,{'syntax':'line_comment_then_class_static_method_and_statement','no_code_repair_attempted':True})
 for m in re.finditer(r'\(\s*(?:and|or|,)\s*\)',text):
  explicit=re.search(r'(?i)\bboth\s+surfaces\s*$',text[max(0,m.start()-200):m.start()]) and re.fullmatch(r'\(\s+and\s+\)',m.group())
  if explicit:finding(reasons,'EMPTY_PAIRED_LABELS',m.start(),m.end(),{'explicit_context':'both surfaces with spaced empty labels','not_conjunction_discussion_generalization':True})
  else:finding(diagnostics,'AMBIGUOUS_CONJUNCTION_OR_LABEL_TOKEN',m.start(),m.end(),{'automatic_hold':False,'source_context_required':True})
 for m in re.finditer(r'(?is)\[latex\]\s*\[/latex\]|\\\[\s*\\\]',text):finding(reasons,'EMPTY_MATH_ELEMENT',m.start(),m.end(),{'replacement_inferred':False})
 # Explicit introduced-object gaps; no arbitrary sentence length/figure count gate.
 for m in re.finditer(r'(?m)^For the (?:relation|function|equation|matrix|expression)\s*\n(?=[ⓐⓑⓒ]|[a-z][.)]\s)',text):
  finding(reasons,'UNBOUND_MATH_EXERCISE_INTRO',m.start(),m.end(),{'announced_object_absent_before_subquestion':True,'replacement_inferred':False})
 for m in re.finditer(r'(?i)estimated to be about[ \t]*\n[ \t]*(?=However\b|Therefore\b|Thus\b)',text):
  finding(reasons,'INTRODUCED_VALUE_ABSENT_AT_DISCOURSE_BOUNDARY',m.start(),m.end(),{'predicate_value_gap_not_source_fact_correction':True})
 for m in re.finditer(r'[^\n.!?]+[.!?]?',text):
  if re.search(r'\b(?:is measured|is given|is calculated|is defined)\b',m.group()) and re.search(r'\band[.]$',m.group()):
   finding(reasons,'DANGLING_MEASURED_VALUE_CLAUSE',m.start(),m.end(),{'announced_quantity_followed_by_dangling_conjunction':True,'uncertain_cause':True})
 # Context signals NEVER independently exclude, rewrite, or prove media is required.
 cues=[('FIGURE_REFERENCE_CONTEXT',r'\b(?:Figure|Fig\.)\s*(?:\([^)\n]*\)|\d[\w.:-]*)?'),('SOURCE_MATH_MARKUP_PRESERVED',r'\[/?latex\]|\\\(|\\\['),('POSSIBLE_COMPONENT_HEADING',r'(?mi)^(?:glossary|references|works cited|image attributions|attributions|further reading|key terms|summary)\s*$')]
 for name,pattern in cues:
  for m in re.finditer(pattern,text):finding(diagnostics,name,m.start(),m.end(),{'automatic_hold':False,'automatic_component_boundary':False})
 return {'policy_status':'DEVELOPMENT_GENERIC_RAW_UNIT_FILTER_NOT_ACCEPTANCE','source_SHA256':sha(raw),'source_UTF8_bytes':len(raw),'source_characters':len(text),'decision':'HOLD_STRUCTURAL_REPRESENTATION_REVIEW' if reasons else 'RAW_CANDIDATE_UNCHANGED_PENDING_ALL_OTHER_GATES','reasons':reasons,'context_only_diagnostics':diagnostics,'raw_unchanged':True,'derivative_SHA256':sha(raw),'omitted_source_bytes':0,'English_quality_or_factual_truth_proven':False,'rights_family_leakage_cleared':False}

ROLES={'MAIN_PROSE','ATTRIBUTION','GLOSSARY','REFERENCE','RESOURCE_INDEX','CODE','MATH','FIGURE','UNKNOWN'}
UNITS={'CHAPTER','SECTION','LEAD','STANDALONE_ARTICLE'}
def separate_components(text,proof):
 """No automatic raw-string cropping. Requires verified native/projection mapping.
 Complete partition is retained, including nonprose. A derivative is ONE complete
 authored main component; never a concatenation of sentence crops.
 """
 raw=text.encode();require(len(raw)<=MAX_BYTES,'raw_text_cap')
 if proof is None:return {'status':'NO_COMPONENT_TRANSFORMATION_NATIVE_BOUNDARIES_UNAVAILABLE','source_SHA256':sha(raw),'derivatives':[],'original_retained':True}
 require(proof['source_SHA256']==sha(raw) and proof['native_projection_whole_text_verified'] is True,'native_source_projection_binding')
 for name in ['native_artifact_SHA256','projection_policy_SHA256','independent_boundary_review_SHA256']:
  v=proof[name];require(isinstance(v,str) and len(v)==64 and bytes.fromhex(v).hex()==v,'native_proof_hash')
 bs=offsets(text);parts=[];position=0;ids=set()
 for c in proof['components']:
  a,b=c['char_start'],c['char_end'];require(type(a)==int and type(b)==int and a==position and a<b<=len(text),'complete_contiguous_component_partition');position=b
  require(c['role'] in ROLES and c['id'] not in ids,'component_role_unique_id');ids.add(c['id'])
  require(isinstance(c['native_locator'],str) and c['native_locator'],'native_component_locator')
  body=text[a:b];require(sha(body.encode())==c['source_span_SHA256'],'exact_native_component_hash')
  parts.append({**c,'byte_start':bs[a],'byte_end':bs[b],'text':body})
 require(position==len(text),'whole_source_partition')
 derivatives=[]
 for p in parts:
  if p['role']!='MAIN_PROSE':continue
  require(p['authored_unit_kind'] in UNITS,'no_sentence_paragraph_crops')
  deps=p['dependencies'];require(isinstance(deps,list) and all(d['component_id'] in ids for d in deps),'resolved_dependency_ids')
  missing=[d for d in deps if d['required'] and not d['available']]
  if missing or p['semantic_independence']!='VERIFIED_WHOLE_AUTHORED_UNIT':continue
  # Keep references/attributions accessible; no language/rights/admission clearance.
  derivatives.append({'component_id':p['id'],'text':p['text'],'SHA256':p['source_span_SHA256'],'char_start':p['char_start'],'char_end':p['char_end'],'byte_start':p['byte_start'],'byte_end':p['byte_end'],'dependency_ids':[d['component_id'] for d in deps],'attribution_component_ids':[q['id'] for q in parts if q['role']=='ATTRIBUTION'],'admitted':False})
 require(''.join(p['text'] for p in parts)==text,'exact_inverse')
 return {'status':'LOSSLESS_COMPONENT_PARTITION_NOT_ADMISSION','source_SHA256':sha(raw),'components':parts,'derivatives':derivatives,'exact_inverse':True,'all_original_components_preserved':True,'native_proof':{k:v for k,v in proof.items() if k!='components'}}
