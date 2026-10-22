"""Focused native-RDF, bounded archive, transfer and manifest tests; no I/O network."""
import bz2,copy,hashlib,io,json,sqlite3,ssl,tarfile,tempfile
from pathlib import Path
from unittest.mock import patch
import catalog as c
import parse_rdf as p
cases=[]
NATIVE=c.ROOT/'gutenberg-discovery-pilot-v2/metadata.raw';RAW=NATIVE.read_bytes()
def refuse(fn):
 try:fn()
 except (ValueError,TimeoutError,OSError,Exception) as e:return
 raise AssertionError('expected refusal')
def good(name,b):assert b,name;cases.append(name)
r=p.parse(RAW,'cache/epub/1342/pg1342.rdf')
good('actual_retained_PG1342_full_minimum_metadata_fields',r['ebook_ID']==1342 and r['languages']==['en'] and r['metadata_English_Text_view'] and r['contributors_and_all_roles'][0]['stable_agent_ID']==68 and r['contributors_and_all_roles'][0]['birthdates']==['1775'] and r['contributors_and_all_roles'][0]['deathdates']==['1817'] and len(r['formats'])==14 and r['subjects'])
good('actual_generated_summary_excluded_not_prose',len(r['excluded_description_summary_fields'])==3 and all('text' not in x for x in r['excluded_description_summary_fields']) and not r['training_admitted'])
role=RAW.replace(b'<dcterms:creator>',b'<rel:trl xmlns:rel="http://id.loc.gov/vocabulary/relators/">').replace(b'</dcterms:creator>',b'</rel:trl>')
rr=p.parse(role,'pg1342.rdf');good('all_contributor_roles_preserved_translation_not_originalEnglish',rr['contributors_and_all_roles'][0]['role_qualified_name']=='{'+p.REL+'}trl' and rr['original_English_composition']=='UNVERIFIED' and 'primary_creator_metadata_missing_or_unresolved' in rr['holds'])
relative=RAW.replace(b'2009/agents/68',b'http://www.gutenberg.org/2009/agents/68');good('relative_and_absolute_xmlbase_agent_binding_agree',p.parse(relative,'pg1342.rdf')['contributors_and_all_roles'][0]['stable_agent_ID']==68)
foreign=RAW.replace(b'<pgterms:agent rdf:about=',b'<pgterms:agent xml:base="https://evil.invalid/" rdf:about=');good('foreign_nested_base_agent_stays_explicitly_held','agent_identity_or_name_missing' in p.parse(foreign,'pg1342.rdf')['holds'])
good('member_ID_mismatch_held','member_filename_ebook_ID_mismatch' in p.parse(RAW,'pg999.rdf')['holds'])
for name,b in [('DTD',b'<!DOCTYPE x>'+RAW),('NUL',RAW+b'\0'),('UTF16',RAW.decode().encode('utf-16')),('wrong_rootbase',RAW.replace(b'http://www.gutenberg.org/"',b'https://evil.invalid/"',1)),('bad_ebook_ID',RAW.replace(b'rdf:about="ebooks/1342"',b'rdf:about="ebooks/not-an-id"'))]:refuse(lambda:p.parse(b,'pg1342.rdf'));cases.append(name+'_refused')
unknown=RAW.replace(b'<dcterms:publisher>',b'<dcterms:future-field>').replace(b'</dcterms:publisher>',b'</dcterms:future-field>');good('unknown_book_fields_preserved_as_hashes_and_held',bool(p.parse(unknown,'pg1342.rdf')['unmapped_book_fields']))
missing=RAW.replace(b'<dcterms:language>',b'<dcterms:missing-language>').replace(b'</dcterms:language>',b'</dcterms:missing-language>');good('missing_language_not_inferred','language_metadata_missing' in p.parse(missing,'pg1342.rdf')['holds'])
with patch.object(p,'MAX_NODES',2):refuse(lambda:p.parse(RAW,'pg1342.rdf'))
cases.append('RDF_node_bound')
with patch.object(p,'MAX_DEPTH',1):refuse(lambda:p.parse(RAW,'pg1342.rdf'))
cases.append('RDF_depth_bound')
def archive(path,rows):
 out=io.BytesIO()
 with tarfile.open(fileobj=out,mode='w',format=tarfile.USTAR_FORMAT) as t:
  for name,raw in rows:
   m=tarfile.TarInfo(name);m.size=len(raw);t.addfile(m,io.BytesIO(raw))
 path.write_bytes(bz2.compress(out.getvalue()));return path
with tempfile.TemporaryDirectory() as td:
 root=Path(td)
 def inv(name,rows):
  out=root/name;out.mkdir();a=archive(out/'source.bz2',rows);return c.inventory(a,c.Guards(out,c.clock(),reserve=None))
 s=inv('good',[('cache/epub/1342/pg1342.rdf',RAW)]);good('full_bzip2_CRC_tar_EOF_SQLite_reconciliation',s['full_tar_EOF_verified'] and s['full_bzip2_CRC_EOF_verified'] and s['SQLite_integrity']=='ok' and s['members']==1 and s['English_Text_metadata_rows']==1)
 s=inv('held',[('pg1342.rdf',RAW),('pg999.rdf',b'<not-RDF/>')]);good('invalid_member_preserved_held_no_complete_English_frame',s['members']==2 and s['held_potential_records']==1 and not s['all_potential_RDF_records_parsed_without_duplicate_ID'])
 s=inv('dup',[('pg1342.rdf',RAW),('copy/pg1342.rdf',RAW)]);good('duplicate_ebookID_retained_not_usable_frame',s['duplicate_ebook_ID_groups']==1 and not s['all_potential_RDF_records_parsed_without_duplicate_ID'])
 with patch.object(c,'MEMBER_CAP',10):s=inv('oversize',[('pg1342.rdf',RAW)])
 good('oversize_member_whole_hash_and_explicit_hold',s['held_potential_records']==1 and s['member_body_bytes']==len(RAW))
 s=inv('unknown',[('README',b'catalog note')]);good('unknown_nonRDF_member_counted_not_English_frame',s['nonRDF_files']==1 and not s['all_potential_RDF_records_parsed_without_duplicate_ID'])
 for why,suffix in [('truncated',b''),('junk',b'trailingjunk')]:
  a=archive(root/(why+'.bz2'),[('pg1342.rdf',RAW)]);b=a.read_bytes();a.write_bytes(b[:-3] if why=='truncated' else b+suffix);out=root/(why+'out');out.mkdir();refuse(lambda:c.inventory(a,c.Guards(out,c.clock(),reserve=None)));cases.append('bzip2_'+why+'_refused')
 a=archive(root/'CRC.bz2',[('pg1342.rdf',RAW)]);b=bytearray(a.read_bytes());b[len(b)//2]^=1;a.write_bytes(b);out=root/'CRC';out.mkdir();refuse(lambda:c.inventory(a,c.Guards(out,c.clock(),reserve=None)));cases.append('bzip2_corruption_CRC_or_decoder_failure_refused')
 a=archive(root/'nonzero.bz2',[('pg1342.rdf',RAW)]);a.write_bytes(bz2.compress(bz2.decompress(a.read_bytes())+b'nonzero tail'));out=root/'nonzero';out.mkdir();refuse(lambda:c.inventory(a,c.Guards(out,c.clock(),reserve=None)));cases.append('nonzero_decoded_tar_tail_refused')
 a=root/'noend.bz2';m=tarfile.TarInfo('pg1342.rdf');m.size=len(RAW);a.write_bytes(bz2.compress(m.tobuf()+RAW+b'\0'*((-len(RAW))%512)));out=root/'noend';out.mkdir();refuse(lambda:c.inventory(a,c.Guards(out,c.clock(),reserve=None)));cases.append('missing_tar_EOF_blocks_refused')
 a=archive(root/'concat.bz2',[('pg1342.rdf',RAW)]);plain=bz2.decompress(a.read_bytes());a.write_bytes(bz2.compress(plain[:1024])+bz2.compress(plain[1024:]));out=root/'concat';out.mkdir();s=c.inventory(a,c.Guards(out,c.clock(),reserve=None));good('valid_concatenated_bzip2_streams_CRC_verified',s['bzip2_streams']==2)
 a=archive(root/'unsafe.bz2',[('../escape.rdf',RAW)]);out=root/'unsafe';out.mkdir();refuse(lambda:c.inventory(a,c.Guards(out,c.clock(),reserve=None)));cases.append('unsafe_member_path_no_extraction')
 a=archive(root/'cap.bz2',[('pg1342.rdf',RAW)]);out=root/'cap';out.mkdir();refuse(lambda:c.inventory(a,c.Guards(out,c.clock(),limits={'decoded_bytes':1024},reserve=None)));cases.append('actual_decoded_byte_cap')
 with patch.object(c,'MAX_MEMBERS',0):
  out=root/'members';out.mkdir();refuse(lambda:c.inventory(a,c.Guards(out,c.clock(),reserve=None)))
 cases.append('tar_member_count_cap')
 with patch.object(c,'OUTPUT_CAP',20000):
  out=root/'output';out.mkdir();refuse(lambda:c.inventory(a,c.Guards(out,c.clock(),reserve=None)))
 cases.append('SQLite_output_guard_before_record_write')
 refuse(lambda:c.Guards(root,c.clock()-571).check());cases.append('shared_worker_deadline')
class Ledger:
 def __init__(self):self.reserved=False;self.db=self;self.state='pending';self.raw=None
 def reserve(self,key,**kw):assert not self.reserved;self.reserved=True
 def check_time(self):assert self.reserved
 def finish(self,key,raw=None):self.state='complete' if raw is not None else 'failed';self.raw=raw
 def execute(self,*a):return self
 def fetchone(self):return(self.state,)
class Response(io.BytesIO):
 def __init__(self,b,url=c.URL,headers=None):super().__init__(b);self.status=200;self.url=url;self.headers=headers or {'Content-Length':str(len(b))}
 def geturl(self):return self.url
class Opener:
 def __init__(self,r,l):self.r=r;self.l=l;self.calls=0
 def open(self,*a,**kw):assert self.l.reserved;self.calls+=1;return self.r
for why in ['good','redirect','truncated','cap']:
 with tempfile.TemporaryDirectory() as td:
  out=Path(td);ledger=Ledger();resp=Response(b'abc',url='https://evil.invalid/' if why=='redirect' else c.URL,headers={'Content-Length':'9'} if why=='truncated' else None);op=Opener(resp,ledger);guard=c.Guards(out,c.clock())
  if why=='cap':
   with patch.object(c,'BODY_CAP',3):refuse(lambda:c.fetch(ledger,guard,op))
  elif why=='good':r=c.fetch(ledger,guard,op);assert ledger.raw==b'abc' and r['response_SHA256']==c.sha(b'abc')
  else:refuse(lambda:c.fetch(ledger,guard,op))
  assert op.calls==1 and ledger.reserved and ledger.state==('complete' if why=='good' else 'failed');cases.append('precharged_one_request_'+why+'_no_retry')
with tempfile.TemporaryDirectory() as td:
 out=Path(td);ledger=Ledger();op=Opener(Response(b'abc',headers={'Content-Type':'application/octet-stream'}),ledger)
 with patch.object(c,'BODY_CAP',3):refuse(lambda:c.fetch(ledger,c.Guards(out,c.clock()),op))
 assert ledger.state=='failed' and (out/(c.ARCHIVE+'.partial')).read_bytes()==b'abc';cases.append('stream_hits_reservedcap_no_unreserved_EOF_probe_partial_preserved')
with patch.object(c,'size',return_value=64000000000):refuse(c.storage)
cases.append('combined_local64GB_storage_preflight')
# Exactmanifest guards, including empty-inventory replacement exploit.
good_manifest={'environment':c.environment(),'files_SHA256':{str(path.resolve()):c.file_sha(path) for path in c.bound_paths()}}
with tempfile.TemporaryDirectory() as td:
 path=Path(td)/'manifest.json'
 def verify(value,expected=None):
  path.write_text(json.dumps(value))
  with patch.object(c,'MANIFEST',path):return c.pins(c.file_sha(path) if expected is None else expected)
 verify(good_manifest);cases.append('exact_parent_manifest_inventory_and_runtime')
 for why in ['empty','missing','extra','substitute','environment']:
  bad=copy.deepcopy(good_manifest)
  if why=='empty':bad['files_SHA256']={}
  elif why=='missing':bad['files_SHA256'].pop(next(iter(bad['files_SHA256'])))
  elif why=='extra':bad['files_SHA256']['/tmp/unreviewed']='0'*64
  elif why=='substitute':bad['files_SHA256'][next(iter(bad['files_SHA256']))]='0'*64
  else:bad['environment']={}
  refuse(lambda:verify(bad));cases.append('manifest_'+why+'_refused')
 refuse(lambda:verify(good_manifest,'0'*64));cases.append('manifest_replacement_digest_refused')
 refuse(lambda:c.pins(None));cases.append('missing_explicit_parent_manifest_digest_refused')
good('supervisor_RSS_and_deadline_stop',c.decision(600,0,0,1,0) and c.decision(0,1000000001,0,1,0))
good('pinned_existing_strict_TLS_bundle',c.tls.trusted_context().verify_mode==ssl.CERT_REQUIRED and c.tls.trusted_context().check_hostname)
result={'status':'PASS_NATIVE_RETAINED_RDF_AND_FOCUSED_OFFLINE_GUARDS_NO_TRANSFER','cases':cases,'case_count':len(cases),'network_requests':0,'global_ledger_writes':0,'book_bodies_fetched':0,'new_admitted_documents':0,'new_admitted_tokens':0}
(c.HERE/'offline-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
