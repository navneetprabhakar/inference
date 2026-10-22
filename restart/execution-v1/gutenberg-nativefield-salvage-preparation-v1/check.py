"""Synthetic additions to existing nativePG1342 fixture; no claim actual four values reviewed."""
import copy,json
from pathlib import Path
from lxml import etree
import add_fields as a
ROOT=Path(__file__).resolve().parent.parent;raw=(ROOT/'m2-intake/gutenberg-discovery-pilot-v2/metadata.raw').read_bytes();tree=etree.fromstring(raw);book=tree.find('pg:ebook',a.parse_rdf.NS)
for tag,value in [('marc250','SYNTHETIC edition statement, 2nd ed.'),('marc260','SYNTHETIC Place : Publisher, [1901?]'),('marc260','SYNTHETIC second statement')]:
 node=etree.SubElement(book,'{'+a.parse_rdf.PG+'}'+tag);node.text=value
synthetic=etree.tostring(tree);original=a.parse_rdf.parse(synthetic,'pg1342.rdf');result=a.add_native_fields(synthetic,original);fields=result['native_edition_publication_additions_v1']['fields'];cases=[]
def test(name,ok):assert ok,name;cases.append(name)
def refuse(fn):
 try:fn()
 except Exception:return True
 return False
test('three_repeated_native_occurrences_preserved',len(fields)==3 and fields[-1]['XML_path'].endswith('[2]'))
test('exact_uncertain_native_text_not_parsed_into_date',fields[1]['text_exact_itertext'].endswith('[1901?]'))
test('all_old_metadata_holds_and_unknown_fields_unchanged',result['holds']==original['holds'] and result['unmapped_book_fields']==original['unmapped_book_fields'])
test('all_original_keys_values_equal',all(result[k]==v for k,v in original.items()))
test('no_rights_or_originalEnglish_clearance',not result['native_edition_publication_additions_v1']['rights_clearance'] and result['original_English_composition']=='UNVERIFIED')
test('changed_body_refused',refuse(lambda:a.add_native_fields(synthetic+b' ',original)))
bad=copy.deepcopy(original);bad['unmapped_book_fields'][0]['native_subtree_SHA256']='0'*64;test('changed_old_unknown_field_hash_refused',refuse(lambda:a.add_native_fields(synthetic,bad)))
Path(__file__).with_name('checks.json').write_text(json.dumps({'status':'PASS','cases':cases,'count':len(cases),'fixtures_synthetic':True,'actual_four_native_values_available':False},indent=2)+'\n');print(len(cases),'PASS')
