"""Streaming emitted-block metadata diagnostics. No semantic exclusion or body access."""
import hashlib,json
HEADINGS={f'h{i}':i for i in range(1,7)}
KINDS={'p','li','pre','blockquote','table','dl','figure','math'}
def compact(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def digest(x):return hashlib.sha256(compact(x)).hexdigest()
def summarize(blocks,expected_characters,on_block=lambda:None):
 stack=[];empty=leaf=unknown=nonheading=count=0;last_end=None;eh=hashlib.sha256();uh=hashlib.sha256();examples=[];unknown_examples=[]
 def close():
  nonlocal empty,leaf
  h=stack.pop()
  if not h['content']:
   event={'heading_ordinal':h['ordinal'],'kind':h['kind'],'hash':h['hash'],'nested':h['nested']};empty+=1;leaf+=not h['nested'];eh.update(compact(event)+b'\n')
   if len(examples)<12:examples.append(event)
 for ordinal,kind,h,characters,start,end in blocks:
  on_block()
  if type(ordinal)is not int or ordinal!=count or not isinstance(kind,str) or not 1<=len(kind)<=64 or type(characters)is not int or characters<0 or type(start)is not int or type(end)is not int or end-start!=characters or start!=(0 if last_end is None else last_end+2):raise ValueError('block_order_kind_characters_ranges')
  if not isinstance(h,str) or len(h)!=64 or any(c not in '0123456789abcdef' for c in h):raise ValueError('block_hash_schema')
  count+=1;last_end=end
  if kind in HEADINGS:
   level=HEADINGS[kind]
   while stack and stack[-1]['level']>=level:close()
   for s in stack:s['nested']=True
   stack.append({'ordinal':ordinal,'kind':kind,'hash':h,'level':level,'content':False,'nested':False})
  else:
   if kind not in KINDS:
    event={'ordinal':ordinal,'kind':kind};unknown+=1;uh.update(compact(event)+b'\n')
    if len(unknown_examples)<12:unknown_examples.append(event)
   if characters>0:
    nonheading+=1
    for s in stack:s['content']=True
 while stack:close()
 if not count or last_end!=expected_characters:raise ValueError('emitted_block_full_document_character_coverage')
 return {'blocks':count,'nonempty_nonheading':nonheading,'empty_subtrees':empty,'empty_leaf_subtrees':leaf,'empty_close_event_SHA256':eh.hexdigest(),'empty_examples':examples,'unknown_kinds':unknown,'unknown_kind_event_SHA256':uh.hexdigest(),'unknown_examples':unknown_examples}
def bounded_record(identity,feature,max_bytes=1024):
 r={**identity,'feature':feature,'context_review_only':True};r['feature']=dict(feature)
 while True:
  f=r['feature'];r['empty_examples_omitted']=f['empty_subtrees']-len(f['empty_examples']);r['unknown_examples_omitted']=f['unknown_kinds']-len(f['unknown_examples']);raw=compact(r)+b'\n'
  if len(raw)<=max_bytes:return raw
  if f['unknown_examples']:f['unknown_examples']=f['unknown_examples'][:-1]
  elif f['empty_examples']:f['empty_examples']=f['empty_examples'][:-1]
  else:raise ValueError('fixed_metadata_record_exceeds1024')
def select_frame(rows,overlay,expected):
 by={}
 for r in rows:
  i=r['source_ordinal']
  if type(i)is not int or i in by:raise ValueError('frame_identity_duplicate_or_type')
  if r['language_pass']!=1 or r['known_discovery_hold']!=0 or json.loads(r['holds'])!=[] or r['tokens_plus_one_EOS']!=r['content_tokens']+1:raise ValueError('frame_language_or_original_holds')
  by[i]=r
 if len(by)!=expected['base_documents'] or sum(r['content_tokens'] for r in by.values())!=expected['base_tokens']:raise ValueError('base_language_frame_counts')
 held=set()
 for x in overlay:
  i=x['source_ordinal'];r=by.get(i)
  if i in held or r is None or (r['page_id'],r['revision_id'],r['text_sha256'],r['content_tokens'])!=(x['page_id'],x['revision_id'],x['text_SHA256'],x['stored_M1_content_tokens']):raise ValueError('known_manual_hold_identity')
  held.add(i)
 if len(held)!=expected['held_documents'] or sum(by[i]['content_tokens'] for i in held)!=expected['held_tokens']:raise ValueError('hold_overlay_counts')
 candidates={i:r for i,r in by.items() if i not in held}
 if len(candidates)!=expected['candidate_documents'] or sum(r['content_tokens'] for r in candidates.values())!=expected['candidate_tokens']:raise ValueError('candidate_counts')
 return by,candidates,held
