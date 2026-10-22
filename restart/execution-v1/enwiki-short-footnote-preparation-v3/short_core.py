"""Finite page-local short-footnote binding diagnostics; no template rendering."""
import hashlib,re,datetime
H=lambda s:hashlib.sha256(s.encode()).hexdigest()
class Hold(Exception):pass
CITES={'cite web','cite news','cite book','cite journal','cite encyclopedia','cite magazine','cite report','cite conference','citation','cite av media'}
LOC={'p','pp','loc'}
NO_SUPPORTED_KEY={'missing_literal_author_key','missing_literal_year_or_date'}
def name(n):
 if any(type(v).__name__!='Text' for v in n.name.nodes):raise Hold('nonliteral_template_name')
 return str(n.name).strip().replace('_',' ').lower()
def params(n):
 if len(n.params)>128:raise Hold('parameter128cap')
 out={}
 for p in n.params:
  if any(type(v).__name__!='Text' for v in p.name.nodes):raise Hold('nonliteral_parameter_name')
  k=str(p.name).strip()
  if not k or k in out:raise Hold('duplicate_or_empty_parameter_name')
  out[k]=p
 return out
def scalar(code,literal):
 if any(type(v).__name__!='Text' for v in code.nodes):raise Hold('nonliteral_binding_or_qualifier_AST')
 value=str(code).strip()
 if not value or len(value)>512:raise Hold('empty_or_oversize_literal')
 try:literal.project(code)
 except literal.Hold as e:raise Hold('invalid_literal:'+str(e))
 if any(c in value for c in '{}[]<>\n\r'):raise Hold('ambiguous_literal')
 return value
def key_from_short(n,literal):
 p=params(n);positions=sorted(int(k) for k in p if k.isdecimal())
 if positions!=list(range(1,len(positions)+1)) or not 2<=len(positions)<=5 or set(p)-{str(v) for v in positions}-LOC:raise Hold('unsupported_short_key_or_qualifier_parameters')
 values=[scalar(p[str(i)].value,literal) for i in positions]
 if not re.fullmatch('[0-9]{4}[a-z]?',values[-1]):raise Hold('unsupported_literal_year')
 qualifiers={k:{'raw':str(p[k]),'value_raw':str(p[k].value),'literal_value':scalar(p[k].value,literal)} for k in LOC if k in p}
 if 'p' in qualifiers and 'pp' in qualifiers:raise Hold('ambiguous_p_and_pp')
 return tuple(values),qualifiers
MONTHS={n:i for i,n in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'],1)}
def date_year(value):
 if re.fullmatch('[0-9]{4}',value):return value
 if re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value):return str(datetime.date.fromisoformat(value).year)
 for pattern in [r'([0-9]{1,2}) ([A-Za-z]+) ([0-9]{4})',r'([A-Za-z]+) ([0-9]{1,2}), ([0-9]{4})']:
  m=re.fullmatch(pattern,value)
  if m:
   a,b,y=m.groups();day,month=(int(a),b) if a.isdecimal() else (int(b),a)
   if month not in MONTHS:raise Hold('unsupported_date_month')
   return str(datetime.date(int(y),MONTHS[month],day).year)
 m=re.fullmatch(r'([A-Za-z]+) ([0-9]{4})',value)
 if m and m[1] in MONTHS:return m[2]
 raise Hold('unsupported_literal_date_grammar')
def bibliography(n,literal,parser):
 p=params(n);raw_params=[];components=[]
 for k,v in p.items():
  value_holds=[]
  for child in v.value.nodes:
   if type(child).__name__ in ('Text','HTMLEntity','ExternalLink'):
    try:literal.project(parser.wikicode.Wikicode([child]))
    except literal.Hold as e:raise Hold('invalid_bibliographic_literal:'+str(e))
   else:value_holds.append('unrendered_bibliographic_value:'+type(child).__name__)
  if list(v.value.ifilter_tags(matches=lambda t:str(t.tag).lower()=='ref',recursive=True)):raise Hold('nested_reference_in_bibliography')
  raw_params.append({'name_raw':str(v.name),'value_raw':str(v.value),'raw':str(v),'raw_SHA256':H(str(v)),'component_holds':value_holds});components+=value_holds
 if 'ref' in p:
  nodes=p['ref'].value.nodes
  if len(nodes)!=1 or type(nodes[0]).__name__!='Template' or name(nodes[0])!='sfnref':raise Hold('unsupported_explicit_reference_key_no_automatic_fallback')
  key,qualifiers=key_from_short(nodes[0],literal);basis={'kind':'explicit_sfnRef','raw':str(p['ref'].value),'ignored_anchor_location_fields_preserved':qualifiers}
 else:
  if 'last' in p and 'last1' in p:raise Hold('ambiguous_last_last1')
  if ('last' in p or 'last1' in p) and 'author' in p:raise Hold('ambiguous_author_last')
  authors=[]
  for i in range(1,5):
   k=('last' if 'last' in p else 'last1') if i==1 else 'last'+str(i)
   if k in p:authors.append(scalar(p[k].value,literal))
   elif any('last'+str(j) in p for j in range(i+1,5)):raise Hold('noncontiguous_author_key')
  if not authors and 'author' in p:authors=[scalar(p['author'].value,literal)]
  if not authors:raise Hold('missing_literal_author_key')
  if any(re.fullmatch(r'(?:last|author)[0-9]+',k) and (k.startswith('author') or int(k[4:])>4) for k in p):raise Hold('unsupported_author_list_key')
  year=scalar(p['year'].value,literal) if 'year' in p else None
  if year is not None and not re.fullmatch('[0-9]{4}[a-z]?',year):raise Hold('unsupported_literal_year')
  dy=date_year(scalar(p['date'].value,literal)) if 'date' in p else None
  if year and dy and year[:4]!=dy:raise Hold('conflicting_year_date')
  if not year and not dy:raise Hold('missing_literal_year_or_date')
  key=tuple(authors+[year or dy]);basis={'kind':'literal_author_year_or_validated_date','year_raw':str(p['year'].value) if 'year'in p else None,'date_raw':str(p['date'].value) if 'date'in p else None}
 return key,basis,raw_params,sorted(set(components))
def partial_shadow_constraint(node,reason,literal):
 global_result={'kind':'GLOBAL_UNBOUND','reason':reason,'defines_usable_bibliography':False,'retains_all_component_holds':True}
 if reason!='nonliteral_binding_or_qualifier_AST':return global_result
 try:
  p=params(node)
  # An explicit or duplicate/ambiguous identity may define unrelated keys.
  if 'ref' in p or not ('author' in p) or any(k.startswith('last') or (k.startswith('author') and k!='author') for k in p):return global_result
  nodes=p['author'].value.nodes
  # Finite observed class: a single ordinary wikilink author identity. Its
  # name is NOT rendered or guessed; it could shadow any author in this year.
  if len(nodes)!=1 or type(nodes[0]).__name__!='Wikilink':return global_result
  link=nodes[0]
  if any(type(x).__name__!='Text' for x in link.title.nodes):return global_result
  if link.text is not None and any(type(x).__name__!='Text' for x in link.text.nodes):return global_result
  scalar(link.title,literal)
  if link.text is not None:scalar(link.text,literal)
  if any(list(v.value.ifilter_tags(matches=lambda t:str(t.tag).lower()=='ref',recursive=True)) for v in p.values()):return global_result
  year=scalar(p['year'].value,literal) if 'year' in p else None
  if year is not None and not re.fullmatch('[0-9]{4}[a-z]?',year):return global_result
  date=date_year(scalar(p['date'].value,literal)) if 'date' in p else None
  if year and date and year[:4]!=date:return global_result
  if not year and not date:return global_result
  # Keep full possible suffix domain if source supplies date only or a bare
  # year; supported SFN year[a-z]? keys in same base year all stay shadowed.
  base=(year or date)[:4]
  return {'kind':'ANY_AUTHOR_BASE_YEAR','base_year':base,'unresolved_author_raw':str(p['author'].value),'year_raw':str(p['year'].value) if 'year'in p else None,'date_raw':str(p['date'].value) if 'date'in p else None,'defines_usable_bibliography':False,'retains_all_component_holds':True}
 except (Hold,ValueError):return global_result

def partial_shadows(constraint,key):
 if constraint['kind']=='GLOBAL_UNBOUND':return True
 if constraint['kind']=='ANY_AUTHOR_BASE_YEAR':return bool(key) and key[-1][:4]==constraint['base_year']
 raise ValueError('unknown_shadow_constraint')

def resolve_page(source,parser,literal,reference,expected_regions=None,reference_plan=None):
 if len(source.encode())>120000:raise ValueError('page120000bytecap')
 code,regions=reference.spans(source,parser)
 if len(regions)>100 or (expected_regions is not None and expected_regions!=regions):raise ValueError('complete_regions_cap_or_mismatch')
 ref=reference_plan if reference_plan is not None else reference.resolve_page(source,parser,expected_regions,literal)
 if ref['source_SHA256']!=H(source) or ref['complete_section_partition']!=regions or ''.join(x['raw'] for x in ref['source_partition'])!=source:raise ValueError('exact_original_reference_handoff_source_partition')
 owned_refs={}
 for occurrence in ref['ref_occurrences']:
  a,b=occurrence['source_char_span'];ba,bb=occurrence['source_byte_span']
  if source[a:b]!=occurrence['raw'] or source.encode()[ba:bb]!=occurrence['raw'].encode() or H(occurrence['raw'])!=occurrence['raw_SHA256']:raise ValueError('exact_original_reference_handoff_occurrence_binding')
  if not occurrence['holds']:owned_refs[(a,b)]=occurrence
 short=[];bibs=[];opaque=[];holds={i:set(ref['source_partition'][i]['holds']) for i in range(len(regions))};keys={};global_shadow=False;partial_shadows_inventory=[]
 def bound(a,b):return {'source_char_span':[a,b],'source_byte_span':[len(source[:a].encode()),len(source[:b].encode())],'raw':source[a:b],'raw_SHA256':H(source[a:b])}
 def sid(a,b):
  found=[i for i,(x,y) in enumerate(regions) if x<=a and b<=y]
  if len(found)!=1:raise ValueError('construct_crosses_complete_region')
  return found[0]
 def visit(code,start,path,short_allowed=True):
  nonlocal global_shadow
  if len(path)>64:raise ValueError('depth64cap')
  cursor=start
  for i,n in enumerate(code.nodes):
   a=cursor;b=a+len(str(n));cursor=b;assert source[a:b]==str(n);kind=type(n).__name__;nm=name(n) if kind=='Template' and all(type(v).__name__=='Text' for v in n.name.nodes) else None
   if nm=='sfn':
    k=sid(a,b);o={**bound(a,b),'section_ordinal':k,'AST_path':path+[i],'holds':[],'marker':None}
    try:
     if not short_allowed:raise Hold('shortnote_inside_reference_requires_owned_semantic_adapter')
     o['key'],o['qualifiers']=key_from_short(n,literal)
    except Hold as e:o['holds']=[str(e)];holds[k].add(str(e))
    short.append(o)
   elif nm in CITES:
    k=sid(a,b);o={**bound(a,b),'section_ordinal':k,'AST_path':path+[i],'holds':[],'component_holds':[],'bibliography_ID':H(H(source)+'\x00bib\x00'+str(a))}
    try:o['key'],o['key_basis'],o['raw_parameters'],o['component_holds']=bibliography(n,literal,parser);keys.setdefault(o['key'],[]).append(o)
    except (Hold,ValueError) as e:
     o['holds']=[str(e)];o['no_supported_short_key_not_a_prose_failure']=str(e) in NO_SUPPORTED_KEY
     if str(e) not in NO_SUPPORTED_KEY:o['component_holds']=['unrendered_bibliographic_binding_component:'+str(e)]
     if str(e) not in NO_SUPPORTED_KEY:
      constraint=partial_shadow_constraint(n,str(e),literal)
      o['potential_shadow_constraint']=constraint
      if constraint['kind']=='GLOBAL_UNBOUND':global_shadow=True
      else:partial_shadows_inventory.append({**bound(a,b),'section_ordinal':k,'constraint':constraint})
    bibs.append(o)
   elif kind=='Tag' and str(n.tag)=='ref' and (a,b) in owned_refs:
    occurrence=owned_refs[(a,b)]
    if occurrence['kind']=='definition':
     try:pre,_,_=reference.content_parts(n);visit(n.contents,a+len(pre),path+[i,'owned_ref_contents'],False)
     except reference.RefHold as e:raise ValueError('validated_reference_container_handoff:'+str(e))
   elif kind=='Tag' and str(n.tag) in ('b','i','em','strong') and not n.attributes and not n.self_closing:
    try:pre,_,_=reference.content_parts(n);visit(n.contents,a+len(pre),path+[i,'contents'],short_allowed)
    except reference.RefHold:holds[sid(a,b)].add('unsupported_shortfootnote_wrapper')
   elif kind not in ('Text','Comment','HTMLEntity','Heading'):
    nested=[q for child in n.__children__() for q in child.ifilter_templates(recursive=True) if all(type(v).__name__=='Text' for v in q.name.nodes) and name(q) in CITES|{'sfn'}]
    if nested:
     k=sid(a,b);hidden=[]
     for q in nested:
      item={'raw':str(q),'raw_SHA256':H(str(q)),'template_name':name(q)}
      if name(q) in CITES:
       try:bk,_,_,_=bibliography(q,literal,parser);item['potential_key']=bk;keys.setdefault(bk,[]).append({'opaque_shadow':True})
       except (Hold,ValueError) as e:
        item['unbound_key_reason']=str(e);item['unbound_key_global_shadow']=str(e) not in NO_SUPPORTED_KEY;global_shadow=global_shadow or item['unbound_key_global_shadow']
      hidden.append(item)
     opaque.append({**bound(a,b),'section_ordinal':k,'hidden_templates':hidden});holds[k].add('shortfootnote_or_bibliography_inside_opaque_context')
  if cursor!=start+len(str(code)):raise ValueError('node_inverse')
 visit(code,0,[])
 if len(short)>1000 or len(bibs)>1000:raise ValueError('construct1000cap')
 operations=[]
 for i,o in enumerate(short):
  if o['holds']:continue
  choices=keys.get(o['key'],[])
  matching_partial=[v for v in partial_shadows_inventory if partial_shadows(v['constraint'],o['key'])]
  o['potential_shadow_constraint_matches']=[{'source_char_span':v['source_char_span'],'raw_SHA256':v['raw_SHA256'],'constraint':v['constraint']} for v in matching_partial]
  error='unbound_bibliography_global_shadow_guard' if global_shadow else 'potential_bibliography_base_year_shadow_guard' if matching_partial else 'missing_page_local_bibliographic_key' if not choices else 'duplicate_conflicting_or_opaque_bibliographic_key' if len(choices)!=1 or choices[0].get('opaque_shadow') else None
  if error:o['holds'].append(error);holds[o['section_ordinal']].add(error);continue
  b=choices[0];o.update({'bibliography_ID':b['bibliography_ID'],'component_holds':b['component_holds'],'marker':'⟦sfn:'+str(i+1)+'⟧'})
  if o['marker'] in source:o['holds'].append('reserved_short_marker_collision');holds[o['section_ordinal']].add('reserved_short_marker_collision');continue
  operations.append({**{k:o[k] for k in ['source_char_span','source_byte_span','raw','raw_SHA256','section_ordinal']},'replacement_marker':o['marker'],'bibliography_ID':b['bibliography_ID'],'qualifiers':o['qualifiers']})
 sections=[]
 for i,(a,b) in enumerate(regions):
  sections.append({**bound(a,b),'section_ordinal':i,'holds':sorted(holds[i]),'marker_operations':[] if holds[i] else [v for v in operations if v['section_ordinal']==i],'semantic_companion_holds':sorted(set(ref['source_partition'][i].get('semantic_companion_holds',[]))|{h for o in short+bibs if o['section_ordinal']==i for h in o.get('component_holds',[])}),'no_admission':True})
 return {'source_SHA256':H(source),'complete_section_partition':regions,'source_partition':sections,'short_footnote_occurrences':short,'bibliographic_companions':bibs,'opaque_contexts':opaque,'unbound_bibliographic_global_shadow':global_shadow,'partial_bibliographic_shadow_constraints':partial_shadows_inventory,'reference_handoff':{'source_SHA256':ref['source_SHA256'],'structurally_owned_reference_occurrences':len(owned_refs),'all_original_reference_holds_preserved':True},'all_source_values_retained':True,'no_template_execution_citation_rendering_external_fetch_or_fact_clearance':True,'new_admitted_documents':0}
