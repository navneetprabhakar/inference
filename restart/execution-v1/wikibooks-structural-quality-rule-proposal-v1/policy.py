"""Proposed structural routing only. No string/length/code/date semantic classifier."""
def propose(f):
 required={'role_inventory_complete','verified_boilerplate_blocks','residual_nonempty_blocks','residual_verified_index_blocks','residual_unresolved_blocks','index_context_independently_verified','declared_development_status','empty_heading_subtrees','unknown_source_dependencies'}
 if set(f)!=required:raise ValueError('explicit_feature_inventory')
 flags=[]
 if not f['role_inventory_complete']:return {'route':'UNRESOLVED_SOURCE_ROLE_REVIEW','flags':['role_coverage_incomplete'],'quality_pass':False}
 if f['declared_development_status']:flags.append('source_declares_development_status_not_semantic_failure')
 if f['empty_heading_subtrees']:flags.append('empty_source_section_requires_context_review_not_automatic_rejection')
 if f['unknown_source_dependencies']:flags.append('unresolved_source_dependency')
 if f['verified_boilerplate_blocks'] and f['residual_nonempty_blocks']==0:return {'route':'HOLD_NO_REMAINING_SUBJECT_UNIT','flags':flags,'quality_pass':False}
 if f['verified_boilerplate_blocks'] and f['index_context_independently_verified'] and f['residual_nonempty_blocks']==f['residual_verified_index_blocks'] and not f['residual_unresolved_blocks'] and f['residual_nonempty_blocks']>0:return {'route':'HOLD_VERIFIED_BOOK_INDEX_AS_SUBJECT_PROSE_UNIT','flags':flags,'quality_pass':False}
 if f['residual_unresolved_blocks']:flags.append('residual_role_unresolved_not_silently_deleted')
 return {'route':'STRUCTURAL_CONTEXT_REVIEW' if flags else 'NO_STRUCTURAL_EXCLUSION_SEMANTIC_REVIEW_STILL_REQUIRED','flags':flags,'quality_pass':False}

def fixtures():
 base=dict(role_inventory_complete=True,verified_boilerplate_blocks=0,residual_nonempty_blocks=1,residual_verified_index_blocks=0,residual_unresolved_blocks=0,index_context_independently_verified=False,declared_development_status=False,empty_heading_subtrees=0,unknown_source_dependencies=False)
 cases=[]
 def case(name,changes,route):
  got=propose({**base,**changes});assert got['route']==route and not got['quality_pass'];cases.append({'name':name,'PASS':True})
 keep='NO_STRUCTURAL_EXCLUSION_SEMANTIC_REVIEW_STILL_REQUIRED'
 for name in ['one_sentence_definition','short_complete_intro','code_plus_explanation','code_only_role_requires_separate_genre_review','linked_instruction_list','pure_link_reference_list_without_index_adjudication','historical_as_of_statement','ordinary_prose_containing_disclaimer_word']:
  case(name,{},keep)
 case('verified_boilerplate_only',{'verified_boilerplate_blocks':4,'residual_nonempty_blocks':0},'HOLD_NO_REMAINING_SUBJECT_UNIT')
 case('disclaimer_plus_exact_verified_index',{'verified_boilerplate_blocks':4,'residual_nonempty_blocks':21,'residual_verified_index_blocks':21,'index_context_independently_verified':True},'HOLD_VERIFIED_BOOK_INDEX_AS_SUBJECT_PROSE_UNIT')
 case('disclaimer_plus_definition_retained',{'verified_boilerplate_blocks':4},keep)
 case('linkonly_without_explicit_index_context_not_excluded',{'verified_boilerplate_blocks':4,'residual_verified_index_blocks':1},keep)
 case('unknown_residual_not_dropped_to_manufacture_empty_page',{'verified_boilerplate_blocks':4,'residual_verified_index_blocks':1,'residual_unresolved_blocks':1,'index_context_independently_verified':True},'STRUCTURAL_CONTEXT_REVIEW')
 case('empty_heading_review_only',{'empty_heading_subtrees':10},'STRUCTURAL_CONTEXT_REVIEW')
 case('declared0percent_with_good_prose_review_only',{'declared_development_status':True},'STRUCTURAL_CONTEXT_REVIEW')
 case('incomplete_role_inventory_refused',{'role_inventory_complete':False},'UNRESOLVED_SOURCE_ROLE_REVIEW')
 case('unknown_template_dependency_review',{'unknown_source_dependencies':True},'STRUCTURAL_CONTEXT_REVIEW')
 return {'status':'PASS_SYNTHETIC_PROPOSED_POLICY_ONLY','controls':len(cases),'cases':cases}
