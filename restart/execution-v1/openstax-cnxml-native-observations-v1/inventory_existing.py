"""Offline complete162 actual native schema/rights/dependency observations.
Requires independent successful source acquisition first. No semantic renderer.
"""
import collections,hashlib,json,re,time
from pathlib import Path
from lxml import etree
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;SOURCE=EXEC/'m2-intake/openstax-world-history-native-source-v1';OUT=HERE/'complete162-observations'
POLICY=EXEC/'openstax-native-source-preparation-v2/policy.json';POLICY_SHA='7a8a5126dc31cff7d4e5638d31aa77599bc5f5a66febf80962fd69db9a8855c3'
CNXML='http://cnx.rice.edu/cnxml';MD='http://cnx.rice.edu/mdml';CAP=64000000;SECONDS=60
RIGHTS=re.compile(r'copyright|all rights reserved|used (?:with|by) permission|permission of|licensed under|fair use|except (?:as|where)|CC BY|Creative Commons',re.I)
def sha(b):return hashlib.sha256(b).hexdigest()
def loc(n):return etree.QName(n).localname if isinstance(n.tag,str) else ''
def payload(data):return (json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
def main():
 start=time.monotonic();proof=SOURCE/'independent-terminal-verification.json';receipt=json.loads(proof.read_text())
 assert receipt['status']=='PASS_COMPLETE162_RAW_NATIVE_SOURCE_ACQUISITION_ONLY'
 assert sha(POLICY.read_bytes())==POLICY_SHA;policy=json.loads(POLICY.read_text());rows=[];global_tags=collections.Counter();global_attrs=collections.Counter();namespaces=collections.Counter()
 for item in policy['items']:
  if time.monotonic()-start>SECONDS:raise TimeoutError('Offline inventory deadline')
  path=SOURCE/(item['module_ID']+'.cnxml');assert not path.is_symlink()
  with path.open('rb') as f:raw=f.read(1000001)
  assert len(raw)==item['expected_bytes'] and hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==item['expected_Git_blob_SHA1']
  if b'\0' in raw or re.search(br'<!\s*(?:DOCTYPE|ENTITY)',raw,re.I):raise ValueError('Unsafe XML')
  root=etree.fromstring(raw,etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False,huge_tree=False));tree=root.getroottree();tags=collections.Counter();ids=collections.defaultdict(list);links=[];media=[];tables=[];math=[];rights=[];gloss=[];licenses=[]
  for node in root.iter():
   if not isinstance(node.tag,str):continue
   q=etree.QName(node);name=q.localname;tags[node.tag]+=1;global_tags[node.tag]+=1;namespaces[str(q.namespace)]+=1
   for k in node.attrib:global_attrs[node.tag+'/@'+k]+=1
   if node.get('id'):ids[node.get('id')].append({'path':tree.getpath(node),'qualified_name':node.tag})
   entry={'path':tree.getpath(node),'qualified_name':node.tag,'attributes':dict(node.attrib),'subtree_XML_SHA256':sha(etree.tostring(node,encoding='utf-8',with_tail=False))}
   if name=='link':links.append({**entry,'native_label_text':''.join(node.itertext()),'empty_label':not ''.join(node.itertext()).strip(),'unresolved_embedded_exercise':node.get('class')=='os-embed' and (node.get('url') or '').startswith('#exercise/')})
   if name in {'image','media','figure'}:media.append(entry)
   if name in {'table','tgroup','thead','tbody','row','entry'}:tables.append(entry)
   if q.namespace=='http://www.w3.org/1998/Math/MathML' or name in {'equation'}:math.append(entry)
   if name in {'license','copyright','attribution','credit','credits','author','authors','licensor','permission','permissions'}:
    licenses.append({**entry,'original_text':''.join(node.itertext()),'original_XML':etree.tostring(node,encoding='unicode',with_tail=False),'scope':'Exact observed native field; module/object application not automatically established.'})
   if name in {'caption','para','quote','cite','citation'}:
    text=''.join(node.itertext());match=RIGHTS.search(text)
    if match:rights.append({**entry,'original_text':text,'review_scope':'Potential notice/quotation/objectcredit only, not clearance.'})
   if name=='definition':gloss.append({**entry,'direct_child_qualified_names':[c.tag for c in node if isinstance(c.tag,str)],'term_texts':[''.join(c.itertext()) for c in node if loc(c)=='term'],'meaning_texts':[''.join(c.itertext()) for c in node if loc(c)=='meaning'],'boundary_preservation_required':True})
  unresolved=[];resolved=[]
  for l in links:
   target=l['attributes'].get('target-id');doc=l['attributes'].get('document')
   if target and not doc:
    (resolved if len(ids.get(target,[]))==1 else unresolved).append({'link_path':l['path'],'target-id':target,'matches':ids.get(target,[]),'scope':'Native withinmodule ID reference only; image/text missingness still separate.'})
  rows.append({'module_ID':item['module_ID'],'source_SHA256':sha(raw),'source_Git_blob_SHA1':item['expected_Git_blob_SHA1'],'root_qualified_name':root.tag,'root_attributes':dict(root.attrib),'native_metadata_content_IDs':root.xpath('.//md:content-id/text()',namespaces={'md':MD}),'native_metadata_UUIDs':root.xpath('.//md:uuid/text()',namespaces={'md':MD}),'qualified_node_counts':dict(tags),'links':links,'media_and_figures':media,'table_structures':tables,'math_structures':math,'observed_rights_fields':licenses,'potential_rights_credit_spans':rights,'glossary_definitions':gloss,'withinmodule_ID_links_resolved':resolved,'withinmodule_ID_links_unresolved':unresolved,'duplicate_native_IDs':{k:v for k,v in ids.items() if len(v)>1},'embedded_exercise_missing_content_count':sum(l['unresolved_embedded_exercise'] for l in links),'empty_native_link_label_count':sum(l['empty_label'] for l in links),'collection_appearances':item['collection_appearances'],'full_document_semantic_review':False,'rights_clearance':False,'training_admitted':False})
 rawrows=(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows)).encode()
 summary={'status':'COMPLETE162_NATIVE_SCHEMA_AND_DEPENDENCY_DISCOVERY_ONLY','source_acquisition_verification_SHA256':sha(proof.read_bytes()),'policy_SHA256':POLICY_SHA,'module_count':len(rows),'collection_appearances':sum(len(r['collection_appearances']) for r in rows),'actual_root_qualified_name_counts':dict(collections.Counter(r['root_qualified_name'] for r in rows)),'observed_namespaces':dict(namespaces),'qualified_node_counts':dict(global_tags),'qualified_attribute_counts':dict(global_attrs),'embedded_exercise_missing_content_count':sum(r['embedded_exercise_missing_content_count'] for r in rows),'modules_with_missing_embedded_exercises':sum(bool(r['embedded_exercise_missing_content_count']) for r in rows),'empty_native_link_labels':sum(r['empty_native_link_label_count'] for r in rows),'modules_with_native_rights_fields':sum(bool(r['observed_rights_fields']) for r in rows),'withinmodule_unresolved_ID_links':sum(len(r['withinmodule_ID_links_unresolved']) for r in rows),'glossary_definitions':sum(len(r['glossary_definitions']) for r in rows),'inventory_SHA256':sha(rawrows),'full_document_semantic_reviews':0,'rights_clearances':0,'new_admitted_documents':0,'new_admitted_tokens':0,'external_resources_fetched':0,'limitations':['Exactsource-bound complete schema inventory is not quality acceptance or a trainingexport.','All embeddedquestions/mediaexternalresources remainunfetched; missingcontent cannotbe silentlystripped.','Local IDresolution proves referenceidentity only; visiblelabel/figurecontent maystillneedrepresentation.','License/objectcredit observations require scope/rightsreview, not a blanket sourceclearance.']}
 rawsummary=payload(summary)
 if len(rawrows)+len(rawsummary)>CAP:raise ValueError('Inventory output bound before write')
 OUT.mkdir(exist_ok=False)
 for name,data in [('module-inventory.jsonl',rawrows),('summary.json',rawsummary)]:
  with (OUT/name).open('xb') as f:f.write(data)
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
