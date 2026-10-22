"""Observed CNXML development review profile; synthetic reference labels are preview only."""
import collections,hashlib,html,importlib.util,json,pathlib,re,xml.parsers.expat
from lxml import etree
P=pathlib.Path(__file__).resolve().parent;E=P.parent;UP=E/'openstax-cnxml-renderer-preparation-v1/render.py';spec=importlib.util.spec_from_file_location('generic_CNXML_AST',UP);generic=importlib.util.module_from_spec(spec);spec.loader.exec_module(generic)
CN='http://cnx.rice.edu/cnxml';MD='http://cnx.rice.edu/mdml';SOURCE=E/'m2-intake/openstax-world-history-native-source-v1';POLICY=E/'openstax-native-source-preparation-v1/policy.json'
OBS=E/'openstax-cnxml-native-observations-v1/complete162-observations/summary.json';sha=lambda b:hashlib.sha256(b).hexdigest()
def loc(n):return etree.QName(n).localname if isinstance(n.tag,str) else ''
def ws(s):return re.sub(r'\s+',' ',s).strip()
def spans(raw,root):
 records=[];stack=[];parser=xml.parsers.expat.ParserCreate(namespace_separator='}')
 def start(tag,attrs):
  i=parser.CurrentByteIndex;quote=None;j=i
  while j<len(raw):
   ch=raw[j]
   if quote:
    if ch==quote:quote=None
   elif ch in [34,39]:quote=ch
   elif ch==62:break
   j+=1
  records.append({'tag':'{'+tag if '}' in tag else tag,'start':i,'tag_end':j+1,'selfclosing':raw[j-1:j]==b'/'});stack.append(len(records)-1)
 def end(tag):
  row=records[stack.pop()];i=parser.CurrentByteIndex;row['end']=row['tag_end'] if row['selfclosing'] else raw.index(b'>',i)+1
 parser.StartElementHandler=start;parser.EndElementHandler=end;parser.Parse(raw,True);nodes=[n for n in root.iter() if isinstance(n.tag,str)];assert len(nodes)==len(records);mapping={}
 def walk(n,path):
  if isinstance(n.tag,str):mapping[n]={'node_path':path}
  for i,c in enumerate(n):walk(c,path+'/'+str(i))
 walk(root,'/0')
 for n,r in zip(nodes,records):
  assert n.tag==r['tag'];mapping[n].update(source_start_byte=r['start'],source_end_byte=r['end'],source_exact_subtree_sha256=sha(raw[r['start']:r['end']]),source_line=n.sourceline)
 return mapping

def render(raw,expected):
 generic_result=generic.render_module(raw,expected);root=generic.validate_input(raw,expected);mapping=spans(raw,root);observed=json.loads(OBS.read_text())['qualified_node_counts'];unknown=[n.tag for n in root.iter() if isinstance(n.tag,str) and n.tag not in observed]
 if root.tag!='{'+CN+'}document':raise ValueError('Observed CNXML document root required')
 deps=[];blocks=[];holds=set(['development_sample_not_acceptance','full_module_semantic_factual_review_pending','module_and_object_rights_packaging_pending']);ids={n.get('id'):n for n in root.iter() if n.get('id')}
 def dependency(n,kind,**extra):
  deps.append({'kind':kind,**mapping[n],'attributes':dict(n.attrib),**extra,'resolution':'UNFETCHED_OR_VISIBLE_LABEL_UNVERIFIED','training_eligible':False});holds.add(kind)
 def inline(n):
  name=loc(n);out=n.text or ''
  if etree.QName(n).namespace not in [CN,MD]:dependency(n,'unmapped_namespace');return '[UNMAPPED NAMESPACE: '+n.tag+']'+''.join(n.itertext())
  if name=='link':
   label=''.join(n.itertext());target=n.get('url') or n.get('target-id') or n.get('document') or '';attrs=dict(n.attrib)
   if n.get('class')=='os-embed':dependency(n,'unresolved_embedded_question',literal_target=target);return '[UNRESOLVED EMBEDDED QUESTION: '+target+']'
   localtarget=ids.get(n.get('target-id')) if n.get('target-id') else None
   dependency(n,'literal_reference_unresolved_visible_label' if not ws(label) else 'literal_reference_not_fetched',literal_target=target,local_ID_resolved=localtarget is not None,target_node_path=mapping[localtarget]['node_path'] if localtarget is not None else None)
   return label+' [reference: '+json.dumps(attrs,ensure_ascii=False,sort_keys=True)+']' if ws(label) else '[reference: '+json.dumps(attrs,ensure_ascii=False,sort_keys=True)+']'
  if name=='newline':return '\n'
  if name in ['media','image','iframe']:
   dependency(n,'unresolved_media_dependency',literal_target=n.get('src'),literal_alt=n.get('alt'))
   return '[MEDIA '+json.dumps(dict(n.attrib),ensure_ascii=False,sort_keys=True)+']'+''.join(inline(c)+(c.tail or '') for c in n if isinstance(c.tag,str))
  if name in ['sup','sub']:
   dependency(n,'scripted_notation_requires_review');return '['+name+': '+''.join(n.itertext())+']'
  if n.tag not in observed:dependency(n,'unmapped_native_node')
  for c in n:
   if not isinstance(c.tag,str):continue
   boundary='\n' if loc(c) in ['para','list','item','figure','section','title','caption','definition','meaning','term'] and name not in ['para','caption','title','emphasis','quote','term','meaning'] else ''
   out+=boundary+inline(c)+boundary+(c.tail or '')
  return out
 def emit(n,kind=None,text=None):
  value=inline(n) if text is None else text
  if value.strip():blocks.append({'kind':kind or loc(n),'text':value.strip(),**mapping[n],'source_module_sha256':sha(raw),'source_text_is_unnormalized_except_preview_boundaries':True,'synthetic_reference_or_media_markers_are_review_only':True})
 def visit(n):
  name=loc(n)
  if name in ['title','para','caption','quote','footnote','link']:emit(n)
  elif name=='definition':
   term=n.find('{'+CN+'}term');meaning=n.find('{'+CN+'}meaning')
   if term is None or meaning is None:dependency(n,'incomplete_glossary_definition');emit(n,'glossary_definition')
   else:emit(n,'glossary_definition',inline(term)+': '+inline(meaning))
  elif name=='list':
   if n.text and n.text.strip():emit(n,'list_preface',n.text)
   for index,item in enumerate(n):
    if loc(item)=='item':emit(item,'list_item',(''+str(index+1)+'. ' if n.get('list-type')=='enumerated' else '• ')+inline(item))
    else:visit(item)
  elif name in ['media','image','iframe']:emit(n,'media_dependency')
  elif name=='table':
   dependency(n,'table_layout_semantic_review');title=n.find('{'+CN+'}title')
   if title is not None:emit(title,'table_title')
   for caption in n.findall('{'+CN+'}caption'):emit(caption,'table_caption')
   for row in n.iter('{'+CN+'}row'):emit(row,'table_row',' | '.join(inline(x) for x in row if loc(x)=='entry'))
  elif name in ['document','content','section','note','figure','exercise','problem','glossary','item']:
   if n.text and n.text.strip():emit(n,'container_native_text',n.text)
   for c in n:
    if not isinstance(c.tag,str):continue
    if loc(c)=='metadata':continue
    visit(c)
    if c.tail and c.tail.strip():emit(c,'container_tail_native_text',c.tail)
  else:dependency(n,'unmapped_block_structure');emit(n,'unmapped_structure')
 for child in root:
  if loc(child)!='metadata':visit(child)
 if unknown:holds.add('unmapped_native_nodes')
 text='\n\n'.join(x['text'] for x in blocks);view='<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>Development preview</title><style>body{font:16px system-ui;max-width:1000px;margin:30px auto}pre{white-space:pre-wrap}small{color:#555}section{border-top:1px solid #ccc;padding:10px}</style><h1>'+html.escape(expected['module_ID'])+'</h1><p>DEVELOPMENT REVIEW ONLY. Bracketed references/media are explicit editorial diagnostics, never training prose. All dependency-bearing paragraphs remain held.</p>'
 for b in blocks:view+='<section><small>'+html.escape(b['kind']+' '+b['node_path'])+'</small><pre>'+html.escape(b['text'])+'</pre></section>'
 result={'status':'OBSERVED_CNXML_DEVELOPMENT_PREVIEW_NOT_ADMITTED','module_ID':expected['module_ID'],'source_sha256':sha(raw),'source_Git_blob_SHA1':generic.git_blob(raw),'source_bytes':len(raw),'profile':'observed_cnxml_qualified_names_v1','collection_appearances':expected['collection_appearances'],'family_id':'openstax:world-history-2024-both-volumes','blocks':blocks,'dependencies':deps,'holds':sorted(holds),'original_native_text_and_tails_conserved_in_AST':True,'unmapped_node_names':sorted(set(unknown)),'preview_characters':len(text),'preview_bytes':len(text.encode()),'preview_token_count':None,'training_admitted':False}
 return result,text,view,generic_result['AST']
