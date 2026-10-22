"""Conservative section renderer. Import only after caller pins isolated parser origin.
No strip_code, template expansion, source mutation or admissibility decision.
"""
import hashlib, html, re

def H(s): return hashlib.sha256(s.encode('utf8')).hexdigest()
class Hold(Exception): pass

def project(code):
 out=[]
 for node in code.nodes:
  name=type(node).__name__
  if name=='Text':
   s=str(node)
   # Unparsed syntax is not silently treated as ordinary prose.
   if re.search(r'(?m)^\s*(?:[#*:;{|!]|----)|\[\[|\]\]|\{\{|\}\}|<|>',s):raise Hold('unresolved_text_syntax_or_list_table')
   out.append(s)
  elif name=='Wikilink':
   target=str(node.title)
   if not target.strip() or ':' in target or target.startswith('#'):raise Hold('namespace_media_category_or_fragment_link')
   if node.text is None:
    if any(c in target for c in '_#|'):raise Hold('implicit_link_display_needs_rule')
    out.append(target)
   else:
    if not str(node.text).strip():raise Hold('empty_piped_display')
    out.append(project(node.text))
  elif name=='ExternalLink':
   url=str(node.url)
   if not re.fullmatch(r'https?://[^\s<>\[\]]+',url):raise Hold('nonliteral_or_unsupported_external_URL')
   if node.title is None:
    if bool(node.brackets):raise Hold('numbered_unlabelled_reference_needs_render_context')
    out.append(url)
   else:out.append(project(node.title)+' ('+url+')')
  elif name=='HTMLEntity':
   rendered=html.unescape(str(node))
   if rendered==str(node) or '\x00' in rendered:raise Hold('unknown_or_invalid_HTML_entity')
   out.append(rendered)
  elif name=='Comment':
   # Inverse is the exact section/top-node ledger, not a guessed replacement.
   pass
  elif name=='Heading':out.append(project(node.title).strip()+'\n')
  elif name=='Tag':
   tag=str(node.tag).lower()
   if node.attributes:raise Hold('tag_attributes_need_profile')
   if tag in ('b','i','em','strong') and not node.self_closing:
    if node.contents.filter_headings(recursive=True):raise Hold('formatting_crosses_section_boundary')
    out.append(project(node.contents))
   elif tag=='br' and node.self_closing:out.append('\n')
   elif tag=='ref':raise Hold('reference_definition_or_reuse_requires_bound_resolver')
   else:raise Hold('unresolved_extension_or_tag:'+tag)
  elif name=='Template':raise Hold('unresolved_template_or_Lua_dependency')
  elif name=='Argument':raise Hold('unresolved_template_argument')
  else:raise Hold('unsupported_AST_node:'+name)
 return ''.join(out)

def sections(source,parser):
 if len(source.encode())>2000000:raise ValueError('source2MBcap')
 code=parser.parse(source)
 if str(code)!=source:raise ValueError('exact_AST_roundtrip')
 # Complete H2 sections include subordinate headings. Lead is a complete separate
 # source region. No first-paragraph crops, substitution or content-driven replacement.
 records=[];pos=0;bytepos=0;current=[];start=0;startbyte=0;nodeledger=[]
 for i,node in enumerate(code.nodes):
  raw=str(node);n=len(raw);nb=len(raw.encode())
  if type(node).__name__=='Heading' and node.level==2 and current:
   records.append((start,pos,startbyte,bytepos,current,nodeledger));current=[];nodeledger=[];start=pos;startbyte=bytepos
  nodeledger.append({'top_node_path':[i],'type':type(node).__name__,'source_char_span':[pos,pos+n],'source_byte_span':[bytepos,bytepos+nb],'raw':raw,'raw_SHA256':H(raw)})
  current.append(raw);pos+=n;bytepos+=nb
 if current:records.append((start,pos,startbyte,bytepos,current,nodeledger))
 if pos!=len(source) or ''.join(''.join(r[4]) for r in records)!=source:raise ValueError('complete_partition_inverse')
 result=[]
 for k,(a,b,ba,bb,raws,ledger) in enumerate(records):
  raw=''.join(raws);unit=parser.parse(raw)
  try:
   preview=project(unit)
   status='STRUCTURAL_PREVIEW_ONLY_NOT_QUALITY_OR_ADMISSION'
   reasons=[]
  except Hold as e:preview=None;status='HELD_COMPLETE_SECTION_NO_PARTIAL_SILENT_DROP';reasons=[str(e)]
  result.append({'section_ordinal':k,'source_char_span':[a,b],'source_byte_span':[ba,bb],'raw':raw,'raw_SHA256':H(raw),'top_nodes':ledger,'preview':preview,'preview_SHA256':H(preview) if preview is not None else None,'status':status,'holds':reasons,'whole_source_family_unchanged':True,'no_admission':True})
 return {'source_SHA256':H(source),'exact_roundtrip':True,'all_source_bytes_partitioned_once':True,'sections':result}
