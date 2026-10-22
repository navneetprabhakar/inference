"""Synthetic production parser and FD-source checks, no retained source reads."""
import tempfile,hashlib,json,os,copy
from pathlib import Path
import boundaries,inventory
N=0
def ok(v):
 global N;assert v;N+=1
def refuse(fn):
 global N
 try:fn()
 except (ValueError,UnicodeError,FileNotFoundError):N+=1;return
 raise AssertionError('expected refusal')
def raw(body=b'CHAPTER I\nCoherent synthetic prose.\n',article=b'THE',fmt=b'EBOOK',nl=b'\n'):
 return b'The Project Gutenberg eBook\n[EBook #123]\nTitle: A title\nAuthor: Fixture Author\n'+b'*** START OF '+article+b' PROJECT GUTENBERG '+fmt+b' A TITLE ***'+nl+body+b'*** END OF '+article+b' PROJECT GUTENBERG '+fmt+b' A TITLE ***'+nl+b'THE FULL PROJECT GUTENBERG LICENSE\n'
r=raw();x=boundaries.inspect(r,123);ok(not x['boundary_holds']);ok(b''.join(r[p['start_byte']:p['end_byte']] for p in x['partition'])==r);ok(x['partition'][2]['role']=='continuous_PG_payload_envelope');ok(x['source_bytes_removed_or_rewritten']==0);ok(x['raw_header_fields'][1]['exact_text']=='Author: Fixture Author');ok(x['structural_hints'][0]['role']=='chapter_heading_candidate')
for article in [b'THE',b'THIS']:
 for fmt in [b'EBOOK',b'ETEXT']:
  for nl in [b'\n',b'\r\n',b'\r']:
   z=boundaries.inspect(raw(article=article,fmt=fmt,nl=nl),123);ok(not z['boundary_holds'])
for data,reason in [(r.replace(b'*** START',b'--- START'),'missing_or_ambiguous_supported_marker_pair'),(r+r,'missing_or_ambiguous_supported_marker_pair'),(r.replace(b'END OF THE PROJECT GUTENBERG EBOOK A TITLE',b'END OF THE PROJECT GUTENBERG EBOOK OTHER'),'start_end_marker_label_disagreement'),(r.replace(b'END OF THE',b'END OF THIS'),'start_end_marker_grammar_disagreement'),(r.replace(b'EBook #123',b'EBook #124'),'header_ID_missing_conflicting_or_not_unique'),(r.replace(b'THE FULL PROJECT GUTENBERG LICENSE',b'other footer'),'full_license_footer_heading_unobserved')]:ok(reason in boundaries.inspect(data,123)['boundary_holds'])
refuse(lambda:boundaries.inspect(b'\xff',123));refuse(lambda:boundaries.inspect(b'',123));refuse(lambda:boundaries.inspect(b'a'*2400001,123))
z=boundaries.inspect(raw(b'\xef\xbb\xbfUnicode caf\xc3\xa9 \xe6\x97\xa5\n[Illustration: retained.]\n[3]\ntranscriber retained\n'),123);ok(len(z['structural_hints'])==3);ok(z['raw_bytes']>z['raw_characters']);ok(z['payload_includes_all_print_frontmatter_endmatter_notes_unchanged']);refuse(lambda:boundaries.inspect(raw(b'[1]\n[2]\n'),123,event_cap=1))
with tempfile.TemporaryDirectory() as d:
 root=Path(d);p=root/'x';p.write_bytes(r);e={'path':'x','bytes':len(r),'SHA256':boundaries.sha(r),'dev_ino_size_mtime_ns_ctime_ns':inventory.identity(p.stat())};ok(inventory.read_source(root,e,lambda:None)==r)
 wrong=copy.deepcopy(e);wrong['SHA256']='0'*64;refuse(lambda:inventory.read_source(root,wrong,lambda:None));wrong=copy.deepcopy(e);wrong['dev_ino_size_mtime_ns_ctime_ns'][1]+=1;refuse(lambda:inventory.read_source(root,wrong,lambda:None))
 p.unlink();p.symlink_to(root/'missing');refuse(lambda:inventory.read_source(root,e,lambda:None));p.unlink();p.write_bytes(r)
 e['dev_ino_size_mtime_ns_ctime_ns']=inventory.identity(p.stat());changed=False
 def mutate():
  global changed
  if not changed:p.write_bytes(r+b'X');changed=True
 refuse(lambda:inventory.read_source(root,e,mutate))
ok(not boundaries.inspect(raw().replace(b'\n',b'\r'),123)['boundary_holds'])
ok('unsupported_marker_like_lines_no_guess' in boundaries.inspect(raw()+b'*** START OF UNKNOWN BOOK ***\n',123)['boundary_holds'])
# Exercise actual300-record producer using only tiny synthetic files and exact source stats.
with tempfile.TemporaryDirectory() as d:
 root=Path(d)/'raw';root.mkdir();out=Path(d)/'out';out.mkdir();files=[];rows=[]
 for i in range(300):
  folder=root/f'attempt-{i:03}'/'raw';folder.mkdir(parents=True);p=folder/'pg123.txt';p.write_bytes(r)
  files.append({'path':str(p.relative_to(root)),'bytes':len(r),'SHA256':boundaries.sha(r),'dev_ino_size_mtime_ns_ctime_ns':inventory.identity(p.stat())})
  rows.append({'ordinal':i,'ebook_ID':123,'family_component_ID':123,'catalog_extent_bytes_not_expected_current_size':len(r)})
 prof={'records':rows,'source_files':files,'source_output':str(root),'expected_plaintext_bytes':len(r)*300}
 rr=inventory.run(prof,out,lambda *a:None);ok(rr['summary']['raw_files']==300);ok(rr['summary']['unique_unheld_PG_envelopes']==300);ok(len((out/'records.jsonl').read_text().splitlines())==300);ok(rr['records_SHA256']==boundaries.sha((out/'records.jsonl').read_bytes()));ok(set(p.name for p in out.iterdir())=={'records.jsonl'})
print(json.dumps({'status':'PASS_SYNTHETIC_BOUNDARY_AND_FD_CUSTODY_ONLY','controls':N,'retained_body_reads':0}))
