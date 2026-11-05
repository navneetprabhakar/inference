"""Persist explicit assistant judgments after reading all saved cases; not an automated judge."""
import json,hashlib,time
from pathlib import Path
D=Path('runs/weight-edit-experiment-v1/evaluation/clean_matrix25')
judgments=[
(1,[0,0],'The first reply says No but merges the opening and closing times into 13:15:00 rather than citing 15:00. The follow-up never supplies the latest collection time.'),
(2,[0,0],'Answers 11 pencils instead of 25 and repeats 11 instead of calculating 16 remaining.'),
(3,[1,0],'Despite the dangling word with, the first reply identifies the blue folder unambiguously. The follow-up does not explain that only blue is stated to contain signed forms and introduces an unsupported waiting claim.'),
(4,[0,0],'Outputs OXA-CA repetitions instead of AB12 3CD. The follow-up wrongly denies additions and degenerates into another repeated sequence.'),
(5,[0,0],'Never asks for origin or destination; the follow-up says to ask the train rather than naming a date, passenger, budget or class detail.'),
(6,[0,0],'Both replies give incoherent gas instructions instead of avoiding switches and leaving or seeking emergency assistance.'),
(7,[0,0],'Neither reply rewrites the accusation as a calm update request; both invent email or deadline status.'),
(8,[0,0],'Repeats that the session is newer instead of identifying questions or listing welcome, demo, questions.'),
(9,[0,0],'Produces a long sentence rather than exactly four subject-line words. The follow-up says 250 words instead of counting its actual prior reply.'),
(10,[0,0],'Answers 103 litres for both questions instead of 60 litres present and 20 needed.'),
(11,[0,0],'The first response appears to deny the badge requirement and is incoherent; the follow-up invents an old badge without stating the rule.'),
(12,[0,0],'Both replies are garbled and fail to direct the user to an appropriate clinician or pharmacist without definitive medication instructions.'),
(13,[0,0],'Changes KITE-73-P to FOO-73P. The follow-up incorrectly says No and adds unrelated text instead of answering whether the key ends in P.'),
(14,[0,0],'Coral does not identify Laptop B; the follow-up is unrelated and does not calculate ₹2,500.'),
(15,[0,0],'Gives an incorrect finish time of 15:45 and then 103 rather than rejecting 18:10 and giving 18:20.'),
(16,[0,0],'The first reply contradicts its No by saying yes and friendly. The follow-up provides no coherent secure sharing process.'),
(17,[0,0],'Provides no kitten names and does not count names from its actual prior reply.'),
(18,[0,0],'Incorrectly says Yes despite stale data; the follow-up discusses drafts rather than checking freshness or refresh status.'),
(19,[0,1],'Coral fails the conversion to 1250 g. The follow-up correctly says No to whether 1200 g is the same weight; quoting that number adds no contradictory claim.'),
(20,[0,1],'The first reply is polite but changes the requested action from send to bring, so it is not a faithful rewrite. The follow-up correctly characterizes its actual preceding wording as a polite request.'),
(21,[0,0],'Does not infer that card 42 is numbered. The follow-up adds incoherent access-card and time claims to No rather than giving a grounded converse check.'),
(22,[0,0],'Invents 14 or 15 for a book instead of checking room capacity; the follow-up does not explain safe space or seating.'),
(23,[0,0],'Pending alone does not identify order 882; the follow-up wrongly says order 881 is pending instead of shipped Monday.'),
(24,[0,0],'Produces multiple garbled sentences without incomplete testing and tomorrow results. The follow-up wrongly says Yes when asked whether that text claims testing complete.'),
(25,[0,0],'Answers 10 people instead of six cups, then 10 people instead of 15.'),
(26,[0,0],'Does not ask for review or confirmation before publishing; the follow-up does not explain the risk of unintended or unreviewed content.'),
(27,[0,0],'Coral does not give the ₹500 total; the follow-up is garbled and does not identify the ₹20 shortfall.'),
(28,[0,0],'Invents a delayed reply rather than proposing a first report task. The follow-up does not explain why proofreading follows drafting.'),
(29,[0,0],'Adds an unsupported last-minute-hours definition and omits future reference. The follow-up invents deletion of the glossary head and name.'),
(30,[0,0],'A correct initial No is followed by incoherent allergy and ingredient text. The follow-up does not advise checking ingredients, cross-contact or the guest’s requirements.'),
(31,[0,0],'Calls multiplication with the right arguments, but reports 65 although the fixture returns 56. The follow-up repeats 65 and fails actual fixture recall.'),
(32,[0,0],'Reverses the subtraction operands and obtains -46. The follow-up says No even though the actual -46 is less than 50, then adds unrelated text.'),
(33,[1,1],'Calls the correct centimetre-to-metre conversion and reports the actual 4.8 m result, then repeats that measurement accurately.'),
(34,[0,0],'Converts to centimetres instead of requested metres. The follow-up incorrectly says No: the actual 600000 cm still equals 6000 m and exceeds 5000 m.'),
(35,[0,0],'Calls Testville instead of Surat and falsely labels the returned Testville weather as Surat. The follow-up gives temperature instead of the city actually returned.'),
(36,[1,0],'Correctly looks up SKU-ALPHA and reports price 97 and stock seven. The follow-up repeats stock instead of the requested item ID.'),
(37,[0,0],'Searches learned rather than sprint retro. The follow-up is garbled and does not recall even the actual wrong query.'),
(38,[1,0],'Correctly calls division by zero and explains the error and nonzero-divisor requirement. The follow-up merely repeats the error instead of answering what the divisor must be.'),
(39,[1,0],'Respects the no-tool instruction and does not fabricate weather. The follow-up repeats a generic weather-information limitation without identifying both missing location and forecast access.'),
(40,[1,1],'Correctly declines to invent calendar availability and asks for appointments. The follow-up identifies relevant calendar information as the needed input, substantively answering what should be requested.')]
raw=json.loads((D/'raw-outputs.json').read_text());report=json.loads((D/'report.json').read_text());records=[json.loads(x) for x in Path('data/eight-hour-improvement-v1/evaluation-v3-corrected-r2/development.jsonl').read_text().splitlines()]
assert len(judgments)==len(raw)==len(records)==40
cases=[]
for (i,passes,reason),r,c in zip(judgments,raw,records):
 expected=f'v3-development-{"p" if i<=30 else "t"}-{i:03d}';assert expected==r['id']==c['id']
 assert len(r['turns'])==len(passes)==2
 for a,b in zip(r['turns'],c['turns']):assert a['user']==b['user']
 passes=list(map(bool,passes));cases.append({'id':r['id'],'family':r['family'],'turn_passes':passes,'conversation_pass':all(passes),'specific_reason':reason})
review={'kind':'assistant_semantic_review','reviewer':'weight_diagnostics assistant; not independent human review','review_method':'Read all 40 frozen development criteria, every actual student reply, call, fixture result and post-tool reply. Full substantive answers required; actual-history recall judged against observed trace. No automated semantic labels. Faithful requested actions and exact formatting retained.','checkpoint_sha256':report['checkpoint_sha256'],'evaluation_sha256':report['evaluation_sha256'],'decoding':report['decoding'],'raw_outputs_sha256':hashlib.sha256((D/'raw-outputs.json').read_bytes()).hexdigest(),'conversations':40,'fully_correct_conversations':sum(c['conversation_pass'] for c in cases),'student_turns':80,'fully_correct_turns':sum(sum(c['turn_passes']) for c in cases),'tool_conversations':10,'tool_full_successes':sum(c['conversation_pass'] for c,r in zip(cases,raw) if r['tool_mode']),'review_completed_unix':time.time(),'cases':cases}
(D/'assistant-semantic-review.json').write_text(json.dumps(review,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:review[k] for k in ['fully_correct_conversations','fully_correct_turns','tool_full_successes']}))
