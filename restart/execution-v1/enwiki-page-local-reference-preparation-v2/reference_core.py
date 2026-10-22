"""Page-local ref binding diagnostics. No citation expansion or native runner.
Only exact top-level refs/validated attribute-free inline formatting containers.
Unsupported containers/list-definitions remain conservative holds, not omissions.
"""
import hashlib,json,re

def H(s):return hashlib.sha256(s.encode('utf8')).hexdigest()
class RefHold(Exception):pass

def spans(source,parser):
 code=parser.parse(source)
 if str(code)!=source:raise ValueError('exact_AST_roundtrip')
 regions=[];start=0;pos=0;has=False
 for node in code.nodes:
  if type(node).__name__=='Heading' and node.level==2 and has:regions.append([start,pos]);start=pos
  pos+=len(str(node));has=True
 if has:regions.append([start,pos])
 if pos!=len(source):raise ValueError('partition_end')
 return code,regions

def literal_attrs(node):
 out={}
 for a in node.attributes:
  name=str(a.name)
  if name not in ('name','group') or name in out or a.value is None or any(type(x).__name__!='Text' for x in a.name.nodes) or any(type(x).__name__!='Text' for x in a.value.nodes):raise RefHold('unsupported_duplicate_or_nonliteral_ref_attribute')
  value=str(a.value)
  if value!=value.strip() or not (re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.:/\-]{0,127}',value) or (name=='name' and a.quotes in ('"',"'") and re.fullmatch(r':[0-9]{1,127}',value))) or (name=='name' and value.isdecimal()):raise RefHold('unsupported_empty_numeric_or_ambiguous_ref_attribute_value')
  out[name]=value
 return out

def content_parts(node):
 raw=str(node)
 if node.invalid or node.implicit or node.self_closing:raise RefHold('unsupported_implicit_invalid_container')
 if node.wiki_markup:prefix=node.wiki_markup+''.join(map(str,node.attributes))+(node.padding or '')+(node.wiki_style_separator or '');suffix=node.closing_wiki_markup or ''
 else:prefix='<'+str(node.tag)+''.join(map(str,node.attributes))+node.padding+'>';suffix='</'+str(node.closing_tag)+'>'
 if raw!=prefix+str(node.contents)+suffix:raise RefHold('container_exact_serialization_not_proven')
 return prefix,str(node.contents),suffix

def ref_nodes(node):
 for child in node.__children__():
  for tag in child.ifilter_tags(recursive=True):
   if str(tag.tag).lower()=='ref':yield tag

CITE_NAMES={'cite web','cite news','cite book','cite journal','cite encyclopedia','cite magazine','cite report','cite conference','citation'}
def citation_fields(code,literal_policy,parser):
 """Keep raw allbytes; fields are source records, not rendered Cite output."""
 fields=[]
 for n in code.nodes:
  kind=type(n).__name__
  if kind=='Comment':continue # original raw citation remains authoritative
  if kind in ('Text','HTMLEntity'):
   try:literal_policy.project(parser.wikicode.Wikicode([n]))
   except literal_policy.Hold as e:raise RefHold('unresolved_citation_literal:'+str(e))
   continue
  if kind=='ExternalLink':
   try:literal_policy.project(parser.wikicode.Wikicode([n]))
   except literal_policy.Hold as e:raise RefHold('unresolved_citation_literal:'+str(e))
   continue
  if kind!='Template' or any(type(x).__name__!='Text' for x in n.name.nodes) or str(n.name).strip().replace('_',' ').lower() not in CITE_NAMES:raise RefHold('unsupported_citation_construct_requires_review')
  if len(n.params)>128:raise RefHold('citation_parameter_cap')
  params=[];names=set()
  for p in n.params:
   if any(type(x).__name__!='Text' for x in p.name.nodes):raise RefHold('nonliteral_citation_parameter_name')
   value_holds=[]
   for value_node in p.value.nodes:
    if type(value_node).__name__ in ('Text','HTMLEntity','ExternalLink'):
     try:literal_policy.project(parser.wikicode.Wikicode([value_node]))
     except literal_policy.Hold as e:raise RefHold('unresolved_citation_literal:'+str(e))
    else:value_holds.append('unrendered_nested_citation_value_component:'+type(value_node).__name__)
   key=str(p.name).strip()
   if key in names:raise RefHold('duplicate_citation_parameter_requires_review')
   names.add(key);params.append({'name_raw':key,'value_raw':str(p.value),'showkey':bool(p.showkey),'raw_parameter':str(p),'raw_SHA256':H(str(p)),'value_AST_types':[type(x).__name__ for x in p.value.nodes],'component_holds':value_holds})
  fields.append({'template_name_raw':str(n.name),'raw_template':str(n),'raw_SHA256':H(str(n)),'literal_parameters':[p for p in params if not p['component_holds']],'raw_parameters':params,'all_parameter_ASTs_literal':not any(p['component_holds'] for p in params),'component_holds':sorted({h for p in params for h in p['component_holds']}),'rendered_or_factchecked':False})
 return fields

def resolve_page(source,parser,expected_regions=None,literal_policy=None):
 if literal_policy is None or not callable(literal_policy.project) or not isinstance(literal_policy.Hold,type):raise ValueError('pinned_literal_policy_required')
 if len(source.encode())>120000:raise ValueError('finite_page120000byte_cap')
 code,regions=spans(source,parser)
 if expected_regions is not None and expected_regions!=regions:raise ValueError('saved_complete_section_partition_mismatch')
 if len(regions)>100:raise ValueError('section_cap')
 occurrence=[];holds={i:set() for i in range(len(regions))};opaque=[];sourcehash=H(source)
 def section_at(a,b):
  ids=[i for i,(x,y) in enumerate(regions) if x<=a and b<=y]
  if len(ids)!=1:raise RefHold('reference_crosses_complete_section_boundary')
  return ids[0]
 def binding(a,b):return {'source_char_span':[a,b],'source_byte_span':[len(source[:a].encode()),len(source[:b].encode())],'raw':source[a:b],'raw_SHA256':H(source[a:b])}
 def opaque_record(record,nested,inherited_group=None,inherited_group_unknown=False):
  identities=[];unknown=inherited_group_unknown
  for n in nested:
   entry={'raw':str(n),'SHA256':H(str(n))}
   try:
    attrs=literal_attrs(n);entry.update({'name':attrs.get('name'),'group':attrs.get('group',inherited_group if inherited_group is not None else ''),'exact_literal_identity_bound':True})
   except RefHold as e:entry.update({'exact_literal_identity_bound':False,'identity_hold':str(e)});unknown=True
   identities.append(entry)
  if not nested:unknown=True
  opaque.append({**record,'ref_raws_and_hashes':identities,'unbound_identity_global_guard':unknown})
 def visit(wikicode,start,path):
  if len(path)>64:raise ValueError('reference_container_depth64cap')
  cursor=start
  for i,n in enumerate(wikicode.nodes):
   raw=str(n);a=cursor;b=a+len(raw);cursor=b;assert source[a:b]==raw;sid=section_at(a,b) if len(regions)==1 or not (type(n).__name__=='Text' and not raw.strip()) else next((k for k,(x,y) in enumerate(regions) if x<=a<y),0)
   kind=type(n).__name__;tag=str(n.tag).lower() if kind=='Tag' else None
   if tag=='ref':
    if len(occurrence)>=1000:raise ValueError('ref1000cap')
    item={**binding(a,b),'AST_path':path+[i],'section_ordinal':sid,'name':None,'group':'','kind':None,'holds':[],'marker':None}
    try:
     if n.wiki_markup or n.invalid or n.implicit or str(n.tag)!='ref':raise RefHold('unsupported_ref_tag_form')
     attrs=literal_attrs(n);item['name']=attrs.get('name');item['group']=attrs.get('group','')
     if n.self_closing:
      if item['name'] is None:raise RefHold('unnamed_selfclosing_ref')
      item['kind']='reuse'
     else:
      pre,contents,suf=content_parts(n)
      if str(n.closing_tag)!='ref' or not contents.strip():raise RefHold('empty_or_mismatched_reference_definition')
      if list(ref_nodes(n)):raise RefHold('nested_reference_definition')
      item['kind']='definition';item['content']={**binding(a+len(pre),b-len(suf)),'raw_citation_fields':citation_fields(n.contents,literal_policy,parser),'raw_companion_only_not_rendered_bibliography':True}
    except RefHold as e:item['holds'].append(str(e));holds[sid].add(str(e))
    occurrence.append(item)
    if item['holds'] and (item['name'] is None or list(ref_nodes(n))):
     opaque_record({**binding(a,b),'section_ordinal':sid,'unknown_parent_type':'unbound_or_invalid_ref_occurrence'},[n]+list(ref_nodes(n)))
   elif kind=='Tag' and tag in ('b','i','em','strong') and not n.attributes and not n.self_closing:
    try:pre,contents,suf=content_parts(n);visit(n.contents,a+len(pre),path+[i,'contents'])
    except RefHold as e:holds[sid].add(str(e))
   elif kind=='Tag' and tag=='references':
    holds[sid].add('references_list_requires_separate_bound_adapter')
    nested=list(ref_nodes(n))
    if nested:
     try:
      parent_attrs=literal_attrs(n)
      if set(parent_attrs)-{'group'}:raise RefHold('unsupported_references_container_attributes')
      inherited=parent_attrs.get('group','');unbound_group=False
     except RefHold:inherited=None;unbound_group=True
     opaque_record({**binding(a,b),'section_ordinal':sid,'unknown_parent_type':kind},nested,inherited,unbound_group)
   elif kind=='Text' and re.search(r'<\s*/?\s*ref(?:erences)?(?:[\s/>]|$)',raw,re.I):
    holds[sid].add('unparsed_reference_shaped_Text');opaque_record({**binding(a,b),'section_ordinal':sid,'unknown_parent_type':'unparsed_reference_shaped_Text'},[])
   elif kind not in ('Text','Comment','HTMLEntity'):
    nested=list(ref_nodes(n))
    if nested:
     holds[sid].add('reference_inside_unknown_or_unsupported_context');opaque_record({**binding(a,b),'section_ordinal':sid,'unknown_parent_type':kind},nested)
  if cursor!=start+len(str(wikicode)):raise ValueError('container_cursor_inverse')
 # Top-level nodes can cross H2 regions only via plain whitespace Text; choose
 # region by start for irrelevant text and keep exact ref boundaries enforced.
 visit(code,0,[])
 buckets={}
 for i,o in enumerate(occurrence):
  key=(o['group'],o['name']) if o['name'] is not None else ('UNNAMED_OFFSET',o['source_char_span'][0])
  buckets.setdefault(key,[]).append(i)
 opaque_keys={(v['group'],v['name']) for parent in opaque for v in parent['ref_raws_and_hashes'] if v.get('exact_literal_identity_bound') and v['name'] is not None}
 global_opaque=any(x['unbound_identity_global_guard'] for x in opaque)
 group_counters={};companions=[];operations=[]
 for key,indices in buckets.items():
  items=[occurrence[i] for i in indices];defs=[x for x in items if x['kind']=='definition' and not x['holds']];bad={h for x in items for h in x['holds']}
  if not defs:bad.add('missing_valid_page_local_reference_definition')
  if len({d['content']['raw'] for d in defs})>1:bad.add('conflicting_page_local_named_reference_definitions')
  if global_opaque:bad.add('unbound_opaque_reference_identity_global_shadow_guard')
  elif key in opaque_keys:bad.add('opaque_reference_context_exact_group_name_shadow_guard')
  if bad:
   for x in items:x['holds']=sorted(set(x['holds'])|bad);holds[x['section_ordinal']].update(bad)
   continue
  # First-inline-use order will be assigned below; preserve every definition occurrence.
  companions.append({'citation_ID':H(sourcehash+'\x00'+str(items[0]['group'])+'\x00'+str(items[0]['name'])+'\x00'+str(items[0]['source_char_span'][0])),'group':items[0]['group'],'name':items[0]['name'],'occurrence_indices':indices,'definitions':[{'occurrence_index':occurrence.index(d),'content':d['content'],'full_ref':{k:d[k] for k in ['source_char_span','source_byte_span','raw','raw_SHA256']}} for d in defs],'component_holds':sorted({h for d in defs for field in d['content']['raw_citation_fields'] for h in field.get('component_holds',[])}),'all_raw_explanatory_text_and_qualifiers_retained':True,'citation_rendered':False,'fact_or_rights_certification':False})
 by_index={j:c for c in companions for j in c['occurrence_indices']};group_ids={'':0}
 for i,o in enumerate(occurrence):
  if i not in by_index:continue
  c=by_index[i];g=c['group']
  if 'marker' not in c:
   if g not in group_ids:group_ids[g]=len(group_ids)
   group_counters[g]=group_counters.get(g,0)+1;c['marker']='⟦ref:g'+str(group_ids[g])+':'+str(group_counters[g])+'⟧'
  o['marker']=c['marker']
  if c['marker'] in source:holds[o['section_ordinal']].add('reserved_reference_marker_collision')
  operations.append({**{k:o[k] for k in ['source_char_span','source_byte_span','raw','raw_SHA256','section_ordinal']},'replacement_marker':c['marker'],'citation_ID':c['citation_ID']})
 sections=[]
 for i,(a,b) in enumerate(regions):sections.append({'section_ordinal':i,**binding(a,b),'holds':sorted(holds[i]),'marker_operations':[] if holds[i] else [o for o in operations if o['section_ordinal']==i],'semantic_companion_holds':sorted({h for c in companions if any(occurrence[j]['section_ordinal']==i for j in c['occurrence_indices']) for h in c['component_holds']}),'preview_not_materialized':True})
 return {'source_SHA256':sourcehash,'source_UTF8_bytes':len(source.encode()),'complete_section_partition':regions,'source_partition':sections,'ref_occurrences':occurrence,'citation_companions':companions,'opaque_reference_contexts':opaque,'opaque_propagation':{'exact_named_keys':[list(k) for k in sorted(opaque_keys)],'unbound_identity_global_guard':global_opaque},'all_raw_source_and_citation_spans_retained':True,'reference_holds_only_all_other_AST_gates_unchanged':True,'prior_structural_holds_cleared':False,'native_or_main_prose_preview_materialized':False,'no_template_expansion_external_fetch_or_citation_bibliography_render':True,'new_admitted_documents':0}

def synthetic_section_proxy(section):
 """For control fixtures only; actual integration needs parent-reviewed runner."""
 if section['holds']:return None
 raw=section['raw'];start=section['source_char_span'][0];out=[];cursor=0
 for op in section['marker_operations']:
  a,b=op['source_char_span'];a-=start;b-=start
  if a<cursor or raw[a:b]!=op['raw'] or H(raw[a:b])!=op['raw_SHA256']:raise ValueError('nonoverlap_source_inverse')
  out.extend([raw[cursor:a],op['replacement_marker']]);cursor=b
 out.append(raw[cursor:]);return ''.join(out)
