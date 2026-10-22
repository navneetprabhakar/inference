"""Exact metadata-only additive hold proposal, no source-body query/transformation."""
import pathlib,json,hashlib,sqlite3,sys,copy,datetime
R=pathlib.Path('/Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1');I=R/'m2-intake';O=pathlib.Path(__file__).resolve().parent
H=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def J(p):return json.loads(pathlib.Path(p).read_text())
def dump(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
oldpath=I/'wikibooks-current20-parent-integration-v1/integration.json';parentpath=I/'wikibooks-heading-context-parent-whole20-review-v1/review.json';judgmentpath=parentpath.parent/'judgments.json';ind10path=I/'wikibooks-heading-empty10-independent-whole-review-v1/review.json';ourpath=R/'wikibooks-heading-context-ten-independent-semantic-review-v1/review.json';comparison=ourpath.parent/'comparison-to-parent.json';meta=R/'wikibooks-heading-context-whole-capture-preparation-v1/selected.metadata.json';selection=I/'wikibooks-heading-context-development-selection-v1/selection.json';screen=I/'wikibooks-language-token-v1/screening.sqlite3';final=I/'wikibooks-global-finalization-v3/finalized.sqlite3';capture_result=I/'wikibooks-heading-context-development-whole20-v1/result.json';capture_supervisor=capture_result.parent/'supervisor.json';sourceprofile=R/'wikibooks-rendered-heading-triage-executor-preparation-v1/profile.json'
old=J(oldpath);parent=J(parentpath);judgments=J(judgmentpath);ind10=J(ind10path);our=J(ourpath);selected=J(selection);metaby={x['source_ordinal']:x for x in J(meta)['selected']};selby={x['source_ordinal']:x for x in selected['selected']};parentby={x['source_ordinal']:x for x in judgments}
assert H(parentpath)=='cf9391bb63ddba659434bb46f4d25776570b6122a4cec607c2b828884c8d72ee' and H(ourpath)=='4f12d4e4957c74e3e65a2fba36765d13cabb60bf8b85cbab01e476c0d3a858bf'
assert H(selection)=='6ddf08ae24cd3f4fb39e8ccaf7acf66da20003c5f4efd8cbbc7568cb9533987b'
assert H(capture_result)=='28647d448c54704a504f22ae0605042d06cadbe4164dddb35b3cfb4c0ba69433' and H(capture_supervisor)=='c85ce27cbef8d0b2a6721a8c01bff414d43b5b547f12dfc0741ad21f644bcccb'
assert J(capture_result)['whole_captured']==20 and J(capture_result)['held_outcomes']==0 and J(capture_result)['all_inputs_rechecked']
oldrows=old['known_hold_overlay'];assert len(oldrows)==8 and sum(x['stored_M1_content_tokens'] for x in oldrows)==4220
quality={j['source_ordinal'] for j in judgments if j['proposed_whole_parent_quality_hold']};assert quality==set(parent['quality_hold_ordinals']) and len(quality)==12
assert sum(parentby[x]['stored_M1_content_tokens'] for x in quality)==10396
independent9={x['source_ordinal'] for x in ind10['records'] if x['support_narrow_whole_parent_presentation_or_quality_hold']};assert len(independent9)==9 and quality-independent9=={13191,24535,59106}
indby={x['source_ordinal']:x for x in ind10['records']};ourby={x['source_ordinal']:x for x in our['reviews']}
for n,j in parentby.items():
 assert j['whole_text_SHA256']==selby[n]['text_sha256'] and j['page_id']==selby[n]['page_id'] and j['revision_id']==selby[n]['revision_id']
 independent=indby.get(n,ourby.get(n));assert independent is not None
 assert independent.get('whole_text_SHA256',independent.get('text_SHA256'))==j['whole_text_SHA256']
for n in [13191,24535,59106]:assert 'HOLD' in ourby[n]['quality']
# The ESS decision remains a component/import hold, NEVER a readability failure.
assert not parentby[1518]['proposed_whole_parent_quality_hold'] and parentby[1518]['component_rights_status']=='EXPLICIT_EXTERNAL_IMPORT_HOLD' and ourby[1518]['readability'].startswith('PASS')
newids=quality|{1518};assert len(newids)==13 and not newids&{x['source_ordinal'] for x in oldrows}
readonly_seven={31019,48408,6098,40483,5123,43518,1518};assert readonly_seven.isdisjoint(quality) and not parentby[71003]['proposed_whole_parent_quality_hold'];assert ind10['intentional_course_outline_without_quality_hold']==71003
# Exact same established screening base; metadata only, never payload or tokenstream.
c=sqlite3.connect(screen.resolve().as_uri()+'?mode=ro&immutable=1',uri=True);c.row_factory=sqlite3.Row
base=[dict(v) for v in c.execute('select source_ordinal,page_id,revision_id,family,title,text_sha256,characters,utf8_bytes,content_tokens,tokens_plus_one_EOS,language_pass,known_discovery_hold,holds from docs where language_pass=1 and known_discovery_hold=0 order by source_ordinal')];c.close();by={v['source_ordinal']:v for v in base}
assert len(base)==len(by)==18688 and sum(v['content_tokens'] for v in base)==19909154
for v in base:assert json.loads(v['holds'])==[] and v['tokens_plus_one_EOS']==v['content_tokens']+1
for v in oldrows:
 s=by[v['source_ordinal']];assert (v['page_id'],v['revision_id'],v['text_SHA256'],v['stored_M1_content_tokens'],v['UTF8_bytes'])==(s['page_id'],s['revision_id'],s['text_sha256'],s['content_tokens'],s['utf8_bytes'])
oldids={v['source_ordinal'] for v in oldrows};prior={n:v for n,v in by.items() if n not in oldids}
def identity_digest(rows):return hashlib.sha256(json.dumps([[v['source_ordinal'],v['page_id'],v['revision_id'],v['family'],v['text_sha256'],v['content_tokens']] for v in sorted(rows,key=lambda x:x['source_ordinal'])],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
assert len(prior)==18680 and sum(v['content_tokens'] for v in prior.values())==19904934 and identity_digest(list(prior.values()))==J(sourceprofile)['candidate_identity_SHA256']=='9b1449cafcaded7bcdeb114bc28fe20d8f98f7a85437f031de922387ce492195'
f=sqlite3.connect(final.resolve().as_uri()+'?mode=ro&immutable=1',uri=True);f.row_factory=sqlite3.Row
for n in selby:
 s=by[n];m=metaby[n];j=parentby[n]
 assert n in prior and (s['page_id'],s['revision_id'],s['family'],s['text_sha256'],s['utf8_bytes'],s['content_tokens'])==(m['page_id'],m['revision_id'],m['family'],j['whole_text_SHA256'],j['whole_UTF8_bytes'],j['stored_M1_content_tokens'])
 row=dict(f.execute('select source_ordinal,page_id,revision_id,family,title,depth,text_sha256,characters,utf8_bytes,holds,active from pages where source_ordinal=?',(n,)).fetchone());role=dict(f.execute('select source_ordinal,holds,exact_owner from final_pages where source_ordinal=?',(n,)).fetchone());assert row==m['expected_finalizer_page'] and role==m['expected_finalizer_role']
f.close()
new=[]
for n in sorted(newids):
 j=parentby[n];s=by[n];component=n==1518;axis='explicit_external_import_component_permission_unresolved_not_readability_failure' if component else j['quality_disposition'].lower()
 reason=j['specific_reason']
 if n==59106:reason='Whole checklist has an unidentified recon chemical dilution and underspecified safety/treatment dependencies. Parentheses are balanced; bleach parenthetical crosses a paragraph boundary. Hold for instruction completeness and separate safety/factual review; no invented replacement recipe.'
 if n==24535:reason='Dense project-management notes contain ambiguous flattened-looking input/tool/output relationships and run-together lists/forms; rendered-only review cannot prove extractor-caused loss rather than source-authored presentation. Specific gantthead.com/Q12 component leads independently require rights review. No proven major extraction-corruption claim.'
 new.append({'source_ordinal':n,'page_id':s['page_id'],'revision_id':s['revision_id'],'text_SHA256':s['text_sha256'],'stored_M1_content_tokens':s['content_tokens'],'UTF8_bytes':s['utf8_bytes'],'hold_axis':axis,'source_namespace':'enwikibooks_rendered_exact_parent_body','family':s['family'],'title':s['title'],'hold_class':'source_component_rights' if component else 'individual_whole_parent_quality_presentation_or_instruction_context','readability_failed':False if component else None,'reason':reason,'parent_disposition_preserved':j['quality_disposition'],'original_frozen_development_stratum':selby[n]['stratum'],'matching_scope':'Exactordinal/page/revision/textSHA only; no blanketfamily/source/heading/unknownkind filter.','potential_complete_subcomponents_not_automatically_rejected_or_derived':True})
combined=copy.deepcopy(oldrows)+new;assert combined[:8]==oldrows
expected={'base_documents':18688,'base_tokens':19909154,'held_documents':21,'held_tokens':15715,'candidate_documents':18667,'candidate_tokens':19893439}
sys.path.insert(0,str(R/'wikibooks-rendered-heading-triage-executor-preparation-v1'));import feature_core
_,remaining,held=feature_core.select_frame(base,combined,expected)
assert len(new)==13 and sum(v['stored_M1_content_tokens'] for v in new)==11495 and sum(v['stored_M1_content_tokens'] for v in new if v['source_ordinal'] in quality)==10396
remaining_from20=set(selby)-newids;assert remaining_from20=={71003,31019,48408,6098,40483,5123,43518} and remaining_from20<=set(remaining)
assert 1518 not in remaining and 71003 in remaining
legacy={R/'m0-registry-v1/registry.json':'4e29107580c7041eba93e922fedcceae15b4ddfa77aa447acea19d3e1b2dd280',I/'gutenberg-individual-admissions-v1/manifest.json':'4abc4f880f6f51fa33fcd5012d9e03f2c816ae7468293b50670492f520edd77d',I/'gutenberg-post1900-individual-admissions-v1/manifest.json':'f51fd9c50b1deae525a0ba3d49dbb8aad6fcafe110abd9388e4ca210ca206064',I/'wikibooks-individual-admissions-v1/manifest.json':'e89947d5ded0c31b61f4218951c75957ce71e07b5bb5d21cf59cb81eaa2ce10a'}
for path,d in legacy.items():assert H(path)==d
# Parent40765nativebody stays oldheld while different exactderivedhash remains admitted.
wbdocs=J(I/'wikibooks-individual-admissions-v1/documents.json');assert len(wbdocs)==1
precision={'59106':'Parentheses balanced(2pairs), bleachparenthetical splitsparagraph; unidentifiedrecon/instruction-safetycontext hold retained.','24535':'Ambiguous flattened-looking relationships/presentation; rendered-only causeunknown; no provenextractorcorruption. Sourcecomponent leads independent.'}
overlay={'status':'PROPOSED_ADDITIVE_EXACT_KNOWN_HOLD_OVERLAY_NOT_ADMISSION_OR_GENERIC_FILTER','recorded_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_overlay':{'path':str(oldpath),'SHA256':H(oldpath),'JSON_pointer':'/known_hold_overlay','preserved_exact_first8records':True},'known_hold_overlay':combined,'new_exact_hold_records':new,'held_documents':21,'held_stored_content_tokens':15715,'original_8_hold_documents':8,'original_8_hold_tokens':4220,'new_quality_presentation_context_hold_documents':12,'new_quality_presentation_context_hold_tokens':10396,'new_separate_explicit_component_hold_documents':1,'new_separate_explicit_component_hold_tokens':1099,'parent_precision_addendum':precision,'protected_precedence':'Exclusion-only exactbody overlay assigns no split and admits no body. Existingprotected/development/test/historical andtrainfamily reservations remain unchanged andalwayswin. No oldprotectedrecord is moved into train; no renewedleakageclearance is claimed.','readability_negative_controls_preserved':{'seven_readable_in_independent10_no_quality_hold':sorted(readonly_seven),'1518_separate_component_hold_not_readability_failure':True,'71003_intentional_readable_syllabus_no_quality_hold':True},'match_policy':'Do not apply by ordinalalone orfamilyalone: exactpage/revision/bodySHA mustmatch. Versionchanges requirefreshreview ratherthanautomaticclearance. Parentheld bodies do not silently reject faithfulfuturederivedcompletecomponents; those needownhash/count/gates.','no_population_extrapolation':True,'generic_empty_heading_or_unknown_kind_filter':False,'sources_prior_overlays_and_admitted_pools_mutated':False,'new_admitted_documents':0,'new_admitted_tokens':0}
dump('overlay.proposed.json',overlay);dump('remaining-source-ordinals.metadata.json',sorted(remaining));dump('precision-addendum.proposed.json',precision)
integration={'status':'PROPOSED_METADATA_ONLY_EXACT_HOLD_FRAME_RECONCILED_PENDING_ROOT_ADOPTION','provisional_before_new_overlay':{'documents':18680,'M1_content_tokens':19904934,'identity_SHA256':identity_digest(list(prior.values()))},'new_unique_exclusions':{'documents':13,'M1_content_tokens':11495,'quality_presentation_context':12,'component_only':1},'provisional_after_proposed_overlay':{'documents':18667,'M1_content_tokens':19893439,'identity_SHA256':identity_digest(list(remaining.values()))},'all_holds_from_original_base':expected,'original8records_identical':combined[:8]==oldrows,'prior_old8_and_new13_disjoint':not(oldids&newids),'all20_reviewed_identities_screen_finalizer_metadata_match':True,'audited_existing_select_frame_metadata_guard_passed':True,'negative_quality_controls_still_labeled_readable':sorted(readonly_seven|{71003}),'seven_current_candidates_preserved_from_new20':sorted(remaining_from20),'1518_treatment':'KnownexplicitWebopediacomponent concern fits existingheterogeneousknownholdframepolicy(source/factual/presentation),distinctfromreadability. Doesnotlabelallunknownrights asfailed ordeclareinfringement.','prior_40765_parent_vs_admitted_derivative_scope':'Originalparent735B/265M1 remainsoldheld; separate631B/216M1 exactderivedunit alreadyadmitted is untouched. Exacthash overlaycannotoverwrite thatadmission or7membertrainreservation.','protected_precedence':'No split/protection/family mutation; exclusionsonly; no admission/leakagepass conferred.','legacy_manifest_registry_hashes_preserved':{str(p):v for p,v in legacy.items()},'body_or_HTML_or_nativeJSON_queries':0,'tokenizer_renderer_language_or_model_invocations':0,'network_or_globalledger_writes':0,'current_work_status_count_snapshot_edits':0,'new_admissions':0}
dump('integration.proposed.json',integration)
paths=[oldpath,parentpath,judgmentpath,ind10path,ourpath,comparison,meta,selection,capture_result,capture_supervisor,sourceprofile,R/'wikibooks-heading-terminal-independent-verification-v1/verification.json',R/'wikibooks-heading-context-whole-capture-preparation-v1/readiness.json',R/'wikibooks-rendered-heading-triage-executor-preparation-v1/feature_core.py']
dump('evidence-pins.json',{str(p):H(p) for p in paths})
for path,d in legacy.items():assert H(path)==d
assert H(oldpath)==overlay['original_overlay']['SHA256']
dump('manifest.json',{'status':'IMMUTABLE_PROPOSED_EXACT_HOLD_FRAME_NOT_ADMISSION','files':{p.name:{'SHA256':H(p),'bytes':p.stat().st_size} for p in sorted(O.iterdir()) if p.is_file() and p.name!='manifest.json'}})
for p in O.iterdir():
 if p.is_file():p.chmod(0o444)
print(json.dumps({'overlay_SHA256':H(O/'overlay.proposed.json'),'integration_SHA256':H(O/'integration.proposed.json'),'manifest_SHA256':H(O/'manifest.json'),'remaining_documents':len(remaining),'remaining_tokens':sum(x['content_tokens'] for x in remaining.values())}))
