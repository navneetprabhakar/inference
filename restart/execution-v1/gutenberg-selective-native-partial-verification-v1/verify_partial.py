"""Independent offline terminal verification, never launches/selects/network fetches."""
import base64,gzip,hashlib,json,os,re,sqlite3,sys,time,xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;PREP=EXEC/'gutenberg-selective-native-preparation-v1';OUT=EXEC/'m2-intake/gutenberg-selective-native-six-v1';SOURCE=EXEC/'m2-intake/gutenberg-complete-native-catalog-compact-v2'
sys.path.insert(0,str(EXEC/'gutenberg-catalog-compact-preparation-v2'));import compact as c
EXPECTED='e7c4147196112baf1353ea3c8bcab856756f5fd15fad2fd456c8034ef3426f07';COMPACT='659f01bfed7f887306f44f634456d1c75f57596e4cc7f4586b4f04dc9135db87'
checks=[]
def check(name,ok):
 if not ok:raise AssertionError(name)
 checks.append(name)
def file_sha(path):
 h=hashlib.sha256()
 with path.open('rb') as file:
  for block in iter(lambda:file.read(65536),b''):h.update(block)
 return h.hexdigest()
def frozen_manifest(path,expected):
 check(path.name+'_container_'+expected[:8],file_sha(path)==expected);manifest=json.loads(path.read_text())
 for name,digest in manifest['files_SHA256'].items():
  path=Path(name);check('unchanged_input:'+name,not path.is_symlink() and path.is_file() and file_sha(path)==digest)
 return manifest
started=time.monotonic();frozen_manifest(PREP/'manifest.json',EXPECTED);frozen_manifest(c.HERE/'manifest.json',COMPACT)
worker=json.loads((OUT/'worker-result.json').read_text());supervisor=json.loads((OUT/'supervisor-result.json').read_text());targets=json.loads((PREP/'targets.json').read_text())['targets']
check('terminal_source_worker_and_supervisor_success',worker['status']=='TERMINAL_FAILED_NO_RETRY' and worker['error']=='decoded_byte_cap' and supervisor['status']=='FAILED' and supervisor['worker_exit_code']==1)
check('manifest_worker_supervisor_binding',supervisor['manifest_SHA256']==EXPECTED and supervisor['worker_result_SHA256']==file_sha(OUT/'worker-result.json'))
check('bounded_clock_and_observed_RSS',0<=worker['elapsed_seconds']<55 and worker['elapsed_seconds']<=supervisor['elapsed_seconds']<60 and supervisor['peak_observed_process_tree_RSS_bytes']<=1000000000)
check('original_terminal_failure_hash_preserved',file_sha(OUT/'worker-result.json')=='64be7145a563cb8e567c5b3108b24dc6709573392d5ccf2f9d721bf49db3da0c')
check('uncommitted_last_target_absent',not (OUT/'ordinal-27090.rdf').exists() and not (OUT/'ordinal-27090.receipt.json').exists())
targets=[r for r in targets if r['ordinal']!=27090];check('only_five_partial_bodies_verified',len(targets)==5)
check('no_network_admission_retry',worker['network_requests']==supervisor['network_requests']==0 and worker['new_admitted_documents']==supervisor['new_admitted_documents']==0 and supervisor['retry'] is False)
source_worker=json.loads((SOURCE/'worker-result.json').read_text());source=c.readonly_union([SOURCE/r['file'] for r in source_worker['database_shards']]);expected_files={'worker-result.json','supervisor-result.json','worker.log'};evidence=[]
try:
 for target in targets:
  ordinal=target['ordinal'];prefix='ordinal-'+str(ordinal);rawpath=OUT/(prefix+'.rdf');receiptpath=OUT/(prefix+'.receipt.json');expected_files.update([rawpath.name,receiptpath.name]);raw=rawpath.read_bytes();receipt=json.loads(receiptpath.read_text())
  check(str(ordinal)+'_exact_raw_length_SHA',len(raw)==target['bytes'] and len(raw)<=2000000 and file_sha(rawpath)==target['body_SHA256'])
  native=source.execute('select raw_bytes,raw_hash,packed_hash,codec,payload from members where ordinal=?',(ordinal,)).fetchone();member=c.unpack(*native)
  check(str(ordinal)+'_complete_source_identity_header_binding',all(member[k]==target[v] for k,v in [('ordinal','ordinal'),('name','name'),('size','bytes'),('body_SHA256','body_SHA256'),('header_SHA256','header_SHA256')]))
  check(str(ordinal)+'_receipt_worker_binding',receipt['target']=={k:v for k,v in target.items() if k!='original_record'} and receipt['raw_body_verified'] is True and receipt['source_archive_SHA256']==c.ARCHIVE_SHA and receipt['training_admitted'] is False)
  for artifact in receipt['artifacts']:
   path=OUT/artifact['file'];check(str(ordinal)+'_artifact_'+artifact['file'],path.name==artifact['file'] and path.stat().st_size==artifact['bytes'] and file_sha(path)==artifact['SHA256'])
  root=ET.fromstring(raw);books=root.findall('{'+c.parse_rdf.PG+'}ebook');check(str(ordinal)+'_independent_XML_identity',root.tag=='{'+c.parse_rdf.RDF+'}RDF' and len(books)==1 and root.get('{'+c.parse_rdf.XML+'}base') in {'http://www.gutenberg.org/','https://www.gutenberg.org/'})
  about=books[0].get('{'+c.parse_rdf.RDF+'}about');eid=int(re.fullmatch(r'(?:https?://(?:www\.)?gutenberg\.org/)?ebooks/([1-9][0-9]*)',about).group(1));check(str(ordinal)+'_native_ID_filename',target['name'].endswith('/pg'+str(eid)+'.rdf'))
  if target['kind']=='OVERSIZE_DERIVED_PARSE_ONLY':
   check(str(ordinal)+'_original_oversize_hold_unchanged',member['hold']=='oversize_RDF_member_not_parsed' and source.execute('select count(*) from records where member=?',(ordinal,)).fetchone()[0]==0)
   path=OUT/(prefix+'.derived-metadata.json.gz');expected_files.add(path.name)
   # Bound decompression before JSON parsing; native parse node/depth limits unchanged.
   with gzip.open(path,'rb') as file:body=file.read(16000001);tail=file.read(1)
   check(str(ordinal)+'_derived_bounded_JSON',len(body)<=16000000 and not tail);derived=json.loads(body)
   with patch.object(c.parse_rdf,'MAX_BYTES',2000000):fresh=c.parse_rdf.parse(raw,target['name'])
   check(str(ordinal)+'_all_derived_fields_equal_original_parser_only2MB',derived==fresh and derived['ebook_ID']==eid)
   check(str(ordinal)+'_native_unknown_holds_and_no_rights_clearance',receipt['holds']==derived['holds'] and receipt['unknown_fields']==derived['unmapped_book_fields'] and derived['edition_and_jurisdiction_rights']=='UNVERIFIED' and derived['original_English_composition']=='UNVERIFIED' and derived['training_admitted'] is False)
   evidence.append({'ordinal':ordinal,'ebook_ID':eid,'derived_JSON_SHA256':hashlib.sha256(body).hexdigest(),'holds':derived['holds'],'unmapped_fields':derived['unmapped_book_fields'],'source_hold_retained':member['hold']})
  else:
   original=target['original_record'];fresh=c.parse_rdf.parse(raw,target['name']);check(str(ordinal)+'_all_original_metadata_unchanged',fresh==original)
   check(str(ordinal)+'_old_holds_roles_unchanged',receipt['original_holds_unchanged']==original['holds'] and receipt['native_roles_all']==original['contributors_and_all_roles'])
   additions=receipt['native_edition_publication_additions_v1'];fields=additions['fields'];nodes=[n for n in books[0] if n.tag in {'{'+c.parse_rdf.PG+'}marc250','{'+c.parse_rdf.PG+'}marc260'}]
   check(str(ordinal)+'_all_native_fields_captured',len(nodes)==len(fields)>0)
   for node,field in zip(nodes,fields):
    xml=base64.b64decode(field['serialized_XML_UTF8_base64'],validate=True);xmlnode=ET.fromstring(xml);check(str(ordinal)+'_native_value_XML_hash_binding',field['qualified_name']==node.tag==xmlnode.tag and field['text_exact_itertext']==''.join(node.itertext())==''.join(xmlnode.itertext()) and field['native_subtree_SHA256']==hashlib.sha256(xml).hexdigest() and any(u['qualified_name']==node.tag and u['native_subtree_SHA256']==field['native_subtree_SHA256'] for u in original['unmapped_book_fields']))
   check(str(ordinal)+'_addition_not_rights_or_date_clearance',additions['rights_clearance'] is False and additions['old_unknown_fields_and_holds_unchanged'] is True and additions['original_print_dates_not_automatically_inferred'] is True)
   evidence.append({'ordinal':ordinal,'ebook_ID':eid,'native_fields':fields,'original_holds_retained':original['holds']})
finally:source.close()
check('exact_output_inventory',{p.name for p in OUT.iterdir() if p.is_file()}==expected_files)
outputbytes=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file());check('aggregate_output_caps',outputbytes<=8000000-1048576)
try:os.kill(supervisor['worker_pid'],0)
except ProcessLookupError:gone=True
else:gone=False
check('worker_process_terminal',gone)
# Rehash immutable source manifests again after all verification reads.
frozen_manifest(PREP/'manifest.json',EXPECTED);frozen_manifest(c.HERE/'manifest.json',COMPACT)
result={'status':'PASS_FIVE_PARTIAL_BODIES_ONLY_ORIGINAL_RUN_TERMINAL_FAILURE_PRESERVED','checks':checks,'check_count':len(checks),'output_bytes':outputbytes,'source_archive_SHA256':c.ARCHIVE_SHA,'worker_result_SHA256':file_sha(OUT/'worker-result.json'),'supervisor_result_SHA256':file_sha(OUT/'supervisor-result.json'),'evidence':evidence,'elapsed_verification_seconds':time.monotonic()-started,'network_requests':0,'archive_passes':0,'new_admitted_documents':0,'new_admitted_tokens':0,'full_archive_EOF_claim':False,'original_run_status':'FAILED_DECODED_BYTE_CAP_NO_RETRY','committed_selected_bodies':5,'requested_selected_bodies':6,'last_uncommitted_ordinal':27090}
(HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n');(HERE/'manifest.json').write_text(json.dumps({'files_SHA256':{p.name:file_sha(p) for p in [HERE/'verify_partial.py',HERE/'verification.json']},'no_training_or_admission':True},indent=2)+'\n');print(json.dumps({'status':result['status'],'check_count':len(checks),'output_bytes':outputbytes,'manifest_SHA256':file_sha(HERE/'manifest.json'),'evidence_brief':[{'ordinal':r['ordinal'],'ebook_ID':r['ebook_ID'],'holds':r.get('holds',r.get('original_holds_retained')),'field_values':[f['text_exact_itertext'] for f in r.get('native_fields',[])]} for r in evidence]}))
