"""Read-only dependency inventory, not rendering/extraction or eligibility change."""
from pathlib import Path
import sys,json,hashlib,collections,time,signal
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[1];ROOT=BASE/'m2-intake';SOURCE=ROOT/'enwiki-native20-generic-AST-development-v4';TARGET=BASE/'tool-dependencies/mwparserfromhell-0.7.2'
H=lambda b:hashlib.sha256(b).hexdigest()
def run():
 start=time.monotonic();signal.signal(signal.SIGALRM,lambda s,f:(_ for _ in ()).throw(TimeoutError('inventory30seconds')));signal.alarm(30)
 try:
  manifest=json.loads((HERE/'input-pins.json').read_text())
  for path,h in manifest['files'].items():assert H(Path(path).read_bytes())==h
  sys.path.insert(0,str(TARGET));import mwparserfromhell as m
  assert m.__version__=='0.7.2' and m.parser.use_c and Path(m.__file__).resolve().is_relative_to(TARGET)
  pages=[];templates=collections.Counter();tags=collections.Counter();namespace_links=collections.Counter();occurrences=[];parsedbytes=0;nodecount=0
  for q in sorted(SOURCE.glob('row-*.json')):
   obj=json.loads(q.read_text())
   if obj['preserved_role']!='pending':continue
   page={'row':obj['row_ordinal'],'title':obj['native_title'],'source_SHA256':obj['source_text_SHA256'],'sections':[]}
   for section in obj['frame']['sections']:
    raw=section['raw'];parsedbytes+=len(raw.encode());assert parsedbytes<=114599;code=m.parse(raw);assert str(code)==raw;sectioncounts=collections.Counter();items=[]
    def walk(code,path,top):
     nonlocal nodecount
     for i,node in enumerate(code.nodes):
      nodecount+=1
      if nodecount>30000:raise ValueError('node30000cap')
      kind=type(node).__name__;sectioncounts[kind]+=1;p=path+[i];entry=None
      if kind=='Template':
       name=str(node.name).strip();templates[name]+=1;entry={'kind':kind,'name_literal':name,'parameter_names':[str(x.name) for x in node.params],'positional_flags':[not x.showkey for x in node.params]}
      elif kind=='Tag':
       name=str(node.tag);tags[name]+=1;entry={'kind':kind,'name_literal':name,'attribute_names':[str(x.name) for x in node.attributes],'self_closing':bool(node.self_closing),'wiki_markup':node.wiki_markup}
      elif kind=='Wikilink':
       target=str(node.title);ns=target.split(':',1)[0] if ':' in target else None
       if ns:namespace_links[ns]+=1;entry={'kind':kind,'namespace_prefix_literal':ns,'explicit_label':node.text is not None}
      elif kind=='Argument':entry={'kind':kind,'name_literal':str(node.name)}
      if entry is not None:
       entry.update({'row':obj['row_ordinal'],'section':section['section_ordinal'],'nested_AST_path':p,'top_node_source_byte_span':top['source_byte_span'],'top_node_SHA256':top['raw_SHA256'],'node_literal_SHA256':H(str(node).encode())});occurrences.append(entry);items.append(len(occurrences)-1)
      for j,child in enumerate(node.__children__()):walk(child,p+['child',j],top)
    # Each saved topnode bound independently; no substring-inferred nestedoffsets.
    assert len(code.nodes)==len(section['top_nodes'])
    for i,(node,top) in enumerate(zip(code.nodes,section['top_nodes'])):
     assert str(node)==top['raw'] and H(str(node).encode())==top['raw_SHA256'];single=m.parse(str(node));walk(single,[i],top)
    page['sections'].append({'section':section['section_ordinal'],'source_byte_span':section['source_byte_span'],'raw_SHA256':section['raw_SHA256'],'original_structural_holds':section['holds'],'node_counts':dict(sectioncounts),'dependency_occurrence_indexes':items})
   pages.append(page)
  assert len(pages)==5 and sum(len(p['sections']) for p in pages)==27
  result={'status':'COMPLETE_READONLY_NATIVE5_DEPENDENCY_INVENTORY_NO_RENDERING','scope':'Existing saved27sections only; no newsourceextraction, preview, tokenization, policyapplication oradmission. Nestedpaths anchored to exacttopnode spans/hash, not claimedexactnestedbyteoffsets.','source_bytes_AST_introspected':parsedbytes,'AST_nodes_observed':nodecount,'template_names_counts':dict(templates.most_common()),'tag_names_counts':dict(tags.most_common()),'namespace_prefix_counts':dict(namespace_links.most_common()),'pages':pages,'dependency_occurrences':occurrences,'elapsed_seconds':time.monotonic()-start,'new_admitted_documents':0}
  raw=(json.dumps(result,indent=2,ensure_ascii=False)+'\n').encode();assert len(raw)+sum(p.stat().st_size for p in HERE.iterdir() if p.is_file())<2000000
  (HERE/'inventory.json').write_bytes(raw)
  for path,h in manifest['files'].items():assert H(Path(path).read_bytes())==h
  print('inventorySHA',H(raw));print('bytes',len(raw));print('sourcebytes',parsedbytes);print('nodes',nodecount);print('templates',dict(templates.most_common()));print('tags',dict(tags.most_common()));print('namespace',dict(namespace_links))
 finally:signal.alarm(0)
if __name__=='__main__':run()
