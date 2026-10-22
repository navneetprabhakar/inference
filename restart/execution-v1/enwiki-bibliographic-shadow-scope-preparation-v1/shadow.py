"""Proposed conservative partial shadow constraint only, never bibliography binding/rendering."""
def constraint(node,reason,short,literal):
 global_result={'kind':'GLOBAL_UNBOUND','reason':reason,'defines_usable_bibliography':False,'retains_all_component_holds':True}
 if reason!='nonliteral_binding_or_qualifier_AST':return global_result
 try:
  p=short.params(node)
  # An explicit or duplicate/ambiguous identity may define unrelated keys.
  if 'ref' in p or not ('author' in p) or any(k.startswith('last') or (k.startswith('author') and k!='author') for k in p):return global_result
  nodes=p['author'].value.nodes
  # Finite observed class: a single ordinary wikilink author identity. Its
  # name is NOT rendered or guessed; it could shadow any author in this year.
  if len(nodes)!=1 or type(nodes[0]).__name__!='Wikilink':return global_result
  link=nodes[0]
  if any(type(x).__name__!='Text' for x in link.title.nodes):return global_result
  if link.text is not None and any(type(x).__name__!='Text' for x in link.text.nodes):return global_result
  short.scalar(link.title,literal)
  if link.text is not None:short.scalar(link.text,literal)
  if any(list(v.value.ifilter_tags(matches=lambda t:str(t.tag).lower()=='ref',recursive=True)) for v in p.values()):return global_result
  year=short.scalar(p['year'].value,literal) if 'year' in p else None
  if year is not None and not short.re.fullmatch('[0-9]{4}[a-z]?',year):return global_result
  date=short.date_year(short.scalar(p['date'].value,literal)) if 'date' in p else None
  if year and date and year[:4]!=date:return global_result
  if not year and not date:return global_result
  # Keep full possible suffix domain if source supplies date only or a bare
  # year; supported SFN year[a-z]? keys in same base year all stay shadowed.
  base=(year or date)[:4]
  return {'kind':'ANY_AUTHOR_BASE_YEAR','base_year':base,'unresolved_author_raw':str(p['author'].value),'year_raw':str(p['year'].value) if 'year'in p else None,'date_raw':str(p['date'].value) if 'date'in p else None,'defines_usable_bibliography':False,'retains_all_component_holds':True}
 except (short.Hold,ValueError):return global_result

def shadows(constraint,key):
 if constraint['kind']=='GLOBAL_UNBOUND':return True
 if constraint['kind']=='ANY_AUTHOR_BASE_YEAR':return bool(key) and key[-1][:4]==constraint['base_year']
 raise ValueError('unknown_shadow_constraint')
