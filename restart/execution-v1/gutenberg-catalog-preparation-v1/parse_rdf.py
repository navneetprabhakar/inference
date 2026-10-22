"""Native Gutenberg RDF metadata only. Does not fetch or produce book prose."""
import hashlib,re
from urllib.parse import urljoin,urlsplit
from lxml import etree
RDF='http://www.w3.org/1999/02/22-rdf-syntax-ns#';PG='http://www.gutenberg.org/2009/pgterms/';DCT='http://purl.org/dc/terms/';REL='http://id.loc.gov/vocabulary/relators/';XML='http://www.w3.org/XML/1998/namespace'
NS={'rdf':RDF,'pg':PG,'d':DCT};MAX_BYTES=1000000;MAX_NODES=50000;MAX_DEPTH=96
def sha(b):return hashlib.sha256(b).hexdigest()
def text(n):return ''.join(n.itertext()).strip() if n is not None else ''
def resolve(n,value):return urljoin(n.base or 'https://www.gutenberg.org/',value)
def native_identity(url,kind):
 u=urlsplit(url)
 if u.scheme not in {'https','http'} or u.netloc not in {'www.gutenberg.org','gutenberg.org'} or u.query or u.fragment:raise ValueError('Noncanonical official '+kind+' authority')
 match=re.fullmatch('/'+('ebooks' if kind=='ebook' else '2009/agents')+'/([1-9][0-9]*)',u.path)
 if not match:raise ValueError('Unknown '+kind+' identity path')
 identity=int(match.group(1))
 if identity>=2**63:raise ValueError('Unbounded native authorityID')
 return identity
def node_info(n):return {'qualified_name':n.tag,'attributes':dict(n.attrib),'text':text(n),'native_subtree_SHA256':sha(etree.tostring(n,encoding='utf-8',with_tail=False))}
def typed_values(n):
 return {'qualified_name':n.tag,'values':[text(x) for x in n.findall('.//rdf:value',NS)],'memberOf':[x.get('{'+RDF+'}resource') for x in n.iter() if isinstance(x.tag,str) and x.tag.endswith('}memberOf')],'native_subtree_SHA256':sha(etree.tostring(n,encoding='utf-8',with_tail=False))}
def parse(raw,member):
 if len(raw)>MAX_BYTES or b'\0' in raw:raise ValueError('RDF byte/encoding bound')
 raw.decode('utf-8-sig','strict')
 if re.search(br'<!\s*(?:DOCTYPE|ENTITY)',raw,re.I):raise ValueError('RDF DTD/entities refused')
 declaration=re.search(br'<\?xml[^?]*encoding\s*=\s*[\"\']([^\"\']+)',raw,re.I)
 if declaration and declaration.group(1).lower() not in {b'utf-8',b'utf8'}:raise ValueError('NonUTF8 declaration')
 root=etree.fromstring(raw,etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False,huge_tree=False),base_url='https://www.gutenberg.org/')
 if root.tag!='{'+RDF+'}RDF' or root.get('{'+XML+'}base') not in {'http://www.gutenberg.org/','https://www.gutenberg.org/'}:raise ValueError('Explicit official RDF root/xmlbase required')
 nodes=0;stack=[(root,0)]
 while stack:
  n,depth=stack.pop();nodes+=1
  if nodes>MAX_NODES or depth>MAX_DEPTH:raise ValueError('RDF node/depth bound')
  stack.extend((c,depth+1) for c in n)
 books=root.findall('pg:ebook',NS)
 if len(books)!=1:raise ValueError('Exactly one native ebook per RDF member required')
 book=books[0];original=book.get('{'+RDF+'}about','');url=resolve(book,original);bookid=native_identity(url,'ebook');holds=[]
 match=re.search(r'(?:^|/)pg([1-9][0-9]*)\.rdf$',member)
 if match and int(match.group(1))!=bookid:holds.append('member_filename_ebook_ID_mismatch')
 titles=[text(x) for x in book.findall('d:title',NS)];languages=[typed_values(x) for x in book.findall('d:language',NS)];langset=sorted({v for n in languages for v in n['values']});types=[typed_values(x) for x in book.findall('d:type',NS)];typevals=sorted({v for n in types for v in n['values']})
 if len(titles)!=1 or not titles[0]:holds.append('missing_or_ambiguous_title')
 if not langset:holds.append('language_metadata_missing')
 if not typevals:holds.append('type_metadata_missing')
 agents=[];unresolved=[];handled=set()
 for role in book:
  if not isinstance(role.tag,str):continue
  children=role.findall('pg:agent',NS)
  if children:handled.add(role.tag)
  for agent in children:
   about=agent.get('{'+RDF+'}about','');authority=resolve(agent,about) if about else None;aid=None;aholds=[]
   try:aid=native_identity(authority,'agent') if authority else None
   except ValueError:aholds.append('agent_authority_unresolved')
   if aid is None:aholds.append('stable_agent_ID_missing')
   fields=[node_info(x) for x in agent if isinstance(x.tag,str)]
   names=[text(x) for x in agent.findall('pg:name',NS)]
   if not names:aholds.append('agent_name_missing')
   agents.append({'role_qualified_name':role.tag,'original_authority':about,'resolved_authority':authority,'stable_agent_ID':aid,'names':names,'birthdates':[text(x) for x in agent.findall('pg:birthdate',NS)],'deathdates':[text(x) for x in agent.findall('pg:deathdate',NS)],'all_native_agent_fields':fields,'holds':sorted(set(aholds))})
  if role.tag in {'{'+DCT+'}creator','{'+DCT+'}contributor'} or role.tag.startswith('{'+REL+'}'):
   handled.add(role.tag)
   if not children:unresolved.append(node_info(role))
 creators=[x for x in agents if x['role_qualified_name']=='{'+DCT+'}creator']
 if not creators:holds.append('primary_creator_metadata_missing_or_unresolved')
 if unresolved:holds.append('unresolved_contributor_role_or_reference')
 if any(x['holds'] for x in agents):holds.append('agent_identity_or_name_missing')
 formats=[]
 for f in book.findall('d:hasFormat/pg:file',NS):
  target=f.get('{'+RDF+'}about','');resolved=resolve(f,target);extent=f.findtext('d:extent',namespaces=NS);fh=[]
  u=urlsplit(resolved)
  if not target or u.scheme not in {'http','https'} or not u.hostname or u.username or u.password:fh.append('format_URL_missing_or_not_plain_HTTP_reference')
  try:extentnum=int(extent);assert extentnum>=0
  except (ValueError,TypeError,AssertionError):extentnum=None;fh.append('format_extent_missing_or_invalid')
  mimes=[text(x) for x in f.findall('d:format//rdf:value',NS)];isformats=[resolve(x,x.get('{'+RDF+'}resource','')) for x in f.findall('d:isFormatOf',NS)]
  try:
   if not isformats or any(native_identity(u,'ebook')!=bookid for u in isformats):fh.append('format_source_identity_mismatch_or_missing')
  except ValueError:fh.append('format_source_identity_mismatch_or_missing')
  if not mimes:fh.append('format_MIME_missing')
  formats.append({'original_URL':target,'resolved_URL':resolved,'MIME_values':mimes,'original_extent':extent,'extent_bytes':extentnum,'modified_values':[text(x) for x in f.findall('d:modified',NS)],'isFormatOf_URLs':isformats,'native_subtree_SHA256':sha(etree.tostring(f,encoding='utf-8',with_tail=False)),'holds':sorted(set(fh))})
 if not formats:holds.append('format_metadata_missing')
 excluded=[{'qualified_name':n.tag,'original_text_SHA256':sha(text(n).encode()),'characters':len(text(n)),'reason':'Catalog description/summary never becomes human-prose intake.'} for n in book if n.tag in {'{'+DCT+'}description','{'+PG+'}marc520'}]
 known_qualified={('{'+DCT+'}'+k) for k in ['publisher','license','issued','rights','creator','title','description','language','subject','type','hasFormat','alternative','hasPart','isPartOf','relation','contributor']}|{('{'+PG+'}'+k) for k in ['downloads','bookshelf','marc508','marc520','marc908']}
 unknown=[{'qualified_name':n.tag,'attributes':dict(n.attrib),'native_subtree_SHA256':sha(etree.tostring(n,encoding='utf-8',with_tail=False))} for n in book if isinstance(n.tag,str) and n.tag not in known_qualified and n.tag not in handled]
 if unknown:holds.append('unmapped_native_book_fields_preserved_as_hashes')
 return {'ebook_ID':bookid,'original_ebook_rdf_about':original,'resolved_ebook_URL':url,'explicit_root_xmlbase':root.get('{'+XML+'}base'),'member':member,'member_RDF_SHA256':sha(raw),'titles':titles,'languages':langset,'typed_language_fields':languages,'types':typevals,'typed_type_fields':types,'subjects':[typed_values(x) for x in book.findall('d:subject',NS)],'bookshelves':[typed_values(x) for x in book.findall('pg:bookshelf',NS)],'contributors_and_all_roles':agents,'unresolved_contributor_fields':unresolved,'formats':formats,'PG_issued_dates':[text(x) for x in book.findall('d:issued',NS)],'original_print_dates_and_edition':'UNKNOWN_NOT_INFERRED_FROM_PG_RELEASE','rights_fields':[node_info(x) for x in book if x.tag in {'{'+DCT+'}rights','{'+DCT+'}license'}],'native_relations_and_credits':[node_info(x) for x in book if x.tag in {'{'+DCT+'}alternative','{'+DCT+'}hasPart','{'+DCT+'}isPartOf','{'+DCT+'}relation','{'+PG+'}marc508'}],'excluded_description_summary_fields':excluded,'unmapped_book_fields':unknown,'holds':sorted(set(holds)),'metadata_English_Text_view':langset==['en'] and typevals==['Text'],'original_English_composition':'UNVERIFIED','edition_and_jurisdiction_rights':'UNVERIFIED','training_admitted':False,'book_body_fetched':False}
