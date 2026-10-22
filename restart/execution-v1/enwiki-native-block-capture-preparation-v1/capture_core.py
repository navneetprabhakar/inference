"""Bounded native BZ2/page-fragment capture. No rendering or namespace invention."""
import bz2,hashlib,io,re,xml.parsers.expat
from lxml import etree as ET
LIMITS={'decoded_per_range':16000000,'decoded_total':100000000,'output_bytes':16000000,'worker_seconds':55,'external_seconds':60,'observed_RSS_bytes':1000000000,'selected_rows':20,'maximum_ranges':20}
PREFIX=b'<discovery-fragment>';SUFFIX=b'</discovery-fragment>'
def sha(b):return hashlib.sha256(b).hexdigest()
def decode(raw,remaining,check=lambda:None,progress=None):
 limit=min(LIMITS['decoded_per_range'],remaining);parts=[];n=0;data=raw;members=0
 while data:
  check()
  if len(data)<4 or data[:3]!=b'BZh' or data[3] not in b'123456789':raise ValueError('invalid_BZ2_header_or_trailing_data')
  d=bz2.BZ2Decompressor();members+=1
  while True:
   check()
   if n>=limit:raise ValueError('decoded_range_or_total_cap_no_extra_decoded_probe')
   try:part=d.decompress(data,max_length=min(65536,limit-n))
   except OSError as e:raise ValueError('invalid_BZ2_CRC_stream') from e
   parts.append(part);n+=len(part);data=b''
   if progress is not None:progress['decoded_bytes']=n
   if d.eof:data=d.unused_data;break
   if d.needs_input:raise ValueError('truncated_BZ2_no_CRC_EOF')
  # unused data is the next complete member; no padding or garbage accepted.
 if not members:raise ValueError('empty_compressed_range')
 return b''.join(parts),{'decoded_bytes':n,'BZ2_members':members,'all_member_CRC_EOF':True,'trailing_data_absent':True}
def tag_end(b,start):
 quote=None
 for i in range(start,len(b)):
  c=b[i]
  if quote is not None:
   if c==quote:quote=None
  elif c in (34,39):quote=c
  elif c==62:return i+1
 raise ValueError('unterminated_XML_tag')
def page_spans(raw):
 """Expat lexical offsets, independently checked by strict lxml subtree count."""
 raw.decode('utf8',errors='strict')
 if b'\x00' in raw or re.search(br'<!\s*(?:DOCTYPE|ENTITY)',raw,re.I):raise ValueError('DTD_entity_or_nonUTF8_denied')
 # Only page-only fragments may acquire an artificial root. Namespace is absent
 # unless declared by actual source pages. Global mediawiki header is unknown.
 wrapped=PREFIX+raw+SUFFIX;p=xml.parsers.expat.ParserCreate(namespace_separator='}');stack=[];spans=[];active=None
 def start(name,attrs):
  nonlocal active
  if len(stack)==1:
   if name.split('}')[-1]!='page':raise ValueError('nonpage_fragment_boundary_no_repair')
   active=p.CurrentByteIndex-len(PREFIX)
  stack.append(name)
 def end(name):
  nonlocal active
  if len(stack)==2:
   end=tag_end(wrapped,p.CurrentByteIndex)-len(PREFIX)
   if active is None or not 0<=active<end<=len(raw):raise ValueError('page_span_bounds')
   spans.append((active,end));active=None
  stack.pop()
 def denied(*args):raise ValueError('DTD_entity_denied')
 p.StartElementHandler=start;p.EndElementHandler=end;p.StartDoctypeDeclHandler=denied;p.EntityDeclHandler=denied;p.ExternalEntityRefHandler=denied
 p.Parse(wrapped,True)
 parser=ET.XMLParser(resolve_entities=False,load_dtd=False,no_network=True,recover=False,huge_tree=False,remove_blank_text=False,strip_cdata=False)
 root=ET.fromstring(wrapped,parser=parser)
 if root.text and root.text.strip():raise ValueError('nonwhitespace_outside_page')
 pages=[n for n in root if isinstance(n.tag,str)]
 if len(pages)!=len(spans):raise ValueError('independent_lexical_page_count')
 for n in pages:
  if n.tail and n.tail.strip():raise ValueError('nonwhitespace_page_tail')
 return pages,spans

def fields(page,span,raw,indexrow):
 ns=ET.QName(page).namespace
 q=lambda name:('{'+ns+'}'+name) if ns else name
 holds=[]
 def one(parent,name,required=True):
  found=parent.findall(q(name))
  if len(found)!=1:
   if required or found:holds.append('missing_or_ambiguous_'+name)
   return None
  return found[0]
 def text(n):return None if n is None else n.text
 pageid=one(page,'id');title=one(page,'title');namespace=one(page,'ns');revision=one(page,'revision');redirect=one(page,'redirect',False)
 meta={'selected_index_row':indexrow,'observed_page_namespace_URI':ns,'global_dump_namespace_inherited_or_header_known':False,'native_page_id':text(pageid),'native_title':text(title),'native_ns':text(namespace),'native_redirect_attributes':None if redirect is None else dict(redirect.attrib),'raw_page_XML_start':span[0],'raw_page_XML_end_exclusive':span[1],'raw_page_XML_bytes':span[1]-span[0],'raw_page_XML_SHA256':sha(raw[span[0]:span[1]]),'native_revision':None,'source_text':None,'holds':holds,'article_or_prose_classification_performed':False,'source_text_is_unrendered_wikitext_or_native_model':True,'source_rights_cleared':False,'new_admitted_documents':0,'new_admitted_tokens':0}
 if text(pageid)!=str(indexrow['page_ID_observed']) or text(title)!=indexrow['title_observed']:holds.append('native_identity_title_mismatch')
 if text(namespace)!='0':holds.append('non_namespace0_or_missing')
 if redirect is not None:holds.append('redirect')
 body=None
 if revision is not None:
  rid=one(revision,'id');parent=one(revision,'parentid',False);stamp=one(revision,'timestamp',False);sha1=one(revision,'sha1',False);model=one(revision,'model',False);fmt=one(revision,'format',False);source=one(revision,'text',False)
  slots=revision.findall(q('slots'))
  slotmeta=[]
  if slots:
   if source is not None or len(slots)!=1:holds.append('ambiguous_direct_and_slot_text')
   else:
    main=[]
    for slot in slots[0].findall(q('slot')):
     slotmeta.append(dict(slot.attrib))
     if slot.get('role')=='main':main.append(slot)
    if len(main)!=1:holds.append('missing_or_ambiguous_main_slot')
    else:model=one(main[0],'model',False);fmt=one(main[0],'format',False);source=one(main[0],'text',False)
  meta['native_revision']={'id':text(rid),'parentid':text(parent),'timestamp':text(stamp),'sha1':text(sha1),'model':text(model),'format':text(fmt),'slot_attributes':slotmeta,'attributes':dict(revision.attrib)}
  if text(model)!='wikitext' or text(fmt)!='text/x-wiki':holds.append('non_wikitext_or_unverified_model_format')
  if source is None:holds.append('missing_source_text')
  elif len(source):holds.append('unexpected_source_text_child_nodes')
  else:
   body=(source.text or '').encode('utf8');meta['source_text']={'bytes':len(body),'local_SHA256':sha(body),'attributes':dict(source.attrib),'native_sha1_unverified':source.get('sha1') or text(sha1),'XML_entities_decoded_by_strict_parser':True,'rendering_or_template_expansion':False}
   if source.get('deleted') is not None:holds.append('deleted_source_text')
   if not body:holds.append('empty_source_text')
 meta['status']='HELD_NATIVE_DISCOVERY' if holds else 'NATIVE_SOURCE_CAPTURED_PENDING_QUALITY_RIGHTS_DEPENDENCY_REVIEW'
 return meta,body
