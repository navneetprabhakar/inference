"""Heading-stack diagnostics from emitted metadata, never a semantic acceptance filter."""
HEADINGS={f'h{i}':i for i in range(1,7)}
SEMANTIC_KINDS={'p','li','pre','blockquote','table','dl','figure','math'}
def diagnose(blocks):
 stack=[];empty=[];unknown=[];nonheading=0;prior=-1
 def close():
  item=stack.pop()
  if not item['has_nonheading_block']:empty.append({'heading_ordinal':item['ordinal'],'kind':item['kind'],'heading_SHA256':item['hash'],'contains_nested_heading':item['nested']})
 for b in blocks:
  ordinal=b['ordinal'];kind=b['kind'];chars=b['characters']
  if type(ordinal)is not int or ordinal!=prior+1 or type(chars)is not int or chars<0:raise ValueError('ordered_block_metadata')
  if not isinstance(b['hash'],str) or len(b['hash'])!=64 or any(c not in 'abcdef0123456789' for c in b['hash']):raise ValueError('block_hash_schema')
  prior=ordinal
  if kind in HEADINGS:
   level=HEADINGS[kind]
   while stack and stack[-1]['level']>=level:close()
   for item in stack:item['nested']=True
   stack.append({'ordinal':ordinal,'kind':kind,'hash':b['hash'],'level':level,'has_nonheading_block':False,'nested':False})
  else:
   # Every nonempty nonheading is positive for completeness, including code,
   # reference/instruction lists, links-only lists, or an unknown future kind.
   # Unknown kind is separately reported; it cannot manufacture an empty unit.
   if kind not in SEMANTIC_KINDS:unknown.append({'ordinal':ordinal,'kind':kind})
   if chars>0:
    nonheading+=1
    for item in stack:item['has_nonheading_block']=True
 while stack:close()
 return {'blocks':prior+1,'nonempty_nonheading_blocks':nonheading,'empty_heading_subtrees':sorted(empty,key=lambda x:x['heading_ordinal']),'empty_leaf_heading_subtrees':sum(not x['contains_nested_heading'] for x in empty),'unknown_kind_diagnostics':unknown,'semantic_failure_inferred':False,'exclusion_or_admission_performed':False}
def synthetic():
 def b(k,n=1):return {'ordinal':0,'kind':k,'characters':n,'hash':'a'*64}
 def run(kinds):return diagnose([{**b(k,n),'ordinal':i} for i,(k,n) in enumerate(kinds)])
 tests=[]
 for name,kinds,count in [('empty_leaf',[('h2',5)],1),('empty_nested_parent_and_leaf',[('h2',5),('h3',5)],2),('heading_parent_with_child_prose',[('h2',5),('h3',5),('p',1)],0),('empty_child_does_not_poison_neighbor',[('h2',5),('h3',5),('p',1),('h3',5)],1),('short_definition',[('h2',5),('p',1)],0),('code_only_positive',[('h2',5),('pre',1)],0),('pure_link_reference_list_positive',[('h2',5),('li',1)],0),('procedure_list_positive',[('h2',5),('li',1)],0),('historical_text_positive',[('h2',5),('p',1)],0),('unknown_kind_nonempty_positive',[('h2',5),('future_media',1)],0),('empty_paragraph_not_fake_content',[('h2',5),('p',0)],1),('empty_prior_section_closes_at_same_level',[('h2',5),('h2',5),('p',1)],1),('prose_before_heading_does_not_fill_later_section',[('p',1),('h2',5)],1)]:
  r=run(kinds);assert len(r['empty_heading_subtrees'])==count and not r['semantic_failure_inferred'];tests.append(name)
 for name,rows in [('ordinal_gap',[{**b('p'),'ordinal':1}]),('bad_hash',[{**b('p'),'hash':'x'}]),('negative_length',[b('p',-1)])]:
  try:diagnose(rows)
  except ValueError:tests.append(name)
  else:raise AssertionError(name)
 return {'status':'PASS_SYNTHETIC_METADATA_ONLY','controls':len(tests),'cases':tests}
