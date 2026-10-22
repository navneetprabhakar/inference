import json,hashlib
import roles
N=[]
def case(name,text,expected=None,absent=(),toc=None):
 raw=text.encode();r=roles.inspect(raw);ks={e['kind'] for e in r['events']}
 if expected is not None:assert set(expected)<=ks,(name,ks)
 assert not(set(absent)&ks),(name,ks)
 assert r['source_SHA256']==hashlib.sha256(raw).hexdigest() and r['source_bytes_removed']==r['chapter_units_emitted']==0 and not r['numeric_sequence_selected']
 assert b''.join(raw[p['start_byte']:p['end_byte']] for p in r['parts'])==raw
 for e in r['events']:assert hashlib.sha256(raw[e['start_byte']:e['end_byte']]).hexdigest()==e['raw_SHA256']
 if toc is not None:assert len(r['contents_role_candidates'])==toc,(name,r['contents_role_candidates'])
 N.append(name);return r
case('same_line_title','CHAPTER I. THE HERO.\n\nAuthored narrative.',['chapter_heading_candidate'])
case('same_line_colon','CHAPTER 2: THE SECOND DAY\n\nNarrative.',['chapter_heading_candidate'])
case('same_line_prose_reference_not_header','A locality described in\nchapter xxii. There is an inn.',['prose_chapter_reference'],['chapter_heading_candidate'])
case('incidental_chapter_word','They read a\nchapter, verse for verse.',['prose_chapter_word_not_heading'],['chapter_heading_candidate'])
case('unknown_spelled_label_remains_held','CHAPTER TWENTYONE\ntext',['unsupported_chapter_label'])
case('finite_cardinal_spelled_proposal','CHAPTER ONE\ntext',['chapter_heading_candidate'])
case('canonical_roman_reject','CHAPTER IIX\ntext',['unsupported_chapter_label'])
case('canonical_arabic_reject','CHAPTER 01\ntext',['unsupported_chapter_label'])
case('bare_roman_narrative','\n\nI\n\nThe road was quiet.\n\nII\n\nA second day.',['bare_roman_candidate'])
case('bare_roman_title','\nI\nTHE DISSOLUTION\n\nBoom.',['bare_roman_candidate'])
case('year_is_not_discarded','MCMVI\nCopyright1906\n\nI\n\nNarrative.',['bare_roman_candidate'])
case('French_initial_not_heading','M. Verneuil approached.\n',[],['bare_roman_candidate','chapter_heading_candidate'])
case('I_pronoun_not_heading','I. So I was picked up by a vessel.\n',[],['bare_roman_candidate','chapter_heading_candidate'])
case('letter_role_preserved','\nI\n\nFROM DANE KEMPTON TO HERBERT WACE\n\nLONDON,\nAugust14\nDearfriend',['numbered_letter_candidate'])
case('contents_not_choose_last_sequence','CONTENTS\nCHAPTER I\nCHAPTER II\n\nA TITLE\n\nCHAPTER I\n\nFirst narrative.\n\nCHAPTER II\n\nSecond narrative.',['contents_anchor_candidate','chapter_heading_candidate'],toc=1)
case('normal_chapters_not_contents','CHAPTER I\n\nA meaningful full paragraph.\n\nCHAPTER II\n\nAnother paragraph.',toc=0)
case('complex_contents_books','CONTENTS\nBOOK I.\nEpigraph\nCHAPTER I. THE HERO.\nCHAPTER II. THE RIVER.\nBOOK II.\nCHAPTER I. SUMMER.\n\nHYPERION\n',['contents_anchor_candidate','hierarchy_scope_candidate'],toc=1)
case('contents_title_C_not_roman','CONTENTS\nCHAPTER I\nCHAPTER II\n\nCHIPPINGE BOROUGH\n\nI\nTHE DISSOLUTION\n\nNarrative.',toc=1)
case('volume_ordinal_resets_preserved','VOLUME THE FIRST.\nCHAPTER I.\nText.\nEND OF THE FIRST VOLUME.\nVOLUME THE SECOND.\nCHAPTER I.\nText.',['hierarchy_scope_candidate','end_of_volume_typed_tail_candidate'])
case('VOL_abbreviation','VOL. I.\nTitle.\nVOL. II.\nTitle.',['hierarchy_scope_candidate'])
case('part_hierarchy','PART I\nCHAPTER I\nText\nPART II\nCHAPTER I\nText',['hierarchy_scope_candidate'])
case('exact_first_volume_tail','An authored closing sentence.\n\nEND OF THE FIRST VOLUME.\n\nPrinted in Great Britain by\nPRINTER\n',['end_of_volume_typed_tail_candidate','print_tail_anchor_candidate'])
case('quoted_volume_ending_not_marker','"END OF THE FIRST VOLUME."\n',[],['end_of_volume_typed_tail_candidate'])
case('prose_volume_ending_not_marker','He wrote END OF THE FIRST VOLUME in his letter.\n',[],['end_of_volume_typed_tail_candidate'])
case('unsupported_volume_ordinal_retained','END OF THE TWENTYFIRST VOLUME.\n',['unsupported_end_volume_ordinal'])
r=case('multiple_volume_endings_no_preferredcut','END OF THE FIRST VOLUME.\nOthertext\nEND OF THE SECOND VOLUME.',['end_of_volume_typed_tail_candidate']);assert sum(e['kind']=='end_of_volume_typed_tail_candidate' for e in r['events'])==2
case('THEEND_quoted_not_cut','He shouted THE END before continuing.\n"THE END"\n',[],['literal_authored_ending_candidate'])
case('ending_and_advertisement_preserved','Story ends.\nTHE END.\nADVERTISEMENTS.\nBook catalogue.',['literal_authored_ending_candidate','print_tail_anchor_candidate'])
case('notes_references_not_body_headings','NOTES\nIt is fitting to explain the locality in\nchapter xxii. There is an inn.',['note_or_editorial_companion_anchor','prose_chapter_reference'])
case('correction_log_retained','Typographical errors silently corrected:\nchapter 8: =dry blossoms= replaced by =dry-blossoms=',['note_or_editorial_companion_anchor','editorial_correction_locator_not_chapter'])
case('chapterless_work_no_invention','CHRISTMAS DAY\nA complete authored essay without chapterlabels.\nTranscriber’s Note\nArt text.',['note_or_editorial_companion_anchor'],['chapter_heading_candidate'])
case('transcriber_disclosure_not_deleted','{Transcribed by Person. Notes by the transcriber\nare enclosed in {curly brackets}.\nOriginal prose.',['explicit_transcriber_component_disclosure'])
case('sequel_relation_preserved','TRUE LOVE\nA Sequel to Mona\nCHAPTER I\nNarrative.',['work_relation_or_volume_ancestry_lead'])
case('UTF8_exact_inverse','é🙂\nCHAPTER I. THE HERO.\n本文 unchanged.',['chapter_heading_candidate'])
for raw in [b'\xff',b'x'*2400001]:
 try:roles.inspect(raw)
 except (ValueError,UnicodeError):N.append('bounded_or_UTF8_refusal')
 else:raise AssertionError('expected refusal')
try:roles.inspect(b'THE END\n'*8193)
except ValueError as e:assert str(e)=='role_event_cap_no_truncation';N.append('event_cap_no_silent_truncation')
else:raise AssertionError('event_cap')
print(json.dumps({'status':'PASS_SYNTHETIC_ROLE_PRIMITIVES_ONLY','controls':len(N),'names':N,'retained_source_policy_runs':0,'new_units_or_admissions':0},indent=2))
