"""Independent synthetic probes only; no retained body access."""
import sys,hashlib,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'gutenberg-fiction-300-boundary-inventory-preparation-v1'))
import boundaries as b,inventory as inv
checks=[]
def case(n,v):assert v,n;checks.append(n)
def fixture(body=b'\xc3\xa9\xe6\x97\xa5 complete prose.\n',nl=b'\n'):
 return b'Header [EBook #42]\nTitle: Example\n*** START OF THE PROJECT GUTENBERG EBOOK EXAMPLE ***'+nl+body+b'*** END OF THE PROJECT GUTENBERG EBOOK EXAMPLE ***'+nl+b'THE FULL PROJECT GUTENBERG LICENSE\nFooter'
r=fixture();x=b.inspect(r,42)
case('all_five_partition_spans_exact_hash_inverse',len(x['partition'])==5 and b''.join(r[s['start_byte']:s['end_byte']] for s in x['partition'])==r and all(hashlib.sha256(r[s['start_byte']:s['end_byte']]).hexdigest()==s['SHA256'] for s in x['partition']))
case('UTF8_envelope_characters_not_bytes',x['payload_characters']<x['payload']['bytes'])
case('envelope_not_mainprose_or_rights_clearance',not x['chapter_boundaries_or_edition_rights_quality_cleared'] and x['source_bytes_removed_or_rewritten']==0)
case('repeated_START_no_alternate_selection','missing_or_ambiguous_supported_marker_pair' in b.inspect(fixture(b'*** START OF THE PROJECT GUTENBERG EBOOK EXAMPLE ***\nprose\n'),42)['boundary_holds'])
case('unsupported_START_preserves_prior_pair_but_held','unsupported_marker_like_lines_no_guess' in b.inspect(fixture(b'*** START OF SOMETHING ELSE ***\nprose\n'),42)['boundary_holds'])
case('header_multiple_IDs_held','header_ID_missing_conflicting_or_not_unique' in b.inspect(r.replace(b'[EBook #42]',b'[EBook #42] [EBook #43]'),42)['boundary_holds'])
case('literal_marker_inside_prose_not_anchored',not b.inspect(fixture(b'An example *** START OF THE PROJECT GUTENBERG EBOOK EXAMPLE *** within prose\n'),42)['boundary_holds'])
case('no_unicode_normalization_of_label','start_end_marker_label_disagreement' in b.inspect(r.replace(b'EBOOK EXAMPLE ***\nHeader',b'EBOOK EXAMPLE ***\nHeader').replace(b'END OF THE PROJECT GUTENBERG EBOOK EXAMPLE',b'END OF THE PROJECT GUTENBERG EBOOK E\xcc\x81XAMPLE'),42)['boundary_holds'])
with tempfile.TemporaryDirectory() as d:
 root=Path(d);p=root/'source';p.write_bytes(r);ent={'path':'source','bytes':len(r),'SHA256':b.sha(r),'dev_ino_size_mtime_ns_ctime_ns':inv.identity(p.stat())}
 def change():
  if p.read_bytes()==r:p.write_bytes(r[:-1]+b'!')
 try:inv.read_source(root,ent,change)
 except ValueError:checks.append('same_length_mutation_refused_hash_or_stat')
 else:raise AssertionError('mutation accepted')
print(__import__('json').dumps({'status':'PASS','independent_controls':len(checks),'controls':checks,'retained_body_reads':0},indent=2))
