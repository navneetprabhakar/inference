"""Conservative semantic gates on exact source-bound component diagnostics.
No template expansion, convenience stripping, corpus/quality/admission decision.
"""
import hashlib,re,importlib,pathlib
H=lambda s:hashlib.sha256(s.encode('utf8')).hexdigest()
# Explicit bibliographic schema; unknown keys are held, never thrown away.
BIB_FIELDS=frozenset(('title','url','chapter','chapter-url','work','website','publisher','publication-place','location','place','date','year','orig-year','publication-date','access-date','archive-url','archive-date','url-status','doi','isbn','issn','oclc','jstor','pmid','pmc','bibcode','volume','issue','number','edition','page','pages','at','language','format','type','series','agency','newspaper','journal','magazine','encyclopedia','author','authors','last','first','editor','editors','editor-last','editor-first','display-authors','display-editors'))
CITE_NAMES=frozenset(('cite web','cite news','cite book','cite journal','cite encyclopedia','cite magazine','cite report','cite conference','citation','cite av media'))
SEMANTIC_FIELDS=frozenset(('quote','quotation','transcript','lay-summary','postscript'))
def bib_key(key):
 return key in BIB_FIELDS or bool(re.fullmatch(r'(?:author|last|first|editor|editor-last|editor-first)(?:[1-9]|[1-9][0-9]|1[01][0-9]|12[0-8])',key))
def citation_content(raw,parser,literal,group=''):
 """Classification only: arbitrary source words never establish cite-only status."""
 reasons=[];inventory=[];count=0
 if group:reasons.append('reference_group_semantics_unverified')
 code=parser.parse(raw)
 if str(code)!=raw:raise ValueError('citation_exact_AST_roundtrip')
 for node in code.nodes:
  kind=type(node).__name__;item={'type':kind,'raw':str(node),'raw_SHA256':H(str(node))};inventory.append(item)
  if kind=='Comment' or kind=='Text' and not str(node).strip():continue
  if kind!='Template':reasons.append('explanatory_or_unclassified_reference_content');continue
  if any(type(v).__name__!='Text' for v in node.name.nodes):reasons.append('nonliteral_citation_template_name');continue
  name=str(node.name).strip().replace('_',' ').lower()
  if name not in CITE_NAMES:reasons.append('unsupported_reference_template_semantics');continue
  count+=1;seen=set();has_identifier=False
  if len(node.params)>128:reasons.append('citation_parameter128cap')
  for p in node.params:
   if any(type(v).__name__!='Text' for v in p.name.nodes):reasons.append('nonliteral_bibliographic_key');continue
   key=str(p.name).strip()
   if not key or key in seen:reasons.append('duplicate_or_empty_bibliographic_key')
   seen.add(key)
   if key in SEMANTIC_FIELDS:reasons.append('semantic_quote_or_explanatory_citation_field:'+key)
   elif not bib_key(key):reasons.append('unknown_bibliographic_field_semantics:'+key)
   if key in ('title','url','doi','isbn','issn','oclc','jstor','pmid','pmc') and str(p.value).strip():has_identifier=True
   for v in p.value.nodes:
    if type(v).__name__ not in ('Text','HTMLEntity','ExternalLink'):reasons.append('unresolved_semantic_bibliographic_value:'+type(v).__name__);continue
    try:literal.project(parser.wikicode.Wikicode([v]))
    except literal.Hold as e:reasons.append('unresolved_bibliographic_literal:'+str(e))
  if not has_identifier:reasons.append('bibliographic_identity_missing')
 if not count:reasons.append('no_schema_bound_bibliographic_template')
 return {'class':'CITATION_ONLY_SCHEMA_BOUND_RAW_COMPANION' if not reasons else 'EXPLANATORY_OR_UNRESOLVED_REFERENCE_DEPENDENCY','semantic_holds':sorted(set(reasons)),'content_AST_inventory':inventory,'source_raw_SHA256':H(raw),'all_source_content_preserved':True,'not_rendered_or_factchecked':True}

def sections(source,parser,expected_regions=None):
 import policy_core as literal,reference_core as reference,rules,integrated_core as integrated
 result=integrated.develop_page(source,parser,literal,reference,rules,expected_regions)
 refs=result['reference_resolution'];by_section={s['section_ordinal']:set() for s in result['sections']};classifications=[]
 for companion in refs['citation_companions']:
  defs=[];issues=set(companion.get('component_holds',[]))
  for d in companion['definitions']:
   content=d['content'];raw=content['raw'];bound=citation_content(raw,parser,literal,companion['group']);issues.update(bound['semantic_holds']);defs.append({'occurrence_index':d['occurrence_index'],'source_char_span':content['source_char_span'],'source_byte_span':content['source_byte_span'],'classification':bound})
  affected=sorted({refs['ref_occurrences'][n]['section_ordinal'] for n in companion['occurrence_indices']})
  for sid in affected:by_section[sid].update(issues)
  classifications.append({'citation_ID':companion['citation_ID'],'marker':companion['marker'],'affected_complete_sections':affected,'definitions':defs,'semantic_holds':sorted(issues),'reference_binding_holds_preserved':True})
 # A companion class alone never overrides a classifier schema refusal.
 # Preserve prior integrated output as ancestry; suppress unsupported projections.
 for component in result['exact_raw_metadata_companions']:
  parsed=parser.parse(component['raw'])
  if len(parsed.nodes)==1 and type(parsed.nodes[0]).__name__=='Template':
   node=parsed.nodes[0];params=integrated.literal_parameters(node)
   rule=rules.template_rule(str(node.name).strip(),params or [],True)
   if params is None or rule['action'].startswith('HOLD_'):
    by_section[component['section_ordinal']].add('standalone_component_schema_refusal')
 # SFN bibliography fields can also carry explanatory/unknown/nested semantics.
 # Their definition context remains original and never projected as body prose.
 short=result['shortnote_resolution'];bib_by={b['bibliography_ID']:b for b in short['bibliographic_companions']};bibclass={}
 for bid,b in bib_by.items():bibclass[bid]=citation_content(b['raw'],parser,literal)
 for occurrence in short['short_footnote_occurrences']:
  bid=occurrence.get('bibliography_ID')
  if bid in bibclass:by_section[occurrence['section_ordinal']].update(bibclass[bid]['semantic_holds'])
 for s in result['sections']:
  k=s['section_ordinal'];new=sorted(by_section[k]);oldpreview=s['provisional_prose_preview']
  s['reference_content_semantic_holds']=new
  s['component_independence_holds']=sorted(set(s['semantic_companion_holds'])|set(new))
  s['standalone_semantic_independence']='DEPENDENCY_HELD' if s['component_independence_holds'] else 'STRUCTURAL_ONLY_QUALITY_CONTEXT_FACTS_RIGHTS_UNREVIEWED'
  s['structural_preview_before_semantic_gate_SHA256']=H(oldpreview) if oldpreview is not None else None
  if new:
   s['prose_structural_holds']=sorted(set(s['prose_structural_holds'])|{'semantic_reference_dependency:'+h for h in new});s['provisional_prose_preview']=None;s['preview_SHA256']=None;s['status']='HELD_COMPLETE_REGION_SEMANTIC_REFERENCE_DEPENDENCY_NO_PARTIAL_PREVIEW'
  s['no_admission']=True
 if ''.join(x['raw'] for x in result['sections'])!=source:raise ValueError('whole_source_partition_inverse')
 result.update({'exact_roundtrip':True,'all_source_bytes_partitioned_once':True,'reference_content_classifications':classifications,'shortnote_bibliographic_classifications':bibclass,'new_semantic_gate_does_not_clear_prior_holds':True,'standalone_components_remain_full_raw_semantic_companions':True,'wholepage_eligibility_or_prose_quality_asserted':False})
 return result
