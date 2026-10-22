"""Only400 existing packed prefix payloads. No archive or network operation."""
import collections,json,sys,time
from pathlib import Path
START=time.monotonic();HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;sys.path.insert(0,str(EXEC/'gutenberg-catalog-compact-preparation-v2'));import compact as c
SOURCE=EXEC/'gutenberg-catalog-storage-projection-v1/sample-page65536.sqlite3';CAP=5000000
expected=json.loads((EXEC/'gutenberg-catalog-storage-projection-v1/page65536-projection.json').read_text())
# Independently pin source once, and compare raw rows to immutable original prefix hash evidence.
sourcehash=c.file_sha(SOURCE);db=c.sqlite3.connect('file:'+str(SOURCE.resolve())+'?mode=ro',uri=True);counts=collections.Counter();cases=[];rows=0;occurrences=[]
try:
 for ordinal,*packed in db.execute('select member,raw_bytes,raw_hash,packed_hash,codec,payload from records order by member'):
  assert time.monotonic()-START<30
  row=c.unpack(*packed);rows+=1
  for field in row['unmapped_book_fields']:
   counts[field['qualified_name']]+=1;occurrences.append({'ordinal':ordinal,'ebook_ID':row['ebook_ID'],'field':field})
   if field['qualified_name'].endswith(('}marc250','}marc260')):
    cases.append({'source_packed_DB_SHA256':sourcehash,'ordinal':ordinal,'source_payload_raw_JSON_SHA256':packed[1],'ebook_ID':row['ebook_ID'],'member':row['member'],'member_RDF_SHA256':row['member_RDF_SHA256'],'titles':row['titles'],'languages':row['languages'],'roles_all_native':row['contributors_and_all_roles'],'rights_fields':row['rights_fields'],'PG_issued_not_print_date':row['PG_issued_dates'],'field':field,'expected_namespace_XML_path':'/rdf:RDF/pgterms:ebook/'+field['qualified_name'].split('}')[1].join(['pgterms:','']),'exact_original_XML_path_unavailable':True,'exact_native_value':'UNAVAILABLE_IN_HASH_ONLY_PAYLOAD','original_native_XML_copied_locally':False,'holds_preserved':row['holds']})
finally:db.close()
assert rows==400 and len(cases)==4
result={'status':'ACTUAL400_PREFIX_FIELD_INVENTORY_COMPLETE_EXACT_VALUES_NOT_RECOVERABLE_FROM_HASH_ONLY_PAYLOAD','source':str(SOURCE.resolve()),'source_SHA256':sourcehash,'records':rows,'fields_by_qualified_name':dict(counts),'unknown_occurrences_total':sum(counts.values()),'four_edition_publication_cases':cases,'exact_value_limit':'Original parser intentionally retained unknown subtree hashes without text/XML; compressed payload is lossless for parsed JSON, not complete native RDF. Authoritative original RDF remains solely in retained archive. Do not fabricate edition/publication strings or infer from PG-issued.','network_requests':0,'archive_passes':0,'new_admitted_documents':0,'elapsed_seconds':time.monotonic()-START}
def save(name,obj):
 b=(json.dumps(obj,indent=2)+'\n').encode();assert sum(p.stat().st_size for p in HERE.iterdir() if p.is_file())+len(b)<=CAP;(HERE/name).write_bytes(b)
save('prefix-nativefield-evidence.json',result);save('all400-unknown-occurrences.json',occurrences);print(json.dumps({'cases':[{'ebook_ID':r['ebook_ID'],'ordinal':r['ordinal'],'field':r['field']} for r in cases],'counts':dict(counts)}))
