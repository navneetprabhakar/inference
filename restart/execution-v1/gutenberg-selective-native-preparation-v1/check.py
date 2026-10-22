"""Small synthetic tar fixture; no actual prefix execution."""
import bz2,copy,gzip,io,json,tarfile,tempfile
from pathlib import Path
from unittest.mock import patch
import selective as s
cases=[]
def test(name,ok):assert ok,name;cases.append(name)
def refuse(fn):
 try:fn()
 except Exception:return True
 return False
raw=(s.EXEC/'m2-intake/gutenberg-discovery-pilot-v2/metadata.raw').read_bytes();tree=s.c.etree.fromstring(raw);book=tree.find('pg:ebook',s.add_fields.parse_rdf.NS);node=s.c.etree.SubElement(book,'{'+s.add_fields.parse_rdf.PG+'}marc250');node.text='SYNTHETIC uncertain edition [1901?]';raw=s.c.etree.tostring(tree)
original=s.add_fields.parse_rdf.parse(raw,'pg1342.rdf')
with tempfile.TemporaryDirectory() as temporary:
 root=Path(temporary);archive=root/'six.bz2';buffer=io.BytesIO();targets=[]
 with tarfile.open(fileobj=buffer,mode='w',format=tarfile.USTAR_FORMAT) as tar:
  for ordinal in range(1,7):
   name=str(ordinal)+'/pg1342.rdf';info=tarfile.TarInfo(name);info.size=len(raw);tar.addfile(info,io.BytesIO(raw));record=copy.deepcopy(original);record['member']=name
   targets.append({'ordinal':ordinal,'name':name,'bytes':len(raw),'body_SHA256':s.c.sha(raw),'header_SHA256':s.c.sha(info.tobuf(format=tarfile.USTAR_FORMAT)),'original_record':record if ordinal<=4 else None,'kind':'NATIVE_250_260_CAPTURE_ONLY' if ordinal<=4 else 'OVERSIZE_DERIVED_PARSE_ONLY'})
 archive.write_bytes(bz2.compress(buffer.getvalue()));out=root/'output';out.mkdir();result=s.scan(archive,targets,s.Guard(out,s.c.clock()),stop_at=6)
 test('six_targets_exact_raw_length_hash_and_receipts',result['selected_members']==6 and result['selected_body_bytes']==6*len(raw) and len(list(out.glob('*.rdf')))==6)
 test('intentional_prefix_no_fullEOF_claim',not result['full_tar_EOF_verified'] and not result['full_bzip2_CRC_EOF_verified'] and result['stop_after_ordinal']==6)
 test('four_native_additions_exact_original_unknownholds',all(r['native_edition_publication_additions_v1']['fields'][0]['text_exact_itertext']==node.text and r['original_holds_unchanged']==original['holds'] for r in result['results'][:4]))
 test('two_new_derived_metadata_no_original_admission',all(r['derived_status'].startswith('PARSED_WITH') and r['rights']=='UNVERIFIED' and not r['training_admitted'] for r in result['results'][4:]))
 for ordinal in [5,6]:
  record=json.loads(gzip.decompress((out/('ordinal-'+str(ordinal)+'.derived-metadata.json.gz')).read_bytes()));test('derived_allroles_and_unknownholds_'+str(ordinal),record['contributors_and_all_roles']==original['contributors_and_all_roles'] and record['holds']==original['holds'])
 for label,key,value in [('bodyhash','body_SHA256','0'*64),('headerhash','header_SHA256','0'*64),('name','name','wrong.rdf'),('length','bytes',len(raw)+1)]:
  bad=copy.deepcopy(targets);bad[0][key]=value;output=root/label;output.mkdir();test(label+'_tamper_stops',refuse(lambda:s.scan(archive,bad,s.Guard(output,s.c.clock()),stop_at=6)))
 output=root/'decoded';output.mkdir();guard=s.Guard(output,s.c.clock());guard.limits['decoded_bytes']=1024;test('decoded_cap_before_target',refuse(lambda:s.scan(archive,targets,guard,stop_at=6)))
 output=root/'outputcap';output.mkdir()
 with patch.object(s,'OUTPUT',10000),patch.object(s,'HEADROOM',1000):test('aggregate_prewrite_output_cap',refuse(lambda:s.scan(archive,targets,s.Guard(output,s.c.clock()),stop_at=6)) and not list(output.glob('*.rdf')))
 test('deadline_guard',refuse(lambda:s.Guard(output,s.c.clock()-56).check()))
 bad=copy.deepcopy(targets);bad[0]['bytes']=2000001;test('2MB_selected_member_cap',refuse(lambda:s.scan(archive,bad,s.Guard(output,s.c.clock()),stop_at=6)))
old=(s.c.HERE/'parse_rdf.py').read_text();new=(s.HERE/'parse_rdf_2MB.py').read_text();test('only2MBparser_bytebound_changed',old.replace('MAX_BYTES=1000000;','MAX_BYTES=2000000;')==new)
test('oldparser_source_unchanged',s.c.file_sha(s.c.HERE/'parse_rdf.py')=='2b06c87a1c0c75b4ebc82f229ab87c7a44d55dced7d6f1de705a901cfb79ae1e')
(s.HERE/'checks.json').write_text(json.dumps({'status':'PASS','count':len(cases),'cases':cases,'actual_archive_passes':0,'network_requests':0},indent=2)+'\n');print(len(cases),'PASS')
# Explicit parent manifest digest AND exact inventory, never an untrusted mutable empty map.
good={'environment':s.c.environment(),'files_SHA256':{str(p.resolve()):s.c.file_sha(p) for p in s.bound_paths()}}
with tempfile.TemporaryDirectory() as td:
 manifest=Path(td)/'manifest.json'
 def verify(m,digest=None):
  manifest.write_text(json.dumps(m))
  with patch.object(s,'MANIFEST',manifest):return s.pins(s.c.file_sha(manifest) if digest is None else digest)
 verify(good);test('full_parent_digest_inventory_source_pins',True)
 for label in ['empty','missing','extra','substitute','runtime']:
  bad=copy.deepcopy(good)
  if label=='empty':bad['files_SHA256']={}
  elif label=='missing':bad['files_SHA256'].pop(next(iter(bad['files_SHA256'])))
  elif label=='extra':bad['files_SHA256']['/tmp/extra']='0'*64
  elif label=='substitute':bad['files_SHA256'][next(iter(bad['files_SHA256']))]='0'*64
  else:bad['environment']={}
  test('manifest_'+label+'_refused',refuse(lambda:verify(bad)))
 test('changed_manifest_digest_refused',refuse(lambda:verify(good,'0'*64)))
(s.HERE/'checks.json').write_text(json.dumps({'status':'PASS','count':len(cases),'cases':cases,'actual_archive_passes':0,'network_requests':0},indent=2)+'\n');print(len(cases),'total PASS')
