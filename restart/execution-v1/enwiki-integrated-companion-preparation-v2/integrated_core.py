"""Finite development integration; no corpus eligibility or fact/rights clearance."""
import hashlib,json,re
H=lambda s:hashlib.sha256(s.encode('utf8')).hexdigest()

def literal_parameters(node):
 params=[];seen=set()
 for p in node.params:
  if any(type(n).__name__!='Text' for n in p.name.nodes):return None
  name=str(p.name).strip()
  if name in seen:return None
  seen.add(name)
  params.append((name,str(p.value)))
 return params

def whole_line(source,a,b):
 return not source[source.rfind('\n',0,a)+1:a].strip() and not source[b:source.find('\n',b) if '\n' in source[b:] else len(source)].strip()

def apply_ops(raw,start,ops):
 out=[];cursor=0
 for op in sorted(ops,key=lambda o:o['source_char_span']):
  a,b=op['source_char_span'];a-=start;b-=start
  if a<cursor or raw[a:b]!=op['raw'] or H(raw[a:b])!=op['raw_SHA256']:raise ValueError('operation_nonoverlap_exact_original_preimage')
  out.extend([raw[cursor:a],op['replacement']]);cursor=b
 out.append(raw[cursor:]);return ''.join(out)

def invert_ops(transformed,start,ops):
 out=[];cursor=0;delta=0
 for op in sorted(ops,key=lambda o:o['source_char_span']):
  a,b=op['source_char_span'];position=a-start+delta;replacement=op['replacement']
  if position<cursor or transformed[position:position+len(replacement)]!=replacement:raise ValueError('transformed_operation_inverse')
  out.extend([transformed[cursor:position],op['raw']]);cursor=position+len(replacement);delta+=len(replacement)-(b-a)
 out.append(transformed[cursor:]);return ''.join(out)

def namespace_scope(target):
 # Only directly observed namespace names plus the explicit conservative Image
 # alias hold. Case/space/underscore recognition is not an expansion of the map.
 stripped=target.strip();escaped=stripped.startswith(':');candidate=stripped[1:].lstrip() if escaped else stripped
 prefix,sep,remainder=candidate.partition(':')
 known={'category':'Category','file':'File','module':'Module','image':'Image'}
 canonical=known.get(prefix.replace('_',' ').strip().casefold()) if sep else None
 if canonical is None:
  return {'hold':'leading_colon_display_requires_explicit_rule','safe_standalone_companion':False} if escaped else None
 ambiguous=escaped or stripped!=target or prefix.casefold()!=canonical.casefold() or remainder!=remainder.strip()
 if canonical=='Image':return {'canonical_prefix':canonical,'hold':'media_prefix_alias_unverified','safe_standalone_companion':False}
 return {'canonical_prefix':canonical,'hold':'known_namespace_escape_or_spacing_requires_explicit_rule' if ambiguous else 'known_native_namespace_requires_typed_companion:'+canonical,'safe_standalone_companion':not ambiguous}

def render(code,parser,literal,rules):
 out=[]
 for node in code.nodes:
  kind=type(node).__name__
  if kind=='Wikilink':
   target=str(node.title)
   if any(type(n).__name__!='Text' for n in node.title.nodes) or re.search(r'[{}\[\]<>|]|&(?:#[^\s&<>;]*;?|[A-Za-z][A-Za-z0-9]*;)',target) or re.search(r'&(amp|lt|gt|quot|apos|nbsp)(?![A-Za-z0-9;])',target):raise literal.Hold('unsupported_internal_title_AST')
   if not target.strip() or target.startswith('#'):raise literal.Hold('empty_or_fragment_title')
   scope=namespace_scope(target)
   if scope is not None:raise literal.Hold(scope['hold'])
   if node.text is None:
    if any(c in target for c in '_#|'):raise literal.Hold('implicit_link_display_needs_rule')
    out.append(target)
   else:
    if not str(node.text).strip():raise literal.Hold('empty_piped_display')
    out.append(render(node.text,parser,literal,rules))
  elif kind=='Tag' and str(node.tag)=='span':
   attrs=[]
   for a in node.attributes:
    if a.value is None or any(type(n).__name__!='Text' for n in a.name.nodes) or any(type(n).__name__!='Text' for n in a.value.nodes):raise literal.Hold('unsupported_span_attribute_AST')
    attrs.append((str(a.name),str(a.value)))
   if not rules.span_rule(attrs)['action'].startswith('PROPOSE_TRANSPARENT') or node.self_closing or node.implicit or node.invalid or node.wiki_markup or str(node.closing_tag)!='span':raise literal.Hold('unsupported_span_wrapper')
   if node.contents.filter_headings(recursive=True):raise literal.Hold('span_crosses_heading')
   out.append(render(node.contents,parser,literal,rules))
  elif kind=='Tag' and str(node.tag) in ('b','i','em','strong') and not node.attributes and not node.self_closing:
   if node.invalid or node.implicit or str(node.closing_tag)!=str(node.tag):raise literal.Hold('invalid_formatting_wrapper')
   if node.contents.filter_headings(recursive=True):raise literal.Hold('formatting_crosses_heading')
   out.append(render(node.contents,parser,literal,rules))
  else:out.append(literal.project(parser.wikicode.Wikicode([node])))
 return ''.join(out)

def develop_page(source,parser,literal,reference,rules,expected_regions=None):
 if len(source.encode())>120000:raise ValueError('finite120000pagecap')
 ref=reference.resolve_page(source,parser,expected_regions,literal)
 code=parser.parse(source)
 if str(code)!=source:raise ValueError('exact_source_AST_inverse')
 nodes=[];cursor=0;metadata=[];ops=[];wrapper_spans=[]
 for i,node in enumerate(code.nodes):
  raw=str(node);a=cursor;b=a+len(raw);cursor=b
  sid=next(k for k,(x,y) in enumerate(ref['complete_section_partition']) if x<=a and b<=y)
  bound={'source_char_span':[a,b],'source_byte_span':[len(source[:a].encode()),len(source[:b].encode())],'raw':raw,'raw_SHA256':H(raw),'top_node_path':[i],'section_ordinal':sid}
  nodes.append({**bound,'type':type(node).__name__})
  if type(node).__name__=='Template':
   params=literal_parameters(node);name=str(node.name).strip()
   if any(type(n).__name__!='Text' for n in node.name.nodes) or params is None:continue
   rule=rules.template_rule(name,params,whole_line(source,a,b));category=rule['class'];allowed=False;unresolved=[]
   if category=='maintenance_metadata' and rule['prose_may_proceed_after_review']:
    # Date metadata values cannot hide semantic templates or malformed entities.
    try:
     for p in node.params:literal.project(p.value)
     allowed=True
    except literal.Hold:pass
   elif whole_line(source,a,b) and category in ('semantic_page_metadata','sort_metadata','navigation_or_taxonomy_with_semantic_labels','citation_style_metadata'):
    allowed=True
    if category!='sort_metadata':unresolved=['unrendered_'+category+'_companion_independence_review_required']
   if allowed:
    ident=H(ref['source_SHA256']+'\x00metadata\x00'+str(a));metadata.append({**bound,'companion_ID':ident,'name_literal':name,'class':category,'raw_parameters':[{'raw':str(p),'name_raw':str(p.name),'value_raw':str(p.value),'showkey':bool(p.showkey)} for p in node.params],'component_holds':unresolved,'no_values_discarded':True,'not_rendered_template_expansion':True})
    ops.append({**bound,'replacement':'','kind':'standalone_metadata_to_exact_raw_companion','companion_ID':ident})
  if type(node).__name__=='Wikilink' and whole_line(source,a,b):
   title=str(node.title);scope=namespace_scope(title);prefix=scope.get('canonical_prefix') if scope else None
   # Only namespace prefixes directly observed in pinned native20 metadata.
   if prefix in {'Category','File'} and scope['safe_standalone_companion'] and all(type(n).__name__=='Text' for n in node.title.nodes) and not re.search(r'[{}\[\]<>|]|&(?:#[^\s&<>;]*;?|[A-Za-z][A-Za-z0-9]*;)',title) and not re.search(r'&(amp|lt|gt|quot|apos|nbsp)(?![A-Za-z0-9;])',title):
    ident=H(ref['source_SHA256']+'\x00namespace-companion\x00'+str(a));category='category_taxonomy_metadata' if prefix=='Category' else 'semantic_media'
    metadata.append({**bound,'companion_ID':ident,'name_literal':prefix,'class':category,'raw_link_target':title,'raw_link_display_or_options':str(node.text) if node.text is not None else None,'raw_parameters':[],'component_holds':['unrendered_'+category+'_companion_independence_review_required'],'no_values_discarded':True,'not_rendered_template_expansion':True})
    ops.append({**bound,'replacement':'','kind':'standalone_namespace_node_to_complete_raw_companion','companion_ID':ident})
  # Rendering spans stay in source; inventory exact wrapper preimages for future QA.
  if type(node).__name__=='Tag' and str(node.tag)=='span':wrapper_spans.append(bound)
 if cursor!=len(source) or ''.join(n['raw'] for n in nodes)!=source:raise ValueError('all_topnodes_inverse')
 sections=[]
 for r in ref['source_partition']:
  k=r['section_ordinal'];a,b=r['source_char_span'];regionops=[o for o in ops if o['section_ordinal']==k]
  regionops += [{**o,'replacement':o['replacement_marker'],'kind':'validated_page_local_reference_marker'} for o in r['marker_operations']]
  # Exact citation/reference holds always win; never launder unknown contexts.
  holds=list(r['holds']);preview=None;transformed=None
  if not holds:
   transformed=apply_ops(r['raw'],a,regionops)
   if invert_ops(transformed,a,regionops)!=r['raw']:raise ValueError('full_operation_inverse')
   try:preview=render(parser.parse(transformed),parser,literal,rules)
   except literal.Hold as e:holds.append(str(e))
  components=[m for m in metadata if m['section_ordinal']==k];componentholds=sorted({h for m in components for h in m['component_holds']})
  sections.append({'section_ordinal':k,'source_char_span':r['source_char_span'],'source_byte_span':r['source_byte_span'],'raw':r['raw'],'raw_SHA256':r['raw_SHA256'],'source_operations':regionops,'operations_applied_to_provisional_markup':not bool(r['holds']),'reference_holds':r['holds'],'prose_structural_holds':holds,'semantic_companion_holds':componentholds,'provisional_prose_preview':preview,'preview_SHA256':H(preview) if preview is not None else None,'transformed_markup_SHA256':H(transformed) if transformed is not None else None,'companion_IDs':[m['companion_ID'] for m in components],'status':'PROVISIONAL_PROSE_WITH_COMPLETE_COMPANIONS_PENDING_REVIEW' if preview is not None else 'HELD_COMPLETE_REGION_NO_PARTIAL_PREVIEW','prior_source_rights_quality_language_leakage_gates_unchanged':True,'no_admission':True})
 if ''.join(r['raw'] for r in sections)!=source:raise ValueError('full_complete_region_inverse')
 return {'source_SHA256':H(source),'complete_section_partition':ref['complete_section_partition'],'sections':sections,'all_original_top_nodes':nodes,'exact_raw_metadata_companions':metadata,'reference_resolution':ref,'reference_limitations':{'opaque_context_count':len(ref['opaque_reference_contexts']),'opaque_page_guard_conservative_not_assertion_of_missing_refs':bool(ref['opaque_reference_contexts']),'observed_definition_occurrences':sum(o['kind']=='definition' for o in ref['ref_occurrences']),'all_original_reference_hold_reasons_preserved':True},'original_top_level_span_wrappers':wrapper_spans,'namespace_policy_scope':'Category14/File6/Module828 observed in pinnednative20; knownprefixcasefoldrecognized, spacing/underscore/leadingcolonvariantsheld; Image conservativeunverifiedalias; otherliteralbooktitlecolonsretained','all_source_bytes_and_semantic_companion_values_retained':True,'prior_structural_holds_not_admission_gates_cleared':False,'new_admitted_documents':0}
