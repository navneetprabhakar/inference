"""Bounded streaming native XML frame. No DTD/entities/network/rendering."""
import bz2,collections,hashlib,xml.parsers.expat as expat,urllib.parse
LIMITS={'compressed_prefix_bytes':20000000,'decoded_prefix_bytes':128000000,'pages':2000,'page_XML_bytes':8000000,'header_XML_bytes':1000000,'metadata_field_bytes':262144}
def sha(b):return hashlib.sha256(b).hexdigest()
def split(name):return name.rsplit('}',1) if '}' in name else ('',name)
class Framer:
 def __init__(self,emit=lambda p:None):
  self.p=expat.ParserCreate(namespace_separator='}');self.p.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
  self.p.StartElementHandler=self.start;self.p.EndElementHandler=self.end;self.p.CharacterDataHandler=self.data;self.p.StartNamespaceDeclHandler=self.namespace;self.p.XmlDeclHandler=self.declaration
  self.p.StartDoctypeDeclHandler=self.forbid;self.p.EntityDeclHandler=self.forbid;self.p.ExternalEntityRefHandler=self.forbid;self.p.SkippedEntityHandler=self.forbid
  self.stack=[];self.raw=bytearray();self.base=0;self.decoded=0;self.header=None;self.root=None;self.siteinfo=None;self.root_closed=False;self.active=None;self.pages=[];self.ids=set();self.revids=set();self.counts=collections.Counter();self.namespaces=[];self.emit=emit;self.segment=None;self.leading=b'';self.prefix_checked=False
 def forbid(self,*x):raise ValueError('DTD_entity_external_access_forbidden')
 def declaration(self,version,encoding,standalone):
  if encoding is not None and encoding.lower().replace('-','')!='utf8':raise ValueError('UTF8_XML_required')
 def namespace(self,prefix,uri):self.namespaces.append({'prefix':prefix,'URI':uri,'decoded_byte':self.p.CurrentByteIndex})
 def raw_end(self,node):
  pos=self.p.CurrentByteIndex;i=pos-self.base
  if self.raw[i:i+2]==b'</':
   end=self.raw.find(b'>',i)
   if end<0:raise ValueError('unavailable_closing_tag_source_bytes')
   return self.base+end+1
  # Expat positions an empty-element End callback immediately after '/>'.
  if self.raw[max(0,i-2):i]==b'/>':return pos
  raise ValueError('unsupported_XML_end_event_position')
 def start(self,name,attrs):
  ns,local=split(name);depth=len(self.stack)
  if depth==0:
   if local!='mediawiki' or not ns.startswith('http://www.mediawiki.org/xml/export-') or not ns.endswith('/'):raise ValueError('actual_mediawiki_root_namespace_required')
   self.root={'expanded_name':name,'namespace_URI':ns,'attributes':dict(attrs),'namespace_declarations':list(self.namespaces)}
  elif ns!=self.root['namespace_URI']:raise ValueError('mixed_native_element_namespace')
  if depth==1:
   if local not in ['siteinfo','page']:raise ValueError('unsupported_root_child_'+local)
   if local=='page':
    if self.siteinfo is None:raise ValueError('siteinfo_must_precede_page')
    if self.active is not None:raise ValueError('nested_page')
    if self.header is None:
     n=self.p.CurrentByteIndex-self.base
     if self.base!=0 or n>LIMITS['header_XML_bytes']:raise ValueError('header_limit_or_source_position')
     self.header=bytes(self.raw[:n])
    self.active=self.p.CurrentByteIndex
  node={'name':local,'expanded_name':name,'attrs':dict(attrs),'start':self.p.CurrentByteIndex,'children':[],'hash':hashlib.sha256(),'sha1':hashlib.sha1(),'bytes':0,'parts':[]}
  if self.stack:self.stack[-1]['children'].append(node)
  self.stack.append(node)
 def data(self,text):
  if not self.stack:return
  n=self.stack[-1];b=text.encode('utf8');n['hash'].update(b);n['sha1'].update(b);n['bytes']+=len(b)
  if n['name']!='text':
   if n['bytes']>LIMITS['metadata_field_bytes']:raise ValueError('metadata_field_cap')
   n['parts'].append(text)
 def end(self,name):
  n=self.stack.pop()
  if n['expanded_name']!=name:raise ValueError('end_name_mismatch')
  n['end']=self.raw_end(n);n['value']=''.join(n['parts']);n['SHA256']=n['hash'].hexdigest();n['SHA1']=n['sha1'].hexdigest();n.pop('hash');n.pop('sha1');n.pop('parts')
  if len(self.stack)==1 and n['name']=='siteinfo':
   if self.siteinfo is not None:raise ValueError('duplicate_siteinfo')
   self.siteinfo=n;self.stack[0]['children'].remove(n)
  if len(self.stack)==1 and n['name']=='page':
   if len(self.pages)>=LIMITS['pages']:raise ValueError('page_count_cap')
   record=self.page(n);self.pages.append(record);self.emit(record);self.stack[0]['children'].remove(n);self.active=None
   if len(self.pages)>LIMITS['pages']:raise ValueError('page_count_cap')
  if not self.stack:self.root_closed=True
 def feed(self,b):
  if not isinstance(b,bytes):raise TypeError('bytes_required')
  if self.decoded+len(b)>LIMITS['decoded_prefix_bytes']:raise ValueError('decoded_prefix_cap')
  self.raw.extend(b);self.decoded+=len(b)
  if self.active is not None and self.decoded-self.active>LIMITS['page_XML_bytes']:raise ValueError('page_XML_cap')
  # Native source UTF8; buffer a tiny initial prefix before first parser feed.
  if not self.prefix_checked:
   self.leading+=b
   if len(self.leading)<4:return
   if b'\0' in self.leading[:4] or self.leading.startswith((b'\xff\xfe',b'\xfe\xff')):raise ValueError('nonUTF8_XML_prefix')
   b=self.leading;self.leading=b'';self.prefix_checked=True
  self.p.Parse(b,False)
  keep=self.active if self.active is not None else self.p.CurrentByteIndex
  if self.header is None:keep=0
  if keep<self.base or keep>self.base+len(self.raw):raise ValueError('rolling_source_buffer_position')
  del self.raw[:keep-self.base];self.base=keep
  if self.active is not None and len(self.raw)>LIMITS['page_XML_bytes']:raise ValueError('page_XML_cap')
 def children(self,n,key):return [x for x in n['children'] if x['name']==key]
 def one(self,n,key,required=False):
  v=self.children(n,key)
  if len(v)>1 or (required and len(v)!=1):raise ValueError('direct_native_field_cardinality_'+key)
  return v[0] if v else None
 def field(self,n,key,required=False):
  x=self.one(n,key,required);return x['value'] if x is not None else None
 def describe(self,n):return {'attributes':n['attrs'],'decoded_byte_span':[n['start'],n['end']],'decoded_character_data_UTF8_bytes':n['bytes'],'decoded_character_data_SHA256':n['SHA256'],'value':n['value'] if n['name']!='text' else None}
 def textmeta(self,n):
  if n is None:return {'present':False,'hold':'MISSING_TEXT'}
  if n['children']:raise ValueError('text_contains_unexpected_XML_child')
  result={'present':True,**self.describe(n),'SHA1_hex_of_decoded_UTF8':n['SHA1'],'raw_native_SHA1_unverified_or_comparison':n['attrs'].get('sha1'),'native_byte_count_matches':None,'native_base36_SHA1_matches':None}
  if 'bytes' in n['attrs']:
   if not n['attrs']['bytes'].isdigit():raise ValueError('invalid_text_bytes_attribute')
   result['native_byte_count_matches']=int(n['attrs']['bytes'])==n['bytes']
  h=n['attrs'].get('sha1')
  if h is not None:
   if not h or not all(c in '0123456789abcdefghijklmnopqrstuvwxyz' for c in h):raise ValueError('invalid_native_base36_SHA1')
   result['native_base36_SHA1_matches']=int(h,36)==int(n['SHA1'],16)
  return result
 def page(self,n):
  start,end=n['start'],n['end'];raw=bytes(self.raw[start-self.base:end-self.base])
  if len(raw)!=end-start or len(raw)>LIMITS['page_XML_bytes']:raise ValueError('page_source_span_hash_cap')
  ident=self.field(n,'id',True);title=self.field(n,'title',True);namespace=self.field(n,'ns',True)
  if not ident.isdigit() or not namespace.lstrip('-').isdigit():raise ValueError('direct_pageID_namespace_numeric')
  ident=int(ident);namespace=int(namespace)
  if ident in self.ids:raise ValueError('duplicate_page_ID_within_prefix_'+str(ident))
  self.ids.add(ident);redirect=self.children(n,'redirect')
  if len(redirect)>1:raise ValueError('duplicate_redirect')
  holds=[];revisions=[]
  for r in self.children(n,'revision'):
   revision=self.field(r,'id',True)
   if not revision.isdigit():raise ValueError('direct_revisionID_numeric')
   if revision in self.revids:raise ValueError('duplicate_revision_ID_within_prefix_'+revision)
   self.revids.add(revision);slots=self.one(r,'slots');direct=self.one(r,'text');contents=[]
   if slots is not None and direct is not None:holds.append('AMBIGUOUS_DIRECT_TEXT_AND_SLOTS')
   if slots is not None:
    for slot in self.children(slots,'slot'):contents.append({'slot_attributes':slot['attrs'],'model':self.field(slot,'model'),'format':self.field(slot,'format'),'text':self.textmeta(self.one(slot,'text'))})
    if not contents:holds.append('EMPTY_OR_UNKNOWN_SLOTS_SCHEMA')
   else:contents.append({'slot_attributes':None,'model':self.field(r,'model'),'format':self.field(r,'format'),'text':self.textmeta(direct)})
   for content in contents:
    text=content['text']
    if not text['present'] or 'deleted' in text.get('attributes',{}) or text.get('native_byte_count_matches') is False or text.get('native_base36_SHA1_matches') is False:holds.append('TEXT_MISSING_DELETED_OR_NATIVE_HASH_SIZE_MISMATCH')
    if content['model']!='wikitext':holds.append('NON_WIKITEXT_OR_UNSPECIFIED_MODEL')
   contributor=self.one(r,'contributor')
   revisions.append({'revision_ID':int(revision),'revision_attributes':r['attrs'],'direct_revision_ID_position':self.describe(self.one(r,'id',True)),'parent_ID':self.field(r,'parentid'),'timestamp':self.field(r,'timestamp'),'native_revision_SHA1':self.field(r,'sha1'),'contributor':None if contributor is None else {'attributes':contributor['attrs'],'fields':[{'name':c['name'],**self.describe(c)} for c in contributor['children']]},'comment':None if self.one(r,'comment') is None else self.describe(self.one(r,'comment')),'content_slots_or_legacy':contents,'source_decoded_span':[r['start'],r['end']]})
  if not revisions:holds.append('NO_REVISION')
  namespace_nodes=self.one(self.siteinfo,'namespaces',True);known={selfnode['attrs'].get('key'):selfnode for selfnode in self.children(namespace_nodes,'namespace')}
  if str(namespace) not in known:holds.append('NAMESPACE_NOT_IN_CAPTURED_SITEINFO')
  base=self.field(self.siteinfo,'base',True);u=urllib.parse.urlsplit(base);origin=u.scheme+'://'+u.netloc
  if u.scheme!='https' or u.netloc!='en.wikipedia.org':raise ValueError('actual_enwiki_siteinfo_base_required_for_derived_links')
  self.counts['pages']+=1;self.counts['namespace:'+str(namespace)]+=1;self.counts['redirects']+=bool(redirect);self.counts['nonzero_namespace_pages']+=namespace!=0;self.counts['ns0_nonredirect_pages_pending_only']+=namespace==0 and not redirect
  return {'page_ID':ident,'title':title,'namespace':namespace,'native_page_attributes':n['attrs'],'redirect_present':bool(redirect),'redirect_attributes':redirect[0]['attrs'] if redirect else None,'direct_page_ID_position':self.describe(self.one(n,'id',True)),'page_raw_XML_SHA256':sha(raw),'page_decoded_byte_span':[start,end],'source_compressed_segment':self.segment,'revisions':revisions,'holds':sorted(set(holds)),'source_links_derived_not_literal_XML_fields':{'page':origin+'/w/index.php?curid='+str(ident),'history':origin+'/w/index.php?curid='+str(ident)+'&action=history','revisions':[origin+'/w/index.php?oldid='+str(r['revision_ID']) for r in revisions]},'alltypes_frame_only_not_article_or_English_or_prose':True,'no_author_history_or_rights_clearance':True,'new_admitted_documents':0}
 def finish(self,prefix_only=True):
  if self.active is not None or len(self.stack)!=(1 if prefix_only else 0):raise ValueError('incomplete_XML_element_at_prefix_boundary')
  if prefix_only and (self.root_closed or self.p.CurrentByteIndex!=self.decoded):raise ValueError('prefix_root_closed_or_incomplete_token')
  if self.root is None or self.siteinfo is None or self.header is None:raise ValueError('incomplete_header_siteinfo_or_no_pages')
  return {'status':'PREFIX_ONLY_NO_GLOBAL_XML_VALIDITY_OR_YIELD_CLAIM' if prefix_only else 'COMPLETE_SYNTHETIC_XML_FIXTURE','root':self.root,'siteinfo':self.siteinfo,'counts':dict(self.counts),'decoded_prefix_bytes':self.decoded,'page_IDs_unique_within_prefix_only':True,'revision_IDs_unique_within_prefix_only':True,'XML_root_closed':self.root_closed,'global_XML_validity_claim':False,'all_page_types_retained_in_counts':True}

def segment_decode(raw,feed,remaining,check=lambda:None):
 # Each exact indexed range (or header range) may contain complete concatenated
 # BZ2 members. Every member must reach CRC-verified EOF with no trailingjunk.
 pending=raw;members=0;decoded=0;h=hashlib.sha256()
 while pending:
  if not pending.startswith(b'BZh'):raise ValueError('BZ2_member_or_trailing_data')
  d=bz2.BZ2Decompressor();payload=pending
  while True:
   check()
   if decoded>=remaining:raise ValueError('decoded_cap_reached_no_unbudgeted_probe')
   b=d.decompress(payload,max_length=min(65536,remaining-decoded));payload=b''
   decoded+=len(b)
   if decoded>remaining:raise ValueError('decoded_prefix_cap')
   h.update(b);feed(b)
   if d.eof:break
   if d.needs_input:raise ValueError('truncated_BZ2_member_missing_CRC_EOF')
  members+=1;pending=d.unused_data
 return {'compressed_bytes':len(raw),'compressed_SHA256':sha(raw),'decoded_bytes':decoded,'decoded_SHA256':h.hexdigest(),'members_CRC_EOF_verified':members,'trailing_data_absent':True}
