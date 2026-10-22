"""Narrow additive native XML capture. Does NOT remove any original hold."""
import base64,copy,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'gutenberg-catalog-compact-preparation-v2'))
import parse_rdf
from lxml import etree
TARGETS={'{'+parse_rdf.PG+'}marc250','{'+parse_rdf.PG+'}marc260'}
def add_native_fields(raw,original):
 assert hashlib.sha256(raw).hexdigest()==original['member_RDF_SHA256'],'Exact original RDF body required'
 reparsed=parse_rdf.parse(raw,original['member']);assert reparsed==original,'Pinned original parser/source JSON equality required'
 root=etree.fromstring(raw,etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False,huge_tree=False))
 book=root.find('pg:ebook',parse_rdf.NS);fields=[];seen={}
 for node in book:
  if node.tag not in TARGETS:continue
  xml=etree.tostring(node,encoding='utf-8',with_tail=False);digest=hashlib.sha256(xml).hexdigest()
  assert any(u['qualified_name']==node.tag and u['native_subtree_SHA256']==digest and u['attributes']==dict(node.attrib) for u in original['unmapped_book_fields']),'Original unknown-field hash binding required'
  seen[node.tag]=seen.get(node.tag,0)+1
  fields.append({'qualified_name':node.tag,'attributes':dict(node.attrib),'XML_path':'/rdf:RDF/pgterms:ebook/pgterms:'+node.tag.split('}')[1]+'['+str(seen[node.tag])+']','namespace_bindings':dict(node.nsmap),'text_exact_itertext':''.join(node.itertext()),'serialized_XML_UTF8_base64':base64.b64encode(xml).decode(),'native_subtree_SHA256':digest,'semantic_interpretation':'UNVERIFIED_NATIVE_EDITION_OR_PUBLICATION_STATEMENT_NOT_RIGHTS_CLEARANCE'})
 result=copy.deepcopy(original);result['native_edition_publication_additions_v1']={'fields':fields,'source_RDF_SHA256':original['member_RDF_SHA256'],'old_unknown_fields_and_holds_unchanged':True,'rights_clearance':False,'original_print_dates_not_automatically_inferred':True}
 assert result['holds']==original['holds'] and result['unmapped_book_fields']==original['unmapped_book_fields']
 return result
