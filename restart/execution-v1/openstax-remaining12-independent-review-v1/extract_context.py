import hashlib,json
from pathlib import Path
from lxml import etree
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;SOURCE=EXEC/'m2-intake/openstax-world-history-native-source-v1';CN='{http://cnx.rice.edu/cnxml}';rows=json.loads((EXEC/'openstax-factual-span-overlay-v3/remaining-development-candidates.json').read_text());output=[]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def path(n):
 indices=[]
 while n.getparent() is not None:parent=n.getparent();indices.append(parent.index(n));n=parent
 return '/0'+''.join('/'+str(i) for i in reversed(indices))
def record(n):return {'node_path':path(n),'native_id':n.get('id'),'qualified_name':n.tag,'itertext':''.join(n.itertext()),'serialized_subtree_SHA256':sha(etree.tostring(n,with_tail=False))}
for item in rows:
 raw=(SOURCE/(item['module_ID']+'.cnxml')).read_bytes();assert sha(raw)==item['source_module_SHA256'];piece=raw[item['source_start_byte']:item['source_end_byte']];assert sha(piece)==item['source_exact_subtree_sha256'];root=etree.fromstring(raw);node=root
 for index in item['node_path'].split('/')[2:]:node=node[int(index)]
 assert node.tag==CN+'section';allnodes=list(root.iter());position=allnodes.index(node);end=max(allnodes.index(n) for n in node.iter())
 def substantive(n):
  return n.tag==CN+'para' and ''.join(n.itertext()).strip() and not any(a.get('class') in {'learning-objectives','review-questions','critical-thinking','section-summary'} or a.tag in {CN+'problem',CN+'exercise'} for a in n.iterancestors())
 prior=[n for n in allnodes[:position] if substantive(n)];after=[n for n in allnodes[end+1:] if substantive(n)];openers=[n for n in allnodes if substantive(n)][:2]
 context=[];seen=set()
 for role,nodes in [('module_opening',openers),('nearest_preceding',prior[-2:]),('nearest_following',after[:2])]:
  for n in nodes:
   if path(n) not in seen:context.append({'context_role':role,**record(n)});seen.add(path(n))
 output.append({'source':item,'whole_section_text_itertext':''.join(node.itertext()),'whole_section_XML':piece.decode(),'section_nodes':[{'tag':n.tag,'id':n.get('id'),'attributes':dict(n.attrib)} for n in node.iter()],'context':context,'native_module_outline':[{'node_path':path(n),'title':''.join(n.find(CN+'title').itertext()) if n.find(CN+'title') is not None else None} for n in root.iter(CN+'section')]})
(HERE/'source-bound-reading-packet.json').write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n')
print(len(output),'sourcebound sections')
