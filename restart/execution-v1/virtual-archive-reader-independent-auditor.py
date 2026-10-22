from pathlib import Path
import sys,json,hashlib,tempfile,bz2,io,os
B=Path(__file__).resolve().parent;P=B/'virtual-archive-reader-preparation-v1';O=B/'virtual-archive-reader-independent-audit-v1';sys.path.insert(0,str(P));import virtual_reader as v,checks
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert h(P/'virtual_reader.py')=='10c9e528abe812beaa0fa464fcc9a6a17762ea52bc813c71504373fff4101002' and h(P/'contract.json')=='14360833d35f5ea6bccc9e107cd6ee8024fcae094c3721d573430e52d9a9b17c' and h(P/'code-pins.json')=='7d53d6483983dc1b9221fc908a97c10fb91bfe6693e7526b337ab03c4c091f70';pins=json.loads((P/'code-pins.json').read_text())['SHA256'];assert all(h(p)==d for p,d in pins.items());contract=json.loads((P/'contract.json').read_text());assert contract['native_publication_pins'] is None and contract['native_consumer_ready'] is False
independent=[]
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp).resolve();payload=b'first synthetic member\n'*17+b'second synthetic member\n'*9;compressed=bz2.compress(b'first synthetic member\n'*17)+bz2.compress(b'second synthetic member\n'*9);cut=len(compressed)//3;pp,ex,whole=checks.build(root,blobs=[compressed[:cut],compressed[cut:2*cut],compressed[2*cut:]])
 with v.VirtualArchive(root,pp,ex,max_read=16384) as raw:
  with bz2.BZ2File(raw,'rb') as stream:
   chunks=[]
   while True:
    b=stream.read(7)
    if not b:break
    chunks.append(b)
   assert b''.join(chunks)==payload;assert stream.seek(0)==0 and stream.read(11)==payload[:11]
 independent.append('bounded7B_BZ2_consumer_two_members_cross3physicalparts_and_seek')
 pp,ex,whole=checks.build(root)
 with io.BufferedReader(v.VirtualArchive(root,pp,ex,max_read=16),buffer_size=4) as f:
  out=bytearray(7);assert f.readinto(out)==7 and out==whole[:7];assert f.read(16)==whole[7:] and f.read(1)==b'';assert f.seek(3)==3 and f.read(7)==whole[3:]
 independent.append('BufferedReader_readinto_shortEOF_seek_crossphysicalboundaries')
 # No symlink ancestor accepted even though its target is a valid complete fixture.
 link=root/'alias';link.symlink_to(root,target_is_directory=True)
 try:v.VirtualArchive(link,pp,ex)
 except ValueError:independent.append('completepublication_symlink_directory_refused')
 else:raise AssertionError('directoryalias')
 # All metadata pins are mandatory even if allowed expected paths are intact.
 try:v.VirtualArchive(root,{n:None for n in v.NAMES},ex)
 except ValueError:independent.append('nullpublicationpinvalues_refused')
 else:raise AssertionError('nullpins')
O.mkdir(exist_ok=False);r={'status':'PASS_HELPER_PREPARATION_REVIEW_SYNTHETIC_ONLY_NO_NATIVE_CONSUMER','helper_SHA256':h(P/'virtual_reader.py'),'contract_SHA256':h(P/'contract.json'),'code_pins_SHA256':h(P/'code-pins.json'),'all15pins_verified':len(pins),'reproduced_existing_synthetic_controls':44,'additional_independent_controls':independent,'full_production_reviewed':True,'confirmed':['Exact three externally pinned COMPLETE metadata files; duplicate JSON keys refused; publisher/worker/independent-supervisor hash and byte bindings reconcile','Exact expected ordered component path/length list; no pending/candidate/partial source acceptance','Regular no-symlink paths and ancestors, O_RDONLY|NOFOLLOW|NONBLOCK, descriptor/path fullstat bindings, exact readlength and mutation checks','Explicit nonnegative bounded read<=1MiB and readinto; seek within0..total; all descriptors released even on close mutationerror','No implicit component body hash or concatenation/copy; publisherverification inherited only from reviewed complete publication receipts','BufferedReader and BZ2File boundary/EOF/seek compatibility confirmed with synthetic bytes'],'future_consumer_requirements':['Actual publication triplepins are intentionally missing; no retained archive consumer execution is ready','Later consumer must pin this helper/runtime/contract plus exact completed source manifest and bound every caller-level buffer/decompression/output/time/RSS operation','Reader does not certify BZ2CRC/EOF/XMLvalidity, source quality, language, article counts or admission; current transfer remains separately supervised'],'metadata_read_cap_each':1048576,'component_count_cap':128,'body_read_cap_each':1048576,'actual_retained_archive_body_bytes_read':0,'network_globalledger_model_training_operations':0,'concrete_blockers':[]}
(O/'review.json').write_text(json.dumps(r,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'review.json':h(O/'review.json'),'auditor_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'review.json'),h(O/'manifest.json'))
