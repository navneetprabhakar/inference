"""Exact first complete prose-unit proposals only. Never writes unit text."""
import pathlib,json,re,hashlib
OUT=pathlib.Path(__file__).resolve().parent;ROOT=OUT.parent;SOURCE=ROOT/'gutenberg-first-prose-https-targets-v1';PROPOSAL=ROOT/'gutenberg-first-prose-cohort-proposal-v1/proposal.json';REVIEW=ROOT/'gutenberg-cohort-source-components-review-v1/review.json';sha=lambda b:hashlib.sha256(b).hexdigest();meta=json.loads(PROPOSAL.read_text())['records'];review={r['ebook_ID']:r for r in json.loads(REVIEW.read_text())['records']};MAX=65536
# Exact headings verified from retained source; first mainunit only, no body-quality selection.
patterns={
58940:('prologue',r'^THE PROLOGUE\. IN THE GLADE AND BY THE MOONLIGHT\.\r?\n',r'^CHAPTER I\. THE MARK ON THE TREE\.\r?\n'),
65415:('chapter_I',r'^CHAPTER I\.\r?\n',r'^CHAPTER II\.\r?\n'),
52126:('book_I_chapter_I',r'^[ \t]*\*CHAPTER I\.\*\r?\n',r'^[ \t]*\*CHAPTER II\.\*\r?\n'),
3028:('first_complete_story',r'^THE LADY WHO PUT SALT IN HER COFFEE\.\r?\n',r'^ABOUT ELIZABETH ELIZA’S PIANO\.\r?\n'),
59366:('chapter_I',r'^CHAPTER I\.\r?\n',r'^CHAPTER II\.\r?\n'),
34616:('chapter_I',r'^CHAPTER I\.\r?\n',r'^CHAPTER II\.\r?\n'),
21555:('chapter_ONE',r'^CHAPTER ONE\.\r?\n',r'^CHAPTER TWO\.\r?\n'),
22845:('whole_short_story',r'^THE BEAUTY OF THE VILLAGE\r?\n',r"^End of Project Gutenberg's The Beauty"),
31489:('chapter_I',r'^CHAPTER I\.\r?\n',r'^CHAPTER II\.\r?\n'),
2521:('chapter_I',r'^CHAPTER I\.\r?\n',r'^CHAPTER II\.\r?\n'),
6705:('chapter_I',r'^CHAPTER I\.\r?\n',r'^CHAPTER II\.\r?\n'),
2317:('chapter_I',r'^CHAPTER I\r?\n',r'^CHAPTER II\r?\n'),
10141:('whole_unsectioned_discourse',r'^A Discourse on the Life, Character and Writings of Gulian Crommelin\r?\n',r'^EVENING POST, 41 Nassau'),
8530:('chapter_I',r'^I\.\r?\n',r'^II\.\r?\n'),
3120:('whole_short_essay',r'^MODERN FICTION\r?\n',None),
48959:('first_complete_nature_essay',r'^[ \t]*I\.\r?\n',r'^[ \t]*II\.\r?\n'),
60193:('first_complete_vignette',r'^\[Sidenote: AT VILLENEUVE-LÈS AVIGNON\r?\n[ \t]*April 23\]\r?\n',r'^\[Sidenote: ASCENSION DAY AT ARLES\]\r?\n'),
60951:('section_I',r'^I\.\r?\n',r'^II\.\r?\n'),
3144:('whole_unsectioned_essay_with_dependent_footnotes',r'^[ \t]*FROUDE’S HISTORY OF ENGLAND \{219\}\r?\n',None),
7881:('first_complete_location_section_FRANCE',r'^FRANCE\.\r?\n',r'^MARSEILLES\.\r?\n')}
records=[];pins={str(PROPOSAL):sha(PROPOSAL.read_bytes()),str(REVIEW):sha(REVIEW.read_bytes())};checks=[]
for r in meta:
 eid=r['ebook_ID'];path=SOURCE/f'pg{eid}.raw';raw=path.read_bytes();pins[str(path)]=sha(raw);assert pins[str(path)]==review[eid]['source_sha256'];receipt=SOURCE/f'pg{eid}-receipt.json';pins[str(receipt)]=sha(receipt.read_bytes());assert pins[str(receipt)]==review[eid]['receipt_sha256']
 t=raw.decode('utf-8-sig');bom=3 if raw.startswith(b'\xef\xbb\xbf') else 0;byte=lambda c:bom+len(t[:c].encode('utf8'));s=re.search(r'^\*\*\* START OF .*$',t,re.M);e=re.search(r'^\*\*\* END OF .*$',t,re.M);kind,sp,ep=patterns[eid]
 starts=list(re.finditer(sp,t[s.end():e.start()],re.M));assert starts,(eid,'startmissing');start=s.end()+starts[0].start();heading_end=s.end()+starts[0].end()
 # chapter-pattern anchors are standalone lines, excluding TOC entries with inline titles.
 ends=list(re.finditer(ep,t[heading_end:e.start()],re.M)) if ep else []
 if ep:assert ends,(eid,'endmissing');end=heading_end+ends[0].start();nextend=heading_end+ends[0].end()
 else:end=e.start();nextend=e.end()
 a,b=byte(start),byte(end);unit=raw[a:b];assert a<b and unit.decode('utf8')==t[start:end];assert unit.startswith(t[start:heading_end].encode())
 # Header line presence is mandatory; annotation and whitespace bytes remain byte-identical.
 first_prose=review[eid]['candidate_main_prose_interval_not_extracted']['source_start_byte'];assert a<first_prose<b,(eid,a,first_prose,b)
 flags=[]
 if eid==65415:flags+=['Full BALLADS AND LAYS verse epigraph retained; authorintroduction is separately proposed ascompleteprefixunit, never used to replace chapterI.']
 if eid==58940:flags+=['Whole prologue; source book contains illustration/crossversion-insertion disclosures elsewhere; this is not clearance for entirebook.','Opening contains explicit racialized/stereotyped portrayals and violence; substantive semanticreview required.']
 if eid==21555:
  for addition in review[eid]['identified_modern_added_biography']:assert addition['source_end_byte']<=a
  flags+=['Precisely identified modernHodson biography lies entirely before this unit; remains retained raw and incomponentreview. No modernintro deletion applied to raw.']
 if eid==60193:flags+=['Bracketed Sidenote heading includingdate and allFrenchdialogue remain untouched; foreigntext mayfail later strictlanguagepolicy.']
 if eid==60951:flags+=['LatinVirgil epigraph and Englishrendering retained.']
 if eid==48959:flags+=['GeorgeMeredith quotedverse retained with attribution; currentnatureclaims and anthropomorphic prose not factcleared.']
 if eid==3144:flags+=['Footnote markers{219}/{246} and complete endFOOTNOTES remain within whole proposedinterval; no footnote-stripping.']
 if eid==10141:flags+=['Printedtitle, Societyminutes/resolution and officerslist remain in whole source interval; no pure-speech rewrite or removals.']
 if eid==7881:flags+=['Entire explicit FRANCE source locationsection, includingallentrydatelines, not an arbitrary2048/firstNcharacterexcerpt.','Book has8identifiedEDnotes; none falls in this firstlocationsection according to exactcomponentbounds, but book-leveleditor/editionprovenance staysunresolved.']
 if eid==31489:flags+=['HeaderBrame/titlepageClay capturedalias linkage retained; no authorrelabelling or exactedition certification.']
 unit_notes=[x for x in review[eid]['explicit_editor_notes_read_and_captured'] if a<=x['source_start_byte']<b]
 supplemental=[]
 prefixspec={65415:(r'^INTRODUCTION\.\r?\n',r'^[ \t]*CONTENTS\.\r?\n','complete_author_attributed_narrative_introduction'),3028:(r'^Preface to The Second Edition of The Peterkin Papers\r?\n',r'^THE LADY WHO PUT SALT IN HER COFFEE\.\r?\n','complete_second_edition_preface'),6705:(r'^PREFACE\.\r?\n',r'^CONTENTS\.\r?\n','complete_signed_author_preface')}
 if eid in prefixspec:
  x,y,label=prefixspec[eid];m=re.search(x,t[s.end():start],re.M);assert m;pa=s.end()+m.start();n=re.search(y,t[s.end()+m.end():e.start()],re.M);assert n;pb=s.end()+m.end()+n.start();ba,bb=byte(pa),byte(pb);prefix=raw[ba:bb];supplemental=[{'type':label,'source_start_byte':ba,'source_end_byte':bb,'bytes':len(prefix),'sha256':sha(prefix),'literal_heading':m.group(),'status':'SEPARATE_COMPLETE_PREFIX_UNIT_METADATA_ONLY_NOT_SUBSTITUTED_FOR_MAINUNIT','source_original_author_preface':True}]
 rec={'ebook_ID':eid,'metadata_ordinal':r['ordinal'],'title':r['title'],'native_family_component_ID':r['family_component_ID'],'metadata_row_sha256':r['frame_raw_hash'],'source_path':str(path),'source_SHA256':sha(raw),'source_receipt_SHA256':pins[str(receipt)],'source_component_review_SHA256':pins[str(REVIEW)],'decision':'PROPOSE_FIRST_COMPLETE_MAIN_UNIT_FOR_DISCOVERY' if len(unit)<=MAX else 'HOLD_COMPLETE_UNSECTIONED_WORK_EXCEEDS64KiB_NO_TRUNCATION_NO_REPLACEMENT','unit_kind':kind,'source_start_byte':a,'source_end_byte':b,'exact_unit_bytes':len(unit),'exact_unit_unicode_characters':len(unit.decode('utf8')),'exact_unit_sha256':sha(unit),'literal_heading_included':t[start:heading_end],'literal_next_boundary_excluded':t[end:nextend],'boundary_before_start_context':t[max(s.end(),start-120):start],'unit_first160_characters_context':t[start:min(end,start+160)],'unit_last160_characters_context':t[max(start,end-160):end],'following_boundary_context':t[end:min(e.start(),end+160)],'structural_completeness':'All bytes fromfirstliteral mainunitheading through before nextliteralstructuralheading/PGend/legacyPGend; wholework whereunsectioned. Completesourceunit doesnotclaimbook/storysemanticallyselfcontained.','known_component_flags':flags,'book_component_assessment':review[eid]['component_assessment'],'book_dependencies_and_limits':review[eid]['dependencies_and_quality_limits'],'exact_editor_note_dependencies_intersecting_unit':unit_notes,'literal_bracket_illustration_marker_count':unit.count(b'[Illustration'),'literal_footnote_marker_count':unit.count(b'[Footnote'),'supplemental_complete_original_prefaces':supplemental,'text_transformations':0,'unit_fulltext_written':False,'tokenization_runs':0,'new_admitted_documents':0,'new_admitted_tokens':0}
 if len(unit)>MAX:assert eid in [10141,3144]
 records.append(rec);checks.append({'ebook_ID':eid,'exact_source_hash_and_receipt_match':True,'literal_heading_before_first_prose':True,'entire_structural_unit_includes_all_bytes_no_sanitization':True,'supplemental_prefaces_not_main_replacement':True,'modern_intro_outside_Marryat_unit':True if eid==21555 else None})
assert len(records)==20 and {r['ebook_ID'] for r in records}==set(patterns)
for f,d in pins.items():assert sha(pathlib.Path(f).read_bytes())==d
proposal={'status':'EXACT20_FIRST_COMPLETE_MAIN_PROSE_UNIT_DECISIONS_PREPARED_ONLY_NO_EXTRACTION','selection_rule':'Same20cohortIDs, selectfirstmainprologue/chapter/story/essay/vignette/explicitlocationsection in source order, includeliteralheading and allinterveningbytes. Recordcompleteoriginalauthorprefaces separately; never substitutea laterchapter or anotherbook basedon quality. Wholeunsectionedwork>65536bytes held, never cropped.','maximum_bytes_per_fulltext_discovery_unit':MAX,'records':records,'input_pins':pins,'anticipated_if_parent_approves':{'proposed_main_units':sum(r['decision'].startswith('PROPOSE') for r in records),'held_complete_works':sum(r['decision'].startswith('HOLD') for r in records),'proposed_main_unit_fulltext_bytes':sum(r['exact_unit_bytes'] for r in records if r['decision'].startswith('PROPOSE')),'held_full_work_bytes_not_to_write':sum(r['exact_unit_bytes'] for r in records if r['decision'].startswith('HOLD')),'optional_complete_preface_units':sum(len(r['supplemental_complete_original_prefaces']) for r in records),'optional_preface_fulltext_bytes':sum(u['bytes'] for r in records for u in r['supplemental_complete_original_prefaces'])},'not_acceptance':'Deterministic developmentalfirstunits of deliberatelygenrestratifiedmetadata cohort; no corpusacceptancerate or language/rights/quality certification.','units_written':0,'new_admitted_documents':0,'new_admitted_tokens':0,'tokenizer_runs':0,'model_operations':0,'network_requests':0}
(OUT/'proposal.json').write_text(json.dumps(proposal,ensure_ascii=False,indent=2)+'\n');(OUT/'checks.json').write_text(json.dumps({'status':'PASS_SOURCE_BOUND20_DECISIONS','records':checks,'inputs_unchanged':True,'full_unit_texts_written':0},indent=2)+'\n');assert sum(f.stat().st_size for f in OUT.iterdir())<250000
print(json.dumps({'proposal_SHA256':sha((OUT/'proposal.json').read_bytes()),'checks_SHA256':sha((OUT/'checks.json').read_bytes()),'anticipated':proposal['anticipated_if_parent_approves']},indent=2))
