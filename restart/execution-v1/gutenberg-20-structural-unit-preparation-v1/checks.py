"""Synthetic full inverse/sequence/TOC/notes/lifecycle-facing engine controls."""
from pathlib import Path
import tempfile,json,hashlib,copy
import segment,engine,custody
N=0
def ok(v):
 global N;assert v;N+=1
def no(f):
 global N
 try:f()
 except (ValueError,UnicodeError):N+=1;return
 raise AssertionError('expected refusal')
def source(body):
 prefix='PG café header\n';suffix='\nPG footer';raw=prefix.encode()+body.encode()+suffix.encode();env={'start_byte':len(prefix.encode()),'end_byte':len(prefix.encode())+len(body.encode()),'bytes':len(body.encode()),'SHA256':segment.sha(body.encode())};return raw,env
b='PREFACE\nAn authored preface retained whole.\nCONTENTS\nI. One ... 1\nII. Two ... 5\nCHAPTER I.\nCoherent narrative starts here.\n1. A numbered instruction remains.\n2. Another instruction.\nCHAPTER II.\nCoherent ending here with a note[1].\nTHE END\nNOTES\n[1] Explanatory source note retained.\n'
r,e=source(b);x=segment.discover(r,e,1);ok(not x['whole_envelope_fallback']);ok(len(x['units'])==2);ok(b''.join(r[p['start_byte']:p['end_byte']] for p in x['parts'])==r);ok(sum(p['bytes'] for p in x['parts'])==len(r));ok(x['parts'][-1]['end_character']==len(r.decode()));ok(x['units'][0]['start_character']<x['units'][0]['start_byte']);ok(x['units'][0]['bytes']>0 and x['units'][0]['semantic_completeness']=='UNASSESSED');ok('1. A numbered instruction' in r[x['units'][0]['start_byte']:x['units'][0]['end_byte']].decode());ok(x['parts'][-2]['role']=='unclassified_print_endmatter_preserved');ok(len(x['note_dependency_hints'])==2);ok(any(n['line_initial_marker'] for n in x['note_dependency_hints']));ok(x['notes_front_endmatter_or_editorial_removed']==0)
for text,reason in [
 ('Plain complete text without chapter headings.','fewer_than_two_supported_chapter_boundaries'),
 ('1. One numbered paragraph.\n2. Another numbered paragraph.','fewer_than_two_supported_chapter_boundaries'),
 ('CHAPTER I\nOne\nCHAPTER III\nThree\n','noncontinuous_repeated_or_missing_chapter_sequence'),
 ('CHAPTER I\nTOC\nCHAPTER II\nTOC\nCHAPTER I\nReal1\nCHAPTER II\nReal2\n','noncontinuous_repeated_or_missing_chapter_sequence'),
 ('CHAPTER IIII\nOne\nCHAPTER II\nTwo\n','invalid_or_ambiguous_numeral'),
 ('CHAPTER 01\nOne\nCHAPTER 2\nTwo\n','invalid_or_ambiguous_numeral'),
 ('CHAPTER I\nOne\nCHAPTER 2\nTwo\n','mixed_chapter_number_styles'),
 ('CHAPTER I\nCHAPTER II\nTwo\n','empty_chapter_interval_not_authored_unit'),
 ('CHAPTER I\nOne\nBOOK II\nCHAPTER II\nTwo\n','hierarchy_requires_distinct_policy'),
 ('CHAPTER I\nOne\nCHAPTER TWO\nTwo\nCHAPTER II\nThree\n','unsupported_chapter_like_line_within_sequence'),
 ('CONTENTS\nCHAPTER I\nA story....1\nCHAPTER II\nAnother story....50\n','chapter_intervals_are_page_locator_table_candidates')]:
 rr,ee=source(text);z=segment.discover(rr,ee,1);ok(z['whole_envelope_fallback'] and reason in z['chapter_sequence_holds']);ok(z['units'][0]['start_byte']==ee['start_byte'] and z['units'][0]['end_byte']==ee['end_byte']);ok(b''.join(rr[p['start_byte']:p['end_byte']] for p in z['parts'])==rr)
for labels in [('1','2'),('I','II')]:
 rr,ee=source(f'CHAPTER {labels[0]}\r\nFirst café complete narrative.\r\nCHAPTER {labels[1]}\r\nSecond complete narrative.\r\n');z=segment.discover(rr,ee,9);ok(not z['whole_envelope_fallback']);ok('last_unit_includes_unresolved_possible_print_endmatter' in z['units'][-1]['context_holds'])
rr,ee=source('CHAPTER I\nFirst.\nCHAPTER II\nSecond.\nTHE END\nAnother text\nTHE END\n');z=segment.discover(rr,ee,1);ok(z['units'][-1]['end_byte']==ee['end_byte'])
no(lambda:segment.discover(b'\xff',{'start_byte':0,'end_byte':1,'bytes':1,'SHA256':'x'},1));bad=copy.deepcopy(e);bad['SHA256']='0'*64;no(lambda:segment.discover(r,bad,1));rr,ee=source(('CHAPTER I\nText\n')*1025);no(lambda:segment.discover(rr,ee,1))
# Actual finite engine across20 tiny fake sources; original source records only.
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp)/'raw';root.mkdir();out=Path(tmp)/'out';out.mkdir();rows=[];srcs=[];envs=[]
 for i in range(20):
  q=root/f'pg{i}.txt';q.write_bytes(r);rows.append({'ordinal':i,'ebook_ID':i+1});srcs.append({'path':q.name,'bytes':len(r),'SHA256':segment.sha(r),'dev_ino_size_mtime_ns_ctime_ns':custody.identity(q.stat())});envs.append(e)
 p={'records':rows,'source_files':srcs,'envelopes':envs,'source_output':str(root),'expected_selected_raw_bytes':len(r)*20,'expected_selected_envelope_bytes':e['bytes']*20};s=engine.run(p,out,lambda *a:None);ok(s['stats']['books']==20 and s['stats']['chapter_candidate_units']==40);ok(s['all20_outcomes_retained_no_replacements']);ok(len((out/'records.jsonl').read_text().splitlines())==20);ok(s['records_SHA256']==segment.sha((out/'records.jsonl').read_bytes()));ok(set(q.name for q in out.iterdir())=={'records.jsonl'})
print(json.dumps({'status':'PASS_SYNTHETIC_STRUCTURAL_DISCOVERY_ONLY','controls':N,'retained_PG_body_reads':0,'semantic_completeness_from_headings_claimed':False}))
