"""Offline schema-unverified native XML review views, never training exports.

No actual CNXML body was present when this version was prepared. Every local-name
heuristic is explicitly diagnostic, not an asserted OpenStax schema mapping.
"""
import argparse,collections,hashlib,html,json,re,shutil,time
from pathlib import Path
from urllib.parse import urlsplit
from lxml import etree
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent
POLICY=EXEC/'openstax-native-source-preparation-v1/policy.json'
POLICY_SHA='7a8a5126dc31cff7d4e5638d31aa77599bc5f5a66febf80962fd69db9a8855c3'
MAX_INPUT=1000000;MAX_NODES=50000;MAX_DEPTH=96;MAX_OUTPUT=128000000;MAX_SECONDS=120
CSP="default-src 'none'; script-src 'none'; connect-src 'none'; img-src 'none'; media-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
DEPENDENCY_NAMES={'figure','image','media','table','tgroup','math','equation','link','xref','cite','citation','footnote','list','item','exercise','problem','solution','quote','glossary','term'}
RIGHTS_NAMES={'license','copyright','attribution','credit','credits','author','authors','licensor','permission','permissions','source'}
URI_PATTERN=re.compile(r'https?://(?:www\.)?creativecommons\.org/[^\s<>\"\']+',re.I)
def sha(b):return hashlib.sha256(b).hexdigest()
def git_blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def local(tag):return tag.rsplit('}',1)[-1] if isinstance(tag,str) else ''
def namespace(tag):return tag[1:].split('}',1)[0] if isinstance(tag,str) and tag.startswith('{') else None

def validate_input(raw,expected):
 if not isinstance(raw,bytes) or len(raw)>MAX_INPUT:raise ValueError('Native module input byte bound')
 if b'\0' in raw or re.search(br'<!\s*(?:DOCTYPE|ENTITY)',raw,re.I):raise ValueError('DTD entity or UTF16/32 XML refused')
 if len(raw)!=expected['expected_bytes'] or git_blob(raw)!=expected['expected_Git_blob_SHA1']:raise ValueError('Exact historical module source mismatch')
 return etree.fromstring(raw,etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False,huge_tree=False,remove_comments=False,remove_pis=False))

def render_module(raw,expected):
 root=validate_input(raw,expected);start=time.monotonic();counts=collections.Counter();ns_counts=collections.Counter();deps=[];rights=[];unknown=[];node_count=0
 def walk(node,path,depth):
  nonlocal node_count
  node_count+=1
  if node_count>MAX_NODES or depth>MAX_DEPTH:raise ValueError('XML node/depth bound')
  if time.monotonic()-start>=MAX_SECONDS:raise TimeoutError('Offline render deadline')
  if not isinstance(node.tag,str):
   return {'kind':'comment' if node.tag is etree.Comment else 'processing_instruction','serialized_original_XML':etree.tostring(node,encoding='unicode',with_tail=False),'tail':node.tail}
  tag=node.tag;name=local(tag);attrs=dict(node.attrib);counts[tag]+=1;ns_counts[str(namespace(tag))]+=1
  record={'path':path,'qualified_name':tag,'attributes':attrs,'text':node.text,'tail':node.tail,'children':[]}
  # This version has no verified module schema profile. ALL native names remain
  # explicitly unmapped; the view shows qualified names and preserves nesting.
  unknown.append({'path':path,'qualified_name':tag,'reason':'actual_module_schema_not_yet_verified'})
  if name in DEPENDENCY_NAMES:
   deps.append({'path':path,'qualified_name':tag,'attributes':attrs,'classification':'LOCAL_NAME_HEURISTIC_ONLY_SCHEMA_UNVERIFIED','source_subtree_XML_SHA256':sha(etree.tostring(node,encoding='utf-8',with_tail=False)),'material_preserved_in_original_XML_and_AST':True,'resolution':'UNRESOLVED_NO_NETWORK'})
  for key,value in attrs.items():
   if local(key).lower() in {'href','src','url','document','target-id','resource','ref','idref'}:
    deps.append({'path':path,'attribute_qualified_name':key,'literal_target':value,'classification':'LITERAL_REFERENCE_ATTRIBUTE_HEURISTIC_SCHEMA_UNVERIFIED','resolution':'NOT_FETCHED_NOT_ASSUMED_LOCAL_OR_EXTERNAL'})
  if name.lower() in RIGHTS_NAMES:
   rights.append({'path':path,'qualified_name':tag,'attributes':attrs,'exact_native_subtree_XML':etree.tostring(node,encoding='unicode',with_tail=False),'meaning':'Observed field only; scope and per-object ownership unresolved.'})
  for index,child in enumerate(node):record['children'].append(walk(child,path+'/'+str(index),depth+1))
  return record
 ast=walk(root,'/0',0)
 def ast_text(node):
  if 'kind' in node:return node.get('tail') or ''
  return (node['text'] or '')+''.join(ast_text(x) for x in node['children'])+(node['tail'] or '')
 # root tail is outside the document element and normally absent.
 native_text=''.join(root.itertext());conserved=ast_text(ast)
 if native_text!=conserved:raise ValueError('Original native text/tail conservation failure')
 serialized=etree.tostring(root,encoding='unicode')
 uris=sorted(set(m.group(0).rstrip('.,;)') for m in URI_PATTERN.finditer(serialized)))
 cc=[]
 for uri in uris:
  u=urlsplit(uri);canonical=u.path.rstrip('/')
  cc.append({'original_URI':uri,'canonical_path_for_diagnostic':canonical,'matches_expected_historical_CC_BY4':u.hostname in {'creativecommons.org','www.creativecommons.org'} and canonical=='/licenses/by/4.0' and not u.query and not u.fragment and not u.username and not u.password and not u.port,'clearance':'NOT_GRANTED_BY_THIS_DIAGNOSTIC'})
 holds=['native_CNXML_namespace_and_schema_profile_unverified','all_native_names_unmapped_structure_preserved','full_document_semantic_factual_review_pending','per_module_and_object_rights_review_pending']
 if not any(x['matches_expected_historical_CC_BY4'] for x in cc):holds.append('expected_historical_CC_BY4_URI_not_observed_in_module')
 if any(not x['matches_expected_historical_CC_BY4'] for x in cc):holds.append('other_CC_URI_or_license_scope_conflict_requires_review')
 if deps:holds.append('unresolved_structural_or_reference_dependencies')
 def html_node(node):
  esc=lambda x:html.escape(x or '',quote=True)
  if 'kind' in node:return '<pre class="native-special">'+esc(node['serialized_original_XML'])+'</pre>'+esc(node.get('tail'))
  label=node['qualified_name']+' '+json.dumps(node['attributes'],ensure_ascii=False)
  return '<div class="native-node"><div class="native-label">'+esc(label)+'</div><span class="native-text">'+esc(node['text'])+'</span>'+''.join(html_node(x) for x in node['children'])+'</div>'+esc(node['tail'])
 banner='SCHEMA-UNVERIFIED NATIVE XML REVIEW VIEW. Original XML is authoritative. No training, semantic acceptance or rights clearance.'
 view='<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="'+html.escape(CSP,quote=True)+'"><style>body{font:15px system-ui;margin:24px}.native-node{border-left:1px solid #aaa;margin:6px 0 6px 12px;padding-left:10px}.native-label{font:11px monospace;color:#555}.native-text{white-space:pre-wrap}.native-special{white-space:pre-wrap}</style></head><body><h1>'+html.escape(expected['module_ID'])+'</h1><p>'+banner+'</p>'+html_node(ast)+'</body></html>'
 receipt={'status':'SCHEMA_UNVERIFIED_STRUCTURED_REVIEW_ONLY','module_ID':expected['module_ID'],'native_path':expected['native_path'],'source_original_SHA256':sha(raw),'source_original_Git_blob_SHA1':git_blob(raw),'source_bytes':len(raw),'root_qualified_name':root.tag,'observed_namespace_counts':dict(ns_counts),'qualified_node_counts':dict(counts),'node_count':node_count,'native_text_SHA256':sha(native_text.encode()),'native_text_characters':len(native_text),'all_native_text_and_tails_conserved':True,'unmapped_node_count':len(unknown),'unmapped_nodes':unknown,'dependency_inventory':deps,'rights_field_inventory':rights,'observed_CC_URIs':cc,'holds':holds,'collection_appearances':expected.get('collection_appearances',[]),'new_admitted_documents':0,'new_admitted_tokens':0,'external_resources_fetched':0,'scope':'Generic structural nativeXML review, not schema-confirmed semantic HTML or prose. Tables/math/figures/links remain nested, labeled and unresolved, never stripped or remotely fetched.'}
 return {'AST':ast,'HTML':view.encode(),'receipt':receipt}

class OutputBudget:
 def __init__(self,root,cap=MAX_OUTPUT):self.root=Path(root);self.cap=cap
 def used(self):
  files=list(self.root.rglob('*'))
  if any(p.is_symlink() for p in files):raise ValueError('Output symlink refused')
  return sum(p.stat().st_size for p in files if p.is_file())
 def write_many(self,items,terminal=False):
  reserve=0 if terminal else min(16384,self.cap//4)
  if self.used()+sum(len(raw) for _,raw in items)+reserve>self.cap:raise ValueError('Aggregate output cap before module writes')
  paths=[self.root/name for name,_ in items]
  if any(path.parent.resolve()!=self.root.resolve() or path.exists() for path in paths):raise ValueError('Output path escape or overwrite')
  for path,(_,raw) in zip(paths,items):
   with path.open('xb') as f:f.write(raw)

def render_existing(source,output):
 if sha(POLICY.read_bytes())!=POLICY_SHA:raise ValueError('Exact162 source policy pin')
 policy=json.loads(POLICY.read_text());source=Path(source);output=Path(output)
 disk=json.loads((EXEC/'disk-budget.json').read_text());protected=disk['free_disk_floor_bytes']+disk['weights_checkpoints_reserved_bytes']+disk['scratch_cap_bytes']
 if shutil.disk_usage(output.parent).free<protected+MAX_OUTPUT:raise ValueError('Protected weights scratch freefloor')
 intake=EXEC/'m2-intake'
 if sum(p.stat().st_size for p in intake.rglob('*') if p.is_file())+MAX_OUTPUT>disk['processed_data_cap_bytes']:raise ValueError('Combined64GB processed ceiling')
 output.mkdir(exist_ok=False);budget=OutputBudget(output);started=time.monotonic();receipts=[]
 try:
  for expected in policy['items']:
   if time.monotonic()-started>=MAX_SECONDS:raise TimeoutError('Aggregate offline rendering deadline')
   path=source/(expected['module_ID']+'.cnxml')
   if path.is_symlink():raise ValueError('Source module symlink refused')
   with path.open('rb') as handle:raw=handle.read(MAX_INPUT+1)
   result=render_module(raw,expected)
   mid=expected['module_ID'];items=[(mid+'.AST.json',(json.dumps(result['AST'],ensure_ascii=False)+'\n').encode()),(mid+'.html',result['HTML']),(mid+'.receipt.json',(json.dumps(result['receipt'],ensure_ascii=False,indent=2)+'\n').encode())]
   budget.write_many(items);receipts.append({'module_ID':mid,'source_SHA256':sha(raw),'holds':result['receipt']['holds']})
  summary={'status':'COMPLETE162_SCHEMA_UNVERIFIED_NATIVE_REVIEW_VIEWS_NO_ADMISSION','source_modules':len(receipts),'module_receipts':receipts,'policy_SHA256':POLICY_SHA,'new_admitted_documents':0,'new_admitted_tokens':0,'external_resources_fetched':0}
  budget.write_many([('result.json',(json.dumps(summary,indent=2)+'\n').encode())],terminal=True);return summary
 except BaseException as error:
  budget.write_many([('failure.json',(json.dumps({'status':'PARTIAL_REVIEW_VIEWS_NO_ADMISSION','error':str(error),'completed_modules':len(receipts),'new_admitted_tokens':0})+'\n').encode())],terminal=True);raise

def main():
 p=argparse.ArgumentParser();p.add_argument('--render-existing',action='store_true');p.add_argument('--source',type=Path);p.add_argument('--output',type=Path);args=p.parse_args()
 if not args.render_existing:print(json.dumps({'status':'PREPARED_SYNTHETIC_ONLY_NO_REAL_MODULE_BODY_OBSERVED','no_network':True}));return
 if args.source is None or args.output is None:raise ValueError('Explicit existing source and new output directories required')
 print(json.dumps(render_existing(args.source,args.output)))
if __name__=='__main__':main()
