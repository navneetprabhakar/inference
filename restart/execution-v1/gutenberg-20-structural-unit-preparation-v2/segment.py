"""Conservative lossless lexical-role reconciliation. Candidate units are never quality passes."""
import hashlib,re
import legacy_segment as old
import roles
need=old.need
sha=old.sha
span=old.span
number=old.number

def discover(raw,envelope,eid):
 baseline=old.discover(raw,envelope,eid)
 a,z=envelope['start_byte'],envelope['end_byte'];body=raw[a:z]
 inventory=roles.inspect(body);events=inventory['events'];toc=[]
 # The lexical TOC primitive can consume the first body CHAPTER I line before
 # stopping at prose. Reconcile that exact reset only with blank-delimited
 # restart + following non-entry prose; otherwise keep ambiguity/fallback.
 for original in inventory['contents_role_candidates']:
  t=dict(original);inside=[ev for ev in events if original['start_byte']<=ev['start_byte']<original['end_byte'] and ev['kind'] in {'chapter_heading_candidate','bare_roman_candidate'}]
  prior=[]
  for ev in inside:
   after=body[ev['end_byte']:original['end_byte']+512].splitlines()
   following=next((ln.decode('utf8').strip() for ln in after if ln.strip()),'')
   before=body[:ev['start_byte']].splitlines();blank_before=bool(before and not before[-1].strip())
   prose=bool(re.search('[a-z]',following) and re.search(r'[.!?]',following) and not re.match(r'(?:CHAPTER|BOOK|PART|VOLUME)\b',following,re.I) and not re.search(r'\.{2,}\s*[0-9]+$',following))
   if ev['number']==1 and len(prior)>=2 and prior==list(range(1,len(prior)+1)) and blank_before and prose:
    t['end_byte']=ev['start_byte'];t['raw_SHA256']=sha(body[t['start_byte']:t['end_byte']]);t['boundary_reconciliation']='EXPLICIT_CONTENTS_CONTINUOUS_ENTRIES_THEN_BLANK_RESTART_WITH_PROSE';break
   prior.append(ev['number'])
  toc.append(t)
 def intoc(e):return any(t['start_byte']<=e['start_byte'] and e['end_byte']<=t['end_byte'] for t in toc)
 candidates=[e for e in events if not intoc(e) and e['kind'] in {'chapter_heading_candidate','bare_roman_candidate','numbered_letter_candidate'} and not e.get('possible_print_year')]
 holds=[];ledger=[]
 if len(candidates)<2:holds.append('fewer_than_two_reconciled_body_boundaries')
 if len(candidates)>1024:raise ValueError('chapter_header_cap')
 first=candidates[0]['start_byte'] if candidates else len(body)
 last=candidates[-1]['start_byte'] if candidates else -1
 # An explicit post-body note/correction anchor provides component context, never deletion.
 noteanchors=[e for e in events if e['kind']=='note_or_editorial_companion_anchor' and e['start_byte']>last]
 notes_start=min((e['start_byte'] for e in noteanchors),default=len(body))
 hierarchy=[e for e in events if e['kind']=='hierarchy_scope_candidate' and not intoc(e)]
 # Prefix print years are retained as unresolved prefix evidence, never a chosen body sequence.
 benign={'prose_chapter_reference','prose_chapter_word_not_heading','work_relation_or_volume_ancestry_lead','explicit_transcriber_component_disclosure','contents_anchor_candidate','literal_authored_ending_candidate','note_or_editorial_companion_anchor','print_tail_anchor_candidate','end_of_volume_typed_tail_candidate'}
 for e in events:
  if intoc(e):role='EXPLICIT_DENSE_CONTENTS_PRESERVED'
  elif e in candidates:role='BODY_BOUNDARY_CANDIDATE'
  elif e['kind']=='hierarchy_scope_candidate':role='HIERARCHY_CONTEXT_CANDIDATE'
  elif e.get('possible_print_year') and e['start_byte']<first:role='PREFIX_PRINT_YEAR_OR_NUMERAL_UNRESOLVED_PRESERVED'
  elif e['start_byte']>=notes_start:role='NOTE_EDITORIAL_COMPONENT_PRESERVED_UNRESOLVED'
  elif e['kind'] in benign:role='LITERAL_COMPONENT_OR_NONHEADING_ROLE_PRESERVED'
  else:
   role='UNRESOLVED_LEXICAL_ROLE'
   holds.append('unreconciled_lexical_role_'+e['kind'])
  ledger.append({**e,'resolved_role':role,'source_start_byte':a+e['start_byte'],'source_end_byte':a+e['end_byte']})
 kinds={e['kind'] for e in candidates}
 if 'chapter_heading_candidate' in kinds and len(kinds)>1:holds.append('mixed_chapter_bare_or_letter_boundary_roles')
 if len(kinds)>1 and kinds!={'bare_roman_candidate','numbered_letter_candidate'}:holds.append('mixed_boundary_roles')
 if kinds=={'bare_roman_candidate','numbered_letter_candidate'}:holds.append('mixed_letter_and_unlabelled_roman_roles')
 if any(e['kind'] in {'bare_roman_candidate','numbered_letter_candidate'} and not e.get('blank_before') for e in candidates):holds.append('bare_boundary_without_blank_line_context')
 if len({e.get('number_style') for e in candidates})>1:holds.append('mixed_chapter_number_styles')
 # Hierarchy type must be uniform and every scope reconciled in source order.
 if len({e['scope_type'] for e in hierarchy})>1:holds.append('mixed_hierarchy_types_unresolved')
 if hierarchy and [e['number'] for e in hierarchy]!=list(range(1,len(hierarchy)+1)):holds.append('hierarchy_missing_repeated_or_noninitial_scope')
 if hierarchy and candidates and candidates[0]['start_byte']<hierarchy[0]['start_byte']:holds.append('body_boundary_before_first_scope')
 scoped=[]
 for c in candidates:
  preceding=[h for h in hierarchy if h['start_byte']<c['start_byte']]
  scope=preceding[-1] if preceding else None
  scoped.append((c,scope))
 scopekeys=[]
 for c,h in scoped:
  key=(h['scope_type'],h['number']) if h else None
  if not scopekeys or scopekeys[-1][0]!=key:scopekeys.append((key,[]))
  scopekeys[-1][1].append(c['number'])
 if any(nums!=list(range(1,len(nums)+1)) for _,nums in scopekeys):holds.append('noncontinuous_repeated_or_missing_scoped_chapter_sequence')
 if any(not any(h is hh for _,hh in scoped) for h in hierarchy):holds.append('hierarchy_scope_without_body_boundary')
 # No largest/last/cleanest sequence preference: any unknown/repeated sequence falls back.
 endings=[e for e in events if e['kind'] in {'literal_authored_ending_candidate','end_of_volume_typed_tail_candidate'} and e['start_byte']>last]
 terminal=len(body)
 if len(endings)==1:
  ending=endings[0]
  if ending['kind']=='end_of_volume_typed_tail_candidate':
   applicable=scoped[-1][1] if scoped else None
   if applicable and applicable['scope_type'] in {'VOLUME','VOL.'} and applicable['number']!=ending['volume_number']:holds.append('ending_volume_does_not_match_scope')
  terminal=ending['end_byte']
 elif len(endings)>1:holds.append('multiple_terminal_ending_roles_unresolved')
 if any(e['kind']=='end_of_volume_typed_tail_candidate' and e['start_byte']<last and not any(h['number']==e['volume_number'] and h['scope_type'] in {'VOLUME','VOL.'} and h['start_byte']<e['start_byte'] for h in hierarchy) for e in events):holds.append('intermediate_volume_ending_without_matching_scope')
 # Units end before the next hierarchy context, not after its epigraph/titlepage.
 intervals=[]
 for i,(c,h) in enumerate(scoped):
  end=candidates[i+1]['start_byte'] if i+1<len(candidates) else terminal
  between=[hh['start_byte'] for hh in hierarchy if c['start_byte']<hh['start_byte']<end]
  if between:end=min(between)
  close=[ev for ev in events if ev['kind']=='end_of_volume_typed_tail_candidate' and c['end_byte']<=ev['start_byte']<end]
  if len(close)>1:holds.append('multiple_volume_endings_in_unit_unresolved')
  if len(close)==1:
   if h and h['scope_type'] in {'VOLUME','VOL.'} and h['number']==close[0]['volume_number']:end=close[0]['end_byte']
   elif end!=terminal:holds.append('intermediate_volume_ending_without_matching_unit_scope')
  if not body[c['end_byte']:end].strip():holds.append('empty_chapter_interval_not_authored_unit')
  intervals.append((c,h,c['start_byte'],end))
 holds=list(dict.fromkeys(holds))
 if holds:
  result=baseline.copy();result['parts']=[span(raw,0,a,'PG_header_and_start_marker'),span(raw,a,z,'whole_envelope_unsegmented_fallback'),span(raw,z,len(raw),'PG_end_marker_and_footer')]
  result['units']=[{**result['parts'][1],'unit_ID':f'pg{eid}:{sha(raw)}:{a}-{z}','structural_status':'WHOLE_ENVELOPE_FALLBACK_NOT_CHAPTER_AUDIT_UNIT','semantic_completeness':'UNASSESSED','context_holds':holds,'whole_book_family_lineage_required':True}]
 else:
  result=baseline.copy();parts=[span(raw,0,a,'PG_header_and_start_marker')];units=[];cursor=a
  for c,h,aa,zz in intervals:
   aa+=a;zz+=a
   if cursor<aa:
    companion=span(raw,cursor,aa,'unclassified_prefix_or_hierarchy_context_including_possible_authored_prose_preserved');parts.append(companion)
    # Retain prefix/context as explicit review candidates, never excluded as print matter.
    if raw[cursor:aa].strip():units.append({**companion,'unit_ID':f'pg{eid}:{sha(raw)}:{cursor}-{aa}','structural_status':'PREFIX_OR_HIERARCHY_COMPONENT_REVIEW_CANDIDATE','semantic_completeness':'UNASSESSED','context_holds':['authored_prefix_epigraph_titlepage_or_TOC_role_review_required'],'whole_book_family_lineage_required':True})
   part=span(raw,aa,zz,'scoped_chapter_or_letter_candidate');parts.append(part)
   scope={'type':h['scope_type'],'number':h['number'],'raw_label':h['raw_label'],'source_span':[a+h['start_byte'],a+h['end_byte']]} if h else None
   units.append({**part,'unit_ID':f'pg{eid}:{sha(raw)}:{aa}-{zz}','chapter_number':c['number'],'hierarchy_scope':scope,'hierarchical_unit_key':{'scope':scope,'kind':c['kind'],'ordinal':c['number'],'source_raw_SHA256':sha(raw)},'boundary_role':c['kind'],'heading_span':span(raw,a+c['start_byte'],a+c['end_byte'],'chapter_heading_candidate'),'structural_status':'ORDERED_SCOPED_INTERVAL_CANDIDATE_NOT_SEMANTIC_PASS','semantic_completeness':'UNASSESSED','context_holds':['semantic_self_containment_and_dependency_review_pending','notes_and_components_remain_unresolved']+(['terminal_tail_boundary_requires_review'] if zz==a+terminal else []),'whole_book_family_lineage_required':True});cursor=zz
  if cursor<z:parts.append(span(raw,cursor,z,'typed_or_unclassified_tail_all_bytes_preserved'))
  parts.append(span(raw,z,len(raw),'PG_end_marker_and_footer'));result.update(parts=parts,units=units)
 result.update({'chapter_sequence_holds':holds,'whole_envelope_fallback':bool(holds),'lexical_role_reconciliation':ledger,'contents_role_candidates':toc,'source_roles_primitive_SHA256':sha(open(roles.__file__,'rb').read()),'prior_v1_outcome':{'fallback':baseline['whole_envelope_fallback'],'holds':baseline['chapter_sequence_holds'],'units':len(baseline['units'])},'all_lexical_roles_accounted':len(ledger)==len(events),'authored_prefix_never_discarded':True,'typed_tail_is_candidate_not_clearance':True})
 parts=result['parts'];units=result['units'];cursor=0
 need(parts[0]['start_byte']==0 and parts[-1]['end_byte']==len(raw) and all(p['end_byte']==q['start_byte'] for p,q in zip(parts,parts[1:])),'contiguous_complete_partition')
 need(b''.join(raw[p['start_byte']:p['end_byte']] for p in parts)==raw,'exact_full_source_inverse')
 for e in ledger:
  e['source_start_character']=len(raw[:e['source_start_byte']].decode('utf8'));e['source_end_character']=len(raw[:e['source_end_byte']].decode('utf8'))
 for p in parts:p['start_character']=cursor;cursor+=len(raw[p['start_byte']:p['end_byte']].decode('utf8'));p['end_character']=cursor
 by={(p['start_byte'],p['end_byte']):p for p in parts}
 for u in units:
  p=by[(u['start_byte'],u['end_byte'])];u['start_character']=p['start_character'];u['end_character']=p['end_character']
 for note in result['note_dependency_hints']:
  note['overlapping_unit_IDs']=[u['unit_ID'] for u in units if u['start_byte']<note['end_byte'] and note['start_byte']<u['end_byte']]
 return result
