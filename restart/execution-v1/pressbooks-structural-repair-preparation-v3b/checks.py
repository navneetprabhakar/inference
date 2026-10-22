"""Synthetic development controls; source unchanged and scoped holds only."""
import hashlib,json
import policy as p
cases=[]
def check(name,t,holds=(),queue=None):
 r=p.assess(t);actual={f['reason'] for f in r['delta_representation_review_holds']};assert actual==set(holds),(name,actual)
 assert r['raw_unchanged'] and r['source_SHA256']==hashlib.sha256(t.encode()).hexdigest() and r['source_bytes_removed']==r['new_admissions']==0
 for f in r['delta_representation_review_holds']+r['pending_dependency_queue']:
  a,b=f['char_start'],f['char_end'];x,y=f['byte_start'],f['byte_end'];assert t[a:b].encode()==t.encode()[x:y]
  assert hashlib.sha256(t.encode()[x:y]).hexdigest()==f['source_span_SHA256']
 if queue is not None:assert {f['reason'] for f in r['pending_dependency_queue']}==set(queue),(name,r['pending_dependency_queue'])
 cases.append(name)
W=p.WALL
H='EXACT_ACCESS_WALL_WITHOUT_CAPTURED_BODY';R='RESOURCE_ACCESS_ONLY_NO_SUBSTANTIVE_CAPTURED_BODY';A='EXPLICIT_EMPTY_ASSESSMENT_BLOCK';P='PRACTICE_OPTIONS_AND_ANSWER_WITHOUT_CAPTURED_PROMPT'
check('bare_access_wall',W+'\nPassword:',[H])
check('navigation_wall','Primary Navigation\nBook Contents Navigation\n1. Example\nColophon\n'+W+'\nPassword:\nPrevious/next navigation',[H])
check('wall_with_authored_guide_not_auto','This guide explains why passwords matter.\n'+W+'\nPassword:',[])
check('quoted_wall_not_auto','An example says “'+W+'”\nPassword:',[])
check('code_wall_not_auto','```\n'+W+'\nPassword:\n```',[])
check('PDF_resource_only','22 Readings and Resources\nReadings and Resources\nRead the attached document, Module 11 Readings (Module_11_Readings.pdf).\nYou will need Adobe Acrobat Reader to access this file 2 .',[R])
check('PDF_guide_preserved','Resources\nRead the attached document, Module 2 Readings (Module_02_Readings.pdf).\nCompare its argument with the chapter. Here are three practical reasons the method works.',[])
check('resource_directory_unknown_preserved','Resources\nThe archive offers historical maps, dates and annotated local examples.',[],[])
check('video_access_only','Video\nWatch the following video.',[R])
check('infographic_access_only','Overview: An Infographic\nView the infographic below.',[R])
check('unknown_media_exposition_preserved','Video\nWatch the following video.\nThe model has two competing causes, each explained in this paragraph.',[])
check('chapter_intro_optional_media_preserved','Introduction\nThis chapter explains environmental change through three examples. Watch the video below for additional perspective.',[])
check('complete_caption_preserved','Figure 1: A family standing beside their new house. The intact caption dates the photograph to 1912.',[])
check('poetry_preserved','A video of rain\nFalls on the pane\nAnd falls again.',[],[])
check('empty_heading_at_EOF','Study notes\nKnowledge Check',[A])
check('prerequisite_boilerplate_generalized','Self-Check: Work\nYou’ll have more success on the Self-Check, if you’ve completed the three Readings in this section.',[A])
check('empty_before_attribution','Discussion Questions\nWhat do you think?\nCheck Your Knowledge\nLicenses and Attributions for the Chapter\nOriginal author credits',[A])
check('real_questions_preserved','Knowledge Check\n1. Why did the river flood?\n2. Explain the two causes.',[])
check('unknown_meaningful_assessment_preserved','Knowledge Check\nStudents discuss the evidence and record their interpretation.',[])
check('unknown_resources_after_heading_preserved','Knowledge Check\nHere are three annotated resources explaining the experiment.',[])
check('broken_practice_options','Readable exposition ends here.\nPractice\n- absolutely\n- essentially\n- really\n- working\nShow Answer\na\nShow Glossary\nDefinition',[P])
check('preceding_question_preserves_options','Which option describes a person?\nPractice\n- worker\n- tree\nShow Answer\na',[])
check('in_practice_question_preserved','Practice\nWhich is a mammal?\n- whale\n- shark\nShow Answer\na',[])
check('unknown_answer_content_not_auto','Practice\n- one\n- two\nShow Answer\nThe answer depends on the assumptions.',[])
check('multibyte_exact_spans','é🙂\nKnowledge Check\nLicenses and Attributions\nCredit',[A])
check('named_visual_pending_only','Use Figure 2 to determine the ages on the diagram.',[],['NAMED_MEDIA_COMPARISON_OR_REQUIRED_CONTEXT_REVIEW'])
check('complete_guide_with_optional_media','Guide\nFirst identify the source. Next compare its date and author. Finally record your conclusion.\nWatch the following video for another example.',[])
check('numbered_navigation_question_title','Primary Navigation\nBook Contents Navigation\n2. Week 2: Warm or Cold-blooded?\n'+W+'\nPassword:',[H])
check('ordinary_previous_how_not_question_prompt','There is debate about how much support to provide.\nPractice\n- absolutely\n- essentially\nShow Answer\na',[P])
check('please_choose_previous_prompt_preserved','Please choose the best answer.\nPractice\n- whale\n- shark\nShow Answer\na',[])
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':len(cases),'cases':cases,'source_body_passes':0},indent=2))
