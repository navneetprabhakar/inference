"""Record full root semantic review of the180 locally generated turns."""
import collections,hashlib,json
from pathlib import Path
P=Path('reports/ownbase-budget50-v1');R=Path('runs/ownbase-budget50-v1');a=R/'local-baseline-assessment.json';b=R/'local-baseline-assessment-rest.json';x=json.loads(a.read_text());y=json.loads(b.read_text());suite=json.loads((P/'assessment.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert x['status']=='incomplete_deadline' and len(x['records'])==149
assert y['status']=='complete_requires_full_review' and len(y['records'])==33
assert x['checkpoint_manifest_sha256']==y['checkpoint_manifest_sha256'] and x['runner_sha256']==y['runner_sha256']
for old,new in zip(x['records'][147:],y['records'][:2]):
 assert old['session']==new['session'] and old['turn']==new['turn'] and old['result']['assistant_text']==new['result']['assistant_text']
records=x['records'][:147]+y['records'];assert [(r['session'],r['turn']) for r in records]==[(s['id'],i) for s in suite['sessions'] for i in range(3)]
passes={('b50-07-05',1):'Requiredposter sentence iscorrectandclearlyquoted; introduction isoutsidepostercontent.',('b50-01-02',0):'Genuine96-18calculatorcall and78answer; minutes areunambiguousfromquestion.',('b50-04-05',0):'Genuine125/5calculatorcall and25answer; badgesperbox unambiguous.',('b50-08-03',2):'Correctlyrecallsx=5; fullsentenceallowedbecauseuserdidnotrequireexact-onlyformat.',('b50-08-09',2):'Correctlyrecallsenumeratestartcounter1.',('b50-08-10',2):'Correctlyrecallsrepeatedkeymode.'}
notes={
 'b50-01-01':'Inventsmissinginformationandwrongcliparithmetic; nevercomputescorrectkitlimits.',
 'b50-01-04':'Genericroomadvice doesnotapplydependencyorder orfailedtestconstraint.',
 'b50-01-06':'Firstturn repeatscorrectstatuses butmissesbriefboard-updateform throughirrelevantadvice; laterturnsdropexplicitcollected/readyupdatesandclaimPinepreparing.',
 'b50-01-08':'Echoesformatrequestthenwrongduration25instead60.',
 'b50-01-10':'Doesnotapplyweather/paint/toolavailabilityconstraints; genericrepeatedchecking.',
 'b50-02-01':'Wrongentrance/time; inventsaccessafterclosures.',
 'b50-02-02':'Callsinitialimpossiblestaffingpossible; subsequentacknowledgmentsdonotproduceschedules.',
 'b50-02-04':'Selectsdiscussionroominitiallybutfalselyclaims screenonlyrequirement; failsbroken-screenrevision andkeepsscreenessentialafteroptionalupdate.',
 'b50-07-01':'Inventspackageopenedanddeniesknowncontents/seal evidence.',
 'b50-07-02':'Genericwritingadvice; nofaithfulthree-topicpriorityorderingorrecall.',
 'b50-07-03':'Doesnotdraftrequestedgroundedparcelnote; ignoresdampboxandknownlocation.',
 'b50-07-04':'Doesnotapplytwo-step/one-stepconditional; genericdiagramlayoutclaims.',
 'b50-07-05':'Initialconflictclaimedconsistent; finalrevisioninventsenclosedplaceholder.',
 'b50-07-06':'Invents6pmopeningthenfailsprovided7pmclosingcomparisonandprovenance.',
 'b50-07-07':'Acknowledgmentinsteadattribution; partialcorrectiononlyDev; finalinvalidmodelaction.',
 'b50-07-08':'Genericweatheradvice; nofaithfulpossibleversusunlikely distinction.',
 'b50-07-09':'Initialdefinitionroughlycorrectbutmissesexplicit2sentences; neveraddsoutdatedcopylimitation.',
 'b50-07-10':'Notapackingchecklist; ignorespostponement andwrongrecallofcancelledrequest.',
 'b50-07-11':'Misreadscovermaterialsaspaperwipes; doesnotselectbychangedpriorityandaddsunsupportedproperties.',
 'b50-07-12':'Acknowledgmentswithoutguidelineorexceptions.',
 'b50-01-02':'Lateroperandretrievalwrong:7-7then16-7insteadcorrectedoriginalduration.',
 'b50-01-05':'Noactualconversion; invented/mathematicallywrongroutearithmetic.',
 'b50-01-09':'Wrongdivide8/6followedbyinvalidaction; remainingturnsblocked.',
 'b50-02-03':'Noactualcalculator; panelcount/unitsandcorrectionswrong.',
 'b50-02-05':'Invalidfirstactionthenblockedsession.',
 'b50-02-09':'Noactualcalculator; fails8/5/8clipcounts.',
 'b50-03-01':'Doesnotcomputeusablewidth; incorrectoriginal2.4cmrecall.',
 'b50-03-02':'Unitsandallmassarithmeticincorrect; nocalls.',
 'b50-03-03':'Incorrecthours/minutes/secondsandactive-durationreasoning; nocalls.',
 'b50-03-04':'Nevercomputesdistance orrecognizesmissingdirection.',
 'b50-03-09':'Wrongdivision/allocation; failsreservedemptyandfullpacketchanges.',
 'b50-04-01':'First83calculationcorrectbutexplicitexplanationofprogramtotalmissing; correctionsandshortfallwrong.',
 'b50-04-03':'Wrong8+14=27andfailedtraycorrection; nocalls.',
 'b50-04-04':'Wrongtimeconversionandworkduration; nocalls.',
 'b50-04-05':'Newcapacityandremaining112notcomputed; deniesknown125total.',
 'b50-04-06':'Incorrectkg/gconversionandtare; nocalls.',
 'b50-04-07':'Wrongpath/loopunitsanddistance; nocalls.',
 'b50-04-08':'Wrongchairarithmeticandusablecapacity; invented64squarefeet.',
 'b50-04-09':'Invalidfirstactionthenblockedsession.',
 'b50-04-10':'Failsmm/cmconversion; failstoaskmissingcutlength; calls23-23yieldingwrong0.',
 'b50-05-01':'Noaliasing/copyunderstandingorvalidfix; repeatedfieldplaceholders.',
 'b50-05-02':'Repeatslimit0withouttruthinessfixorrequiredlist.',
 'b50-05-03':'Incorrectlistiterationexplanationandnonfunctionalparts[0]fixes.',
 'b50-05-04':'MissesUnboundLocalError; inventedslowest-wayruleandinvalidclosureadvice.',
 'b50-05-05':'Incorrectstripsemantics; noimmutable-stringfixorleading-space-preservinglist.',
 'b50-05-06':'No shared-defaultstateexplanationorcorrectNone/copyfix.',
 'b50-05-09':'Literal{stock}placeholders; missesRuntimeErrorandidentity-preservingfilter.',
 'b50-05-10':'No latebindingexplanation; finalproposedcodeinvalidsyntaxandwrongbehavior.',
 'b50-06-01':'No shared-rowstateunderstanding; placeholdersinsteadcorrectgrids.',
 'b50-06-06':'Wrongrstripsemanticsandfix; nocorrectsuffixlogic.',
 'b50-08-01':'Wronggenerator/exhaustion/nextsemanticsandinvalidcode.',
 'b50-08-02':'Missesfinallyoverridingreturn; inventsfunctionsemantics.',
 'b50-08-03':'Firsttwofailchainedcomparison/inclusivebounds; finalxrecallcorrect.',
 'b50-08-04':'Wrongnegativeindicesandslice; wrongexcludedstopelement.',
 'b50-08-05':'MissesunpackingValueError; noextendedunpacking; wrongtargetcount.',
 'b50-08-06':'Wrongsort/sortedsemantics, outputandmethodrecall.',
 'b50-08-07':'Inventscurrenttime/result; missesmissingkeyversusNoneandwrongkeyrecall.',
 'b50-08-08':'Incorrectfloat/printsemanticsandcomparison; finaloperandsmentionedbutwrongadditionalclaimsremain.',
 'b50-08-09':'No correctenumerateexplanationorloop; finalstartcounterrecallcorrect.',
 'b50-08-10':'Wrongduplicatekeysemanticsandrepresentation; finalkeyrecallcorrect.'}
judgments=[]
for r in records:
 key=r['session'],r['turn'];judgments.append({'session':key[0],'turn':key[1],'pass':key in passes,'reason':passes.get(key,notes[key[0]]),'record_sha256':hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()})
assert len(notes)==60 and sum(j['pass'] for j in judgments)==6
report={'status':'full_root_review_complete','checkpoint_manifest_sha256':x['checkpoint_manifest_sha256'],'device':'mps','decoding':{'temperature':0,'repetition_penalty':1.0,'reply_budget':192},'suite_sha256':sha(P/'assessment.json'),'raw_reports':[{'path':str(p),'sha256':sha(p)} for p in [a,b]],'continuation':'First30minbudgetendedafter149turns; retained147complete-sessionturns andreranlastpartiallycompletedsessionwith10remainingones.2repeatedturnshadidenticaltext.182executedturns,180uniquereviewedturns.','turns_passed':6,'turns_total':180,'complete_sessions_passed':0,'complete_sessions_total':60,'per_category_complete_sessions':{k:{'passed':0,'total':20} for k in ['natural','tool','code_state']},'generation_status_counts':dict(collections.Counter(r['result']['status'] for r in records)),'criteria':'Fulluserrequest/rubric,correctfactsandactions,applicableformat. Acceptsemanticallyequivalentwordingandimplicitunitswhenunambiguous; rejectincorrectextraassertions. Bare83failsanexplicitexplanationrequest. Toolreferenceexactmatchisnotthesemanticjudge.','judgments':judgments,'usable_general_model':False,'finding':'Retained605runslocallybutfailsallcomplete3turnsessions. Someisolatedcalls/literalrecallwork; broadnaturalreasoningandPythonsemanticsarenotreliable.','training_targets_changed_from_assessment':False}
(P/'local-baseline-review.json').write_text(json.dumps(report,indent=2)+'\n');(R/'local-baseline-combined.json').write_text(json.dumps({**x,'status':'complete_combined_segments','records':records,'source_segments':report['raw_reports']},indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['judgments','criteria','continuation']},indent=2))
