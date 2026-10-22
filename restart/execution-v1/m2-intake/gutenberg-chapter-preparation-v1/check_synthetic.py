import json,pathlib,tempfile,unittest.mock as mock
import extract as x
checks=[]
def fail(name,raw):
 try:x.partition(raw)
 except ValueError:checks.append(name);return
 raise AssertionError(name+' accepted')
raw=b'PG fixture\r\n*** START OF THE PROJECT GUTENBERG EBOOK FIXTURE ***\r\nfront\r\nPREFACE.\r\nCafe\xc3\xa9 preface\r\n[Illustration: List of Illustrations.]\r\nHeading to Chapter II. 42\r\n[Illustration: Title\r\n\r\nChapter I.]\r\nFirst body.\r\n'
for i in range(2,62):raw+=('CHAPTER '+x.roman(i)+'.\r\nBody '+str(i)+'.\r\n').encode()
raw+=b'of uniting them.\r\n[Illustration: THE\r\nEND]\r\ncolophon\r\n*** END OF THE PROJECT GUTENBERG EBOOK FIXTURE ***\r\nfulllicense\r\n'
p=x.partition(raw);assert len(p)==67;checks.append('67parts_61chapters')
assert b''.join(raw[a['start_byte']:a['end_byte']] for a in p)==raw;checks.append('allbytes_reconstruct_once')
assert all(a['end_byte']==b['start_byte'] for a,b in zip(p,p[1:]));checks.append('nooverlap_or_gap')
assert all(x.sha(raw[a['start_byte']:a['end_byte']])==a['sha256'] for a in p);checks.append('everyspan_hash')
assert all(raw[a['start_byte']:a['end_byte']].decode('utf8') for a in p);checks.append('UTF8boundaries')
c=next(a for a in p if a['name']=='chapter_01');t=raw[c['start_byte']:c['end_byte']];assert t.startswith(b'[Illustration: Title') and b'Chapter I.]' in t;checks.append('decorated_firstheading_openclose_preserved')
assert b'Heading to Chapter II.' in raw[p[3]['start_byte']:p[3]['end_byte']];checks.append('TOClist_not_a_chapter')
fail('missingPGstart',raw.replace(b'*** START OF',b'START OF'))
fail('duplicatePGend',raw+b'\n*** END OF THE PROJECT GUTENBERG EBOOK OTHER ***')
fail('missingpreface',raw.replace(b'PREFACE.',b'PREFACE'))
fail('missingillustrationlist',raw.replace(b'[Illustration: List of Illustrations.]',b'List'))
fail('missingchapter',raw.replace(b'CHAPTER III.',b'MISSING III.'))
fail('duplicatechapter',raw.replace(b'CHAPTER III.',b'CHAPTER II.'))
fail('chapterreordered',raw.replace(b'CHAPTER III.',b'CHAPTER IV.'))
fail('brokenfirstcaption',raw.replace(b'Chapter I.]',b'Chapter I.'))
fail('novelendingmissing',raw.replace(b'of uniting them.',b'incomplete ending'))
fail('missingclosingillustration',raw.replace(b'[Illustration: THE\r\nEND]',b'end'))
a=x.annotations(b'[Illustration: A]\n[1]\n[Transcriber note]\nProject Gutenberg note',100)
assert {'illustration_caption','footnote_candidate','modern_editorial_candidate'}<={r['kind'] for r in a};checks.append('annotation_types_detected')
for r in a:assert x.sha((b'[Illustration: A]\n[1]\n[Transcriber note]\nProject Gutenberg note')[r['start_byte']-100:r['end_byte']-100])==r['sha256']
checks.append('annotation_absolute_offsets_hashes')
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td)
 with mock.patch.object(x,'DEST',root),mock.patch.object(x,'CAP',1000010):
  x.write('small',b'12345')
  try:x.write('large',b'123456')
  except ValueError:checks.append('aggregate_prewrite_outputcap')
  else:raise AssertionError('Outputcap failed')
out={'status':'PASS_BOUNDARY_AND_COVERAGE_CHECKS','checks':len(checks),'cases':checks,'models_initialized':False,'network':False};pathlib.Path(__file__).with_name('synthetic-result.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
