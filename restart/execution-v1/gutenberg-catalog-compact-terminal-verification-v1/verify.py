"""Read-only complete stored-field/index/native-identity and original-prefix verifier.
Run only after parent confirms terminal; no source archive reparsing or network.
"""
import hashlib,json,pathlib,sqlite3,sys,time,zlib
from urllib.parse import urlsplit
P=pathlib.Path(__file__).resolve().parent;E=P.parent;PREP=E/'gutenberg-catalog-compact-preparation-v2';sys.path.insert(0,str(PREP));import compact as c
EXPECTED='659f01bfed7f887306f44f634456d1c75f57596e4cc7f4586b4f04dc9135db87';D=c.DEST;OUT=E/'m2-intake/gutenberg-catalog-compact-independent-verification-v1'
h=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def independently_unpack(rawbytes,rawhash,packedhash,codec,blob):
 if type(rawbytes) is not int or not 0<=rawbytes<=16000000 or codec!=c.CODEC:raise ValueError('Unexpected length/codec')
 if hashlib.sha256(blob).hexdigest()!=packedhash:raise ValueError('Compressed hash mismatch')
 decoder=zlib.decompressobj();raw=decoder.decompress(blob,rawbytes+1)
 if len(raw)!=rawbytes or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data or hashlib.sha256(raw).hexdigest()!=rawhash:raise ValueError('Lossless hash/stream/length mismatch')
 return json.loads(raw)
def main():
 start=time.monotonic();c.pins(EXPECTED);worker=json.loads((D/'worker-result.json').read_text());sup=json.loads((D/'supervisor-result.json').read_text())
 if sup['status']!='COMPLETE' or worker['status']!='COMPLETE_LOSSLESS_COMPACT_CATALOG_METADATA_ONLY_NO_ADMISSION':raise RuntimeError('Parent-confirmed COMPLETE terminal evidence required')
 OUT.mkdir(exist_ok=False)
 assert sup['worker_exit_code']==0 and sup['reason'] is None and sup['worker_result_SHA256']==h(D/'worker-result.json') and worker['manifest_SHA256']==sup['manifest_SHA256']==EXPECTED;assert sup['elapsed_seconds']<=600 and sup['peak_observed_process_tree_RSS_bytes']<=1000000000
 stats=worker['stats'];assert stats['full_tar_EOF_verified'] and stats['full_bzip2_CRC_EOF_verified'];assert stats['members']<=150000 and stats['actual_decoded_tar_bytes']<=4000000000;assert worker['network_requests']==worker['ledger_mutations']==worker['book_bodies_fetched']==worker['new_admitted_documents']==worker['new_admitted_tokens']==0
 paths=[D/f'catalog-{i}.sqlite3' for i in range(2)];before={str(p):h(p) for p in paths};assert len(worker['database_shards'])==2 and {x['file'] for x in worker['database_shards']}=={p.name for p in paths}
 for shard in worker['database_shards']:
  p=D/shard['file'];assert p.stat().st_size==shard['bytes'] and h(p)==shard['SHA256'] and p.stat().st_size<=300000000
  db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);assert db.execute('pragma page_size').fetchone()[0]==65536;assert db.execute('pragma integrity_check').fetchone()[0]=='ok';db.close()
 assert sum(p.stat().st_size for p in paths)<=600000000 and c.size(D)<=1000000000 and not list(D.glob('*.sqlite3-journal'));union=c.readonly_union(paths);union.execute('pragma temp_store=MEMORY');union.execute('pragma cache_size=-4096')
 member_count=0;bodybytes=0;record_count=0;prefix_records=0;prefix_members=0;hold_deltas=[];codecs=set();counted_English=0;missing_language=0;missing_type=0;holds=0
 # Reconcile all native members, without relying only on total count.
 previous=0;held_members=[]
 for row in union.execute('select ordinal,name,bytes,body_hash,hold,raw_bytes,raw_hash,packed_hash,codec,payload from members order by ordinal'):
  ordinal,name,n,bodyhash,hold,*packed=row;meta=independently_unpack(*packed);assert ordinal==previous+1;previous=ordinal
  assert meta['ordinal']==ordinal and meta['name']==name and meta['size']==n and meta['body_SHA256']==bodyhash and meta['hold']==hold;assert len(bodyhash)==len(meta['header_SHA256'])==64;member_count+=1;bodybytes+=n
  if hold:held_members.append({'native_member_ordinal':ordinal,'name':name,'source_RDF_bytes':n,'source_body_SHA256':bodyhash,'hold':hold,'source_header_SHA256':meta['header_SHA256']})
 assert member_count==stats['members'] and bodybytes==stats['member_body_bytes']
 duplicate_ids={eid for eid, in union.execute('select ebook_ID from records group by ebook_ID having count(*)>1')};assert len(duplicate_ids)==stats['duplicate_ebook_ID_groups']
 for row in union.execute('select member,ebook_ID,English_Text,types,languages,missing_mask,missingness,hold_count,raw_bytes,raw_hash,packed_hash,codec,payload from records order by member'):
  if time.monotonic()-start>=285:raise TimeoutError('285second terminal verification cap')
  member,eid,English,types,languages,mask,missingness,hold_count,*packed=row;record=independently_unpack(*packed);codecs.add(packed[3]);assert eid==record['ebook_ID']==c.parse_rdf.native_identity(record['resolved_ebook_URL'],'ebook');assert (English,types,languages,mask,missingness,hold_count)==c.indexes(record);assert record['member_RDF_SHA256']==union.execute('select body_hash from members where ordinal=?',(member,)).fetchone()[0]
  native_name=union.execute('select name from members where ordinal=?',(member,)).fetchone()[0];assert record['member']==native_name;assert record['training_admitted'] is False and record['book_body_fetched'] is False and record['original_English_composition']=='UNVERIFIED' and record['edition_and_jurisdiction_rights']=='UNVERIFIED'
  assert (eid in duplicate_ids)==('duplicate_native_ebook_ID_in_catalog_requires_family_reconciliation' in record['holds'])
  for agent in record['contributors_and_all_roles']:
   if agent['stable_agent_ID'] is not None:assert c.parse_rdf.native_identity(agent['resolved_authority'],'agent')==agent['stable_agent_ID']
  record_count+=1;counted_English+=English;missing_language+=bool(mask&1);missing_type+=bool(mask&2);holds+=hold_count>0
 assert record_count==stats['parsed_ebook_records']==stats['lossless_record_roundtrips'];assert counted_English==stats['English_Text_metadata_rows'] and missing_language==stats['rows_with_missing_language_metadata'] and missing_type==stats['rows_with_missing_type_metadata'] and holds==stats['rows_with_metadata_holds']
 original=sqlite3.connect((c.ORIGINAL/'catalog.sqlite3').as_uri()+'?mode=ro',uri=True)
 for member,eid,payload in original.execute('select member,ebook_ID,data from records order by member'):
  old=json.loads(payload);rows=union.execute('select ebook_ID,raw_bytes,raw_hash,packed_hash,codec,payload from records where member=?',(member,)).fetchall();assert len(rows)==1 and rows[0][0]==eid;new=independently_unpack(*rows[0][1:])
  if new!=old:
   prior=set(old['holds']);later=set(new['holds']);allowed='duplicate_native_ebook_ID_in_catalog_requires_family_reconciliation';assert later==prior|{allowed} and eid in duplicate_ids;copy=dict(new,holds=old['holds']);assert copy==old;hold_deltas.append({'member':member,'ebook_ID':eid,'sole_change':'new globally reconciled duplicate-ID hold'})
  else:assert hashlib.sha256(payload.encode()).hexdigest()==rows[0][2]
  prefix_records+=1
 for ordinal,payload in original.execute('select ordinal,data from members order by ordinal'):
  rows=union.execute('select raw_bytes,raw_hash,packed_hash,codec,payload from members where ordinal=?',(ordinal,)).fetchall();assert len(rows)==1 and independently_unpack(*rows[0])==json.loads(payload);prefix_members+=1
 assert prefix_records==35998;original.close();union.close();assert all(h(pathlib.Path(p))==v for p,v in before.items());c.pins(EXPECTED)
 result={'status':'PASS_COMPLETE_STORED_CATALOG_FIELDS_IDENTITIES_QUERY_INDEXES_AND_PREFIX_PARITY_NO_ADMISSION','external_manifest_SHA256':EXPECTED,'worker_receipt_SHA256':h(D/'worker-result.json'),'supervisor_receipt_SHA256':h(D/'supervisor-result.json'),'all_native_members_verified':member_count,'all_member_body_bytes_reconciled':bodybytes,'all_lossless_native_record_payloads_verified':record_count,'all_original_prefix_records_compared':prefix_records,'held_member_identities':held_members,'all_potential_RDF_parsed':stats['all_potential_RDF_records_parsed_without_duplicate_ID'],'all_original_prefix_members_compared':prefix_members,'prefix_expected_duplicate_hold_deltas':hold_deltas,'all_native_ebook_and_resolved_agent_IDs_verified':True,'every_query_index_matches_lossless_payload':True,'strict_tar_EOF_bzip2_CRC_evidence_verified':True,'EOF_scope':'Pinned captured source hash and complete worker strict-reader EOF/CRC evidence reconciled; independent terminal pass does not decompress/reparse the archive a second time.','all_original_pinned_inputs_unchanged':True,'all_output_shards_unchanged':True,'shard_SHA256':before,'complete_archive_identity_not_originalEnglish_or_rights_clearance':True,'elapsed_seconds':time.monotonic()-start,'new_admitted_documents':0,'new_admitted_tokens':0,'network_requests':0,'ledger_mutations':0};(OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');manifest={'verifier_SHA256':h(pathlib.Path(__file__)),'verification_SHA256':h(OUT/'verification.json')};(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
