import json,random,hashlib
from pathlib import Path
from sentencepiece import SentencePieceProcessor
P=Path(__file__).resolve().parent
R=P.parents[2]
sp=SentencePieceProcessor(model_file=str(R/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
def save(n,x): (P/n).write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
# Each authored row encodes a distinct event relationship; no sampled training/final material.
# domain | premise | query | answer | explanatory query | explanation | alternative answer | update
raw='''transport dispatch|The airport shuttle skips Elm stop because the road is closed.|Which stop is skipped?|Elm stop.|Why is Elm skipped?|The road is closed.|Birch stop.|The skipped stop is now Birch, not Elm.
transport dispatch|A spare van waits at bay seven while the main van loads at bay two.|Where is the spare van?|Bay seven.|Which van is loading?|The main van.|Bay nine.|The spare van has moved to bay nine.
transport dispatch|Mira checks tickets before the driver closes the bus doors.|What does Mira check?|Tickets.|What happens before the doors close?|Mira checks tickets.|Seat belts.|Mira checks seat belts instead of tickets.
transport dispatch|The express bus leaves at dusk; the local bus leaves at noon.|When does the express leave?|At dusk.|Which bus leaves earlier?|The local bus.|At dawn.|The express departure changes from dusk to dawn.
transport dispatch|Only the green route accepts bicycles; the silver route does not.|Which route accepts bicycles?|The green route.|Can a bicycle go on the silver route?|No, the silver route does not accept bicycles.|The silver route.|The rule reverses: only the silver route now accepts bicycles.
theater production|The actor enters through the left wing because the right wing holds scenery.|Which wing does the actor use?|The left wing.|Why avoid the right wing?|Scenery occupies it.|The rear wing.|The entrance changes to the rear wing; the scenery stays put.
theater production|The bell cue follows the blackout, and the curtain falls after the bell.|What follows the blackout?|The bell cue.|What comes last?|The curtain falls.|The drum cue.|Replace the bell cue with the drum cue; keep the order.
theater production|An amber spotlight marks the final speech; a white light marks the opening.|Which light marks the final speech?|An amber spotlight.|Does the white light mark the finale?|No, it marks the opening.|A violet spotlight.|The final speech now uses a violet spotlight.
theater production|The understudy reads the captain while the lead actor is away.|Who reads the captain?|The understudy.|Why is the understudy reading?|The lead actor is away.|The director.|The director now reads the captain instead.
theater production|The silent scene needs no microphone; the next scene uses two.|How many microphones does the silent scene need?|None.|Why reserve two microphones?|The next scene uses them.|One.|The revised silent scene needs one microphone.
urban park maintenance|Workers close the gravel path because a fallen branch blocks it.|Which path is closed?|The gravel path.|Why is the path closed?|A fallen branch blocks it.|The paved path.|The closure moves to the paved path; the gravel path reopens.
urban park maintenance|Watering starts after the litter round so the crew can walk on dry ground.|What happens first?|The litter round.|Why delay watering?|So the crew can walk on dry ground.|Watering.|The new order is watering first, then the litter round.
urban park maintenance|The east fountain is off, but the west fountain is running.|Which fountain is off?|The east fountain.|Are both fountains running?|No, the east fountain is off.|The west fountain.|The east fountain restarts and the west fountain stops.
urban park maintenance|A mesh fence protects new grass while the nearby benches remain open.|What protects the grass?|A mesh fence.|Can visitors still use the benches?|Yes, the benches remain open.|A rope barrier.|A rope barrier replaces the mesh fence.
urban park maintenance|The crew piles leaves beside the north gate, away from the drains.|Where are leaves piled?|Beside the north gate.|What must the leaf pile avoid?|The drains.|Beside the south gate.|Move the leaf pile beside the south gate, still away from drains.
fitness club scheduling|The stretching session is indoors because the terrace is booked.|Where is stretching held?|Indoors.|Why not use the terrace?|The terrace is booked.|On the terrace.|The terrace booking is cancelled; stretching moves there.
fitness club scheduling|A beginner session ends before the advanced session starts.|Which session ends first?|The beginner session.|Do the sessions overlap?|No, the beginner session ends before the advanced one starts.|The advanced session.|Reverse the schedule: the advanced session ends before the beginner session starts.
fitness club scheduling|Members reserve bikes on Monday; walk-ins can claim leftovers on Tuesday.|When can walk-ins claim bikes?|On Tuesday.|Who can reserve on Monday?|Members.|On Wednesday.|Walk-in allocation moves from Tuesday to Wednesday.
fitness club scheduling|The evening class has four vacancies, but the morning class is full.|Which class has vacancies?|The evening class.|Can another person join the morning class as listed?|No, it is full.|The morning class.|The evening class fills; four morning places open.
fitness club scheduling|Nia covers the warm-up while Dev handles the final stretch.|Who handles the final stretch?|Dev.|Does Nia handle the final stretch?|No, Nia covers the warm-up.|Nia.|Nia now handles the final stretch, and Dev covers the warm-up.'''
scenes=[]
for i,line in enumerate(raw.splitlines()):
 d,p,q,a,c,e,b,u=line.split('|');scenes.append(dict(domain=d,p=p,q=q,a=a,c=c,e=e,b=b,u=u,source_family=f'development-event-{i:02d}'))
full_explanations=[
'The road is closed.', 'The main van is loading.', 'Mira checks tickets before the doors close.',
'The local bus leaves earlier.', 'The silver route does not accept bicycles.',
'Scenery occupies the right wing.', 'The curtain falls last.', 'The white light marks the opening.',
'The lead actor is away.', 'The next scene uses two microphones.',
'A fallen branch blocks the path.', 'Watering is delayed so the crew can walk on dry ground.',
'The east fountain is off, so both fountains are not running.', 'Visitors can still use the benches.',
'The leaf pile must avoid the drains.', 'The terrace is booked.',
'The sessions do not overlap because the beginner session ends first.', 'Members can reserve on Monday.',
'Another person cannot join the morning class because it is full.', 'Nia covers the warm-up, not the final stretch.']
functions=['grounding','comprehension','clarification','correction','instructions','explanation'];structures=['direct_follow_up','correction_repair','interruption_return','multi_constraint']
dev=[]
for fi,f in enumerate(functions):
 for i in range(20):
  s=scenes[(i+fi*3)%20];st=structures[i//5]; p,q,a,c,e,b,u=[s[k] for k in ['p','q','a','c','e','b','u']]
  if f=='grounding':t=[(p+' '+q,a),(c,e)]
  elif f=='comprehension':t=[(p+' '+c,e),(q,a)]
  elif f=='clarification':t=[(p+' What date was this note written?','The date is not supplied.'),('The note was written on Friday. What date information do we have now?','It was written on Friday.')]
  elif f=='correction':t=[(p+' '+q,a),(u+' '+q,b)]
  elif f=='instructions':t=[(p+' Answer briefly: '+q,a),('In a complete sentence: '+c,full_explanations[scenes.index(s)])]
  else:t=[(p+' '+c+' Explain briefly.',e),(q,a)]
  answerability=i%5==0 or i//5==0
  if st=='correction_repair':
   t += [(u+' '+q,b)]
  elif st=='interruption_return':
   t += [('Separate notice: the noticeboard is purple. What color is it?','Purple.'),('Return to the earlier note. '+q,b if f=='correction' else a)]
  elif st=='multi_constraint':
   t += [('Give the answer to this question, then say whether a budget was supplied: '+q,(b if f=='correction' else a)+' No budget was supplied.')]
  elif f!='clarification':
   t += [('Does the note name its author?','No author is named.')]
  dev.append(dict(id=f'dev-{f}-{i:02d}',function=f,structure=st,domain=s['domain'],source_family=s['source_family'],concrete_values={k:s[k] for k in ['p','a','b']},interruption_continuity=st=='interruption_return',answerability_contrast=answerability or st=='multi_constraint' or f=='clarification',turns=[dict(user=x,reference=y,required_semantics=y,exact_match=False) for x,y in t]))
save('development.json',dev)
# Native prefixes: genuinely distinct situations across four prose registers.
texts={
'everyday':[
'The dispatcher arrived early and found two unsigned route sheets on the desk. She set aside her tea and',
'The theater lobby was quiet until a visitor asked where to leave a wet umbrella. The usher',
'A walker noticed that the park bench was damp. Instead of sitting down immediately, he',
'The club receptionist saw that two members had booked the same bike. She checked the list and',
'The driver could not read the faded bay number. He asked the dispatcher to',
'A stagehand found a scarf under the empty seats after the rehearsal. She',
'The park attendant had only one spare rubbish bag left. Before starting another round, he',
'A member arrived for a class that had moved to another room. The receptionist',
'The shuttle queue grew while a passenger searched for a ticket. Another staff member',
'The theater door stuck when the usher tried to open it. Rather than pulling harder, she',
'The park crew paused beside a drinking fountain that was not working. One worker',
'The club timetable was too high for a visitor to read. The receptionist',
'The dispatcher heard two radios speaking at once and missed the bay change. He',
'The rehearsal finished late, and the lighting crew still needed to pack up. They',
'The park visitor saw a loose sign beside the closed path. She told the attendant, who'],
'procedural':[
'To record a route change, first cross out the old stop. Then write the new stop clearly and',
'Before raising the theater curtain, check that the stage is clear. If anything blocks its path,',
'To close a park path, place a barrier at each entrance. Make sure that',
'To move a club booking, locate the original reservation first. After checking the new time is free,',
'When handing over a shuttle, record the bay and the next departure. Ask the incoming driver to',
'To test a sound cue, lower the volume first. Play the cue, listen, and then',
'Collect loose leaves before clearing a drain cover. This prevents',
'If a session is full, offer the waiting list. Do not confirm a place until',
'Check the destination on both the route sheet and the windscreen sign. If they disagree,',
'Label each prop box before stacking it. Keep the labels facing outward so',
'Before reopening a path, remove the obstruction and inspect the surface. Only then',
'When cancelling a class, update the booking list and the posted timetable. Finally,',
'For a radio check, state your call sign and wait for a reply. If none arrives,',
'To run a blackout rehearsal, warn the cast first. Keep an agreed signal ready in case',
'After watering the park beds, coil the hose away from the walking route. This keeps'],
'explanatory':[
'A shuttle timetable includes a short gap between trips because unloading takes time. Without that gap,',
'A theater cue sheet lists actions in order. This helps the operator',
'A barrier at both ends of a closed park path prevents visitors from',
'A waiting list records interest without promising a place. A member on that list',
'A spare vehicle can cover a delayed departure, but only if a driver is available. Having the vehicle alone',
'A rehearsal can stop and repeat a difficult entrance. A public performance usually continues, so rehearsal gives the cast',
'Grass beside a busy path wears down faster because people step off the pavement. A low fence',
'Two club sessions can share a room if their times do not overlap. The timetable must also allow',
'A radio message that names the route is easier to act on than a message saying only "that bus." The route name',
'Soft scenery can reduce reflected sound, changing how clearly speech reaches the seats. For that reason, the sound check',
'Leaves caught against a drain cover can slow the flow of rainwater. Removing the leaves',
'A booking limit reflects the number of available places. Once those places are reserved,',
'A detour may serve the same destination while missing some stops. Passengers need to know',
'A cue light gives a visible signal without adding sound to a quiet scene. The performer can',
'Watering a path by mistake makes its surface wet without helping the planted beds. A carefully aimed hose'],
'narrative':[
'Leena watched the last shuttle pull away before she noticed the forgotten route folder. She ran to the radio desk and',
'The actor reached for the letter, but the prop table was empty. Behind the curtain, a stagehand',
'A gust sent the park crew\'s empty bags rolling across the path. Ravi caught one against his boot and',
'When the club clock stopped, nobody noticed until two groups arrived together. The receptionist looked from one booking slip to the other and',
'The dispatcher had just announced bay four when a driver pointed to a cone blocking it. She picked up the microphone again and',
'The rehearsal bell rang too early. For a moment the cast froze; then the director',
'At dawn the park keeper found fresh footprints across the newly raked gravel. He followed them as far as',
'A visitor held an old club timetable and insisted the class began now. The receptionist turned the sheet over and',
'The bus doors opened, but the waiting passengers stayed still. The destination sign showed the wrong route. The driver',
'The curtain caught on a chair leg during the final rehearsal. Arun heard the fabric pull tight and',
'A gardener set down the hose to answer a question. When she turned back, water was running across the path, so',
'The final club session had ended, yet a bag remained beside the bench. The attendant',
'Rain blurred the handwritten shuttle notice. Salma sheltered it with her folder while her colleague',
'The substitute actor entered from the wrong wing and faced an empty stage. After a brief pause, the director',
'The park gate was almost shut when the keeper heard someone calling from the far path. She stopped and']}
cont=[]
for d,arr in texts.items():
 for i,p in enumerate(arr):cont.append(dict(id=f'native-{d}-{i:02d}',domain=d,prefix=p,source_family=f'native-{d}-original-{i:02d}',concrete_values=p,cap=64,grading='At least one complete grammatical sentence; preserve premise/entities, relevance and logical continuity; no material contradiction or repetition. Ignore only final cap-cut fragment.'))
save('native_continuations.json',cont)
# Thirty authored fact bundles; four different retrieval questions per bundle.
graw='''everyday|At the bus depot, Tessa logs a missing wheel cover in the morning because loose parts must be traced.|Tessa|the bus depot|the morning|loose parts must be traced
procedural|At the stage desk, Malik checks the cue list before rehearsal to catch skipped cues.|Malik|the stage desk|before rehearsal|to catch skipped cues
explanatory|At the park gate, Ivo counts bags at noon because the stock ledger needs a daily total.|Ivo|the park gate|noon|the stock ledger needs a daily total
narrative|After closing, Yara discovered a stray booking slip at the club desk and filed it to preserve the reservation.|Yara|the club desk|after closing|to preserve the reservation
everyday|At the west bay, Oren wipes a fogged destination board at dawn so riders can read it.|Oren|the west bay|dawn|so riders can read it
procedural|Before the show, Cleo tests the backstage bell in the control booth to verify the signal.|Cleo|the control booth|before the show|to verify the signal
explanatory|Every afternoon, Uma inspects the park drain beside the pond because fallen leaves gather there.|Uma|beside the pond|every afternoon|fallen leaves gather there
narrative|During the lunch break, Felix took the new timetable to the club entrance so late arrivals would see the change.|Felix|the club entrance|during the lunch break|so late arrivals would see the change
everyday|After the first trip, Niko returns a borrowed radio to the dispatch desk because another driver needs it.|Niko|the dispatch desk|after the first trip|another driver needs it
procedural|At the costume rail, Suri counts the capes before packing to detect missing items.|Suri|the costume rail|before packing|to detect missing items
explanatory|At sunset, Bo moves a hose to the park shed because the path must remain clear.|Bo|the park shed|sunset|the path must remain clear
narrative|Before the doors opened, Esme placed a waiting-list notice beside the club lift to direct members with no booking.|Esme|beside the club lift|before the doors opened|to direct members with no booking
everyday|At the turnround bay, Pavel records arrival times each evening because dispatch needs a delay log.|Pavel|the turnround bay|each evening|dispatch needs a delay log
procedural|After the curtain call, Lila checks under the stage stairs to find dropped props.|Lila|under the stage stairs|after the curtain call|to find dropped props
explanatory|Before watering, Rafi marks the park work area near the oak because visitors need a clear boundary.|Rafi|near the oak|before watering|visitors need a clear boundary
narrative|At daybreak, Ada opened the club side door to let the timetable installer enter.|Ada|the club side door|daybreak|to let the timetable installer enter
everyday|At the route office, Ken compares detour maps on Tuesday because two editions disagree.|Ken|the route office|Tuesday|two editions disagree
procedural|At the lighting desk, Juno saves the cue file after each rehearsal to retain the changes.|Juno|the lighting desk|after each rehearsal|to retain the changes
explanatory|On Thursday, Zed closes the park footbridge because a loose board needs repair.|Zed|the park footbridge|Thursday|a loose board needs repair
narrative|At the club hall, Mina moved the sign before the evening session so the new room number was visible.|Mina|the club hall|before the evening session|so the new room number was visible
everyday|At the coach stand, Daro sorts lost tickets in the late morning to match them with waiting passengers.|Daro|the coach stand|the late morning|to match them with waiting passengers
procedural|Before a scene change, Elin clears the center stage to make room for the next backdrop.|Elin|the center stage|before a scene change|to make room for the next backdrop
explanatory|At the north lawn, Hugo sets out cones after rain because the ground is too soft to cross.|Hugo|the north lawn|after rain|the ground is too soft to cross
narrative|After the final session, Iris collected the club sign-in sheets at reception to count attendance.|Iris|reception|after the final session|to count attendance
everyday|At the tram shelter, Veda replaces a torn route notice on Saturday so the stop list is readable.|Veda|the tram shelter|Saturday|so the stop list is readable
procedural|At the prompt corner, Noel marks pauses before the reading to help the substitute follow the script.|Noel|the prompt corner|before the reading|to help the substitute follow the script
explanatory|After leaf collection, Pia weighs the bags at the park yard because the disposal record uses weight.|Pia|the park yard|after leaf collection|the disposal record uses weight
narrative|At the club kiosk, Quinn corrected a duplicate booking before midday to release the extra place.|Quinn|the club kiosk|before midday|to release the extra place
everyday|At the bus turning circle, Rosa removes an empty crate after unloading because it blocks the next vehicle.|Rosa|the bus turning circle|after unloading|it blocks the next vehicle
procedural|At the fly rail, Theo checks the rope labels before setup to avoid raising the wrong backdrop.|Theo|the fly rail|before setup|to avoid raising the wrong backdrop'''
grows=[x.split('|') for x in graw.splitlines()]
register_passages={
1:'Before rehearsal, Malik must work at the stage desk. First check the cue list to catch skipped cues; then hand the checked list to the operator.',
5:'Before the show, Cleo must go to the control booth. Test the backstage bell to verify the signal, and only then mark the check complete.',
9:'Before packing, Suri should count the capes at the costume rail to detect missing items. Finish the count before moving any cape into a box.',
13:'After the curtain call, Lila should check under the stage stairs to find dropped props. Look through the space before putting the stair cover back.',
17:'At the lighting desk, Juno should save the cue file after each rehearsal to retain the changes. Save first, then close the file.',
21:'Before a scene change, Elin must clear the center stage to make room for the next backdrop. Remove the old scenery before bringing in the backdrop.',
25:'At the prompt corner, Noel should mark pauses before the reading to help the substitute follow the script. Mark the pauses first, then hand over the script.',
2:'At the park gate, Ivo counts bags at noon because the stock ledger needs a daily total. The count supplies that total, allowing the ledger to show how many bags remain.',
6:'Every afternoon, Uma inspects the park drain beside the pond because fallen leaves gather there. The drain catches leaves carried toward it, so repeated inspection reveals fresh buildup.',
10:'At sunset, Bo moves a hose to the park shed because the path must remain clear. Storing the hose removes it from the walking route and leaves room for visitors.',
14:'Before watering, Rafi marks the park work area near the oak because visitors need a clear boundary. The marks show where the work area ends and the walking space begins.',
18:'On Thursday, Zed closes the park footbridge because a loose board needs repair. Closing the bridge keeps visitors off the board while the repair is pending.',
22:'At the north lawn, Hugo sets out cones after rain because the ground is too soft to cross. The cones mark an area where footsteps would disturb the softened ground.',
26:'After leaf collection, Pia weighs the bags at the park yard because the disposal record uses weight. Weighing supplies the measure needed for that record.',
3:'After closing, Yara noticed a stray booking slip at the club desk. She read it, then filed it to preserve the reservation before leaving.',
7:'During the lunch break, Felix saw people reading the old room notice. He took the new timetable to the club entrance so late arrivals would see the change, then removed the old notice.',
11:'Before the doors opened, Esme found visitors waiting near the club lift. She placed a waiting-list notice beside the club lift to direct members with no booking, then opened reception.',
15:'At daybreak, Ada heard a knock at the club side door. She opened it to let the timetable installer enter, and the visitor carried the new board inside.',
19:'At the club hall, Mina spotted the old room number on a sign. Before the evening session, she moved the sign so the new room number was visible, then checked it from the doorway.',
23:'After the final session, Iris found a stack of sign-in sheets at reception. She collected the club sign-in sheets at reception to count attendance, then sat down with the register.',
27:'At the club kiosk, Quinn found two entries for one booking. Before midday, Quinn corrected the duplicate booking to release the extra place, then refreshed the list.'}

# Assign 30 questions/register: first 28 bundles give 28 each; last two give two each.
ground=[]
for i,row in enumerate(grows):
 d,p,*vals=row
 p=register_passages.get(i,p)
 for j,(q,field) in enumerate(zip(['Who performs the action?','Where does the action happen?','When does the action happen?','What reason is given for the action?'],['actor','location','time','reason'])):
  domain=d if i<28 else list(texts)[j//2+2*(i-28)]
  if i==28 and domain=='procedural':
   p='At the bus turning circle, Rosa should remove the empty crate after unloading because it blocks the next vehicle. Clear the crate before calling that vehicle forward.'
  if i==29 and domain=='explanatory':
   p='At the fly rail, Theo checks the rope labels before setup to avoid raising the wrong backdrop. The labels identify which rope moves each backdrop, preventing a mistaken selection.'
  if i==29 and domain=='narrative':
   p='Before setup, Theo reached the fly rail and paused over two similar ropes. Theo checked the rope labels at the fly rail to avoid raising the wrong backdrop, then selected the correct rope.'
  opts=[vals[j]]+[grows[(i+k)%30][j+2] for k in [7,13,19]]
  pos=(i+j)%4;opts=opts[-pos:]+opts[:-pos] if pos else opts
  ground.append(dict(id=f'ground-{i:02d}-{j}',domain=domain,passage=p,question=q,options=opts,correct_index=pos,source_family=f'ground-original-event-{i:02d}',concrete_values=dict(zip(['actor','location','time','reason'],vals))))
# Domain is actual prose register. Last two event bundles have explicit per-question register renderings.
for x in ground:
 x['prefix']=x['passage']+'\n'+x['question']+'\nAnswer:'
 x['suffixes']=[' '+v+'.' for v in x['options']]
 ids=[sp.bos_id()]+sp.encode(x['prefix']);joint=[[sp.bos_id()]+sp.encode(x['prefix']+s) for s in x['suffixes']]
 x['joint_encoding']={'prefix_ids':ids,'full_ids':joint,'suffix_start':len(ids),'verified_exact_prefix':all(z[:len(ids)]==ids for z in joint),'score':'sum_log_probability_of_joint_encoded_suffix'}
 assert x['joint_encoding']['verified_exact_prefix']
# Balanced correct answer position exactly30 each. Controls retain identical question/options/key.
for i,x in enumerate(ground):
 donor=ground[(i+44)%120]
 assert donor['source_family']!=x['source_family']
 x['controls']={'empty_passage_prefix':x['question']+'\nAnswer:','shuffled_passage_prefix':donor['passage']+'\n'+x['question']+'\nAnswer:','shuffled_donor':donor['id']}
 for name,prefix in x['controls'].copy().items():
  if name.endswith('prefix'):
   ids=[sp.bos_id()]+sp.encode(prefix);full=[[sp.bos_id()]+sp.encode(prefix+s) for s in x['suffixes']];assert all(z[:len(ids)]==ids for z in full)
   x['controls'][name+'_joint_encoding']={'prefix_ids':ids,'full_ids':full,'suffix_start':len(ids)}
save('grounded_choices.json',ground)
# Full-sentence contrasts; shared prefix ends before complete option so no standalone-token mismatch.
grammar_raw='''The dispatcher checks the list.|The dispatcher check the list.
The drivers know the route.|The drivers knows the route.
The bus was late.|The bus were late.
The vans were ready.|The vans was ready.
She has checked the bay.|She have checked the bay.
They have left the depot.|They has left the depot.
He does not drive today.|He do not drive today.
We do not need a spare.|We does not need a spare.
The driver can wait.|The driver can waits.
The actor must enter now.|The actor must enters now.
The crew will return.|The crew will returned.
She should have checked.|She should has checked.
He is reading the script.|He is read the script.
They are moving the scenery.|They are move the scenery.
She was waiting outside.|She was wait outside.
The doors have been closed.|The doors have be closed.
The note was written clearly.|The note was wrote clearly.
The path is being cleared.|The path is being clear.
The crew had finished before noon.|The crew had finish before noon.
The driver went inside.|The driver goed inside.
The actor spoke quietly.|The actor speaked quietly.
The keeper brought a rake.|The keeper bringed a rake.
The attendant saw the sign.|The attendant seen the sign.
The rope broke during rehearsal.|The rope broken during rehearsal.
The workers kept the path clear.|The workers keeped the path clear.
The club has fewer bookings today.|The club has fewer booking today.
There is a spare chair.|There are a spare chair.
There are two open places.|There is two open places.
Each driver has a radio.|Each driver have a radio.
Neither route stops here.|Neither route stop here.
Both actors are ready.|Both actors is ready.
One of the gates is locked.|One of the gates are locked.
The list of cues is short.|The list of cues are short.
The signs beside the gate are new.|The signs beside the gate is new.
This notice is clear.|These notice is clear.
Those benches are wet.|That benches are wet.
She gave him the folder.|She gave he the folder.
The director spoke to us.|The director spoke to we.
They asked her to wait.|They asked she to wait.
He and I checked the room.|Him and me checked the room.
The driver parked his van.|The driver parked he van.
The members brought their cards.|The members brought they cards.
We checked it ourselves.|We checked it ourself.
She prepared herself for the cue.|She prepared himself for the cue.
The actor whose cue was missed waited.|The actor who cue was missed waited.
The chair that broke was removed.|The chair what broke was removed.
I know where the route ends.|I know where does the route end.
Do you know when the class starts?|Do you know when does the class start?
Why did the bus stop?|Why did the bus stopped?
Where are the keys?|Where the keys are?
She asked whether the gate was open.|She asked whether was the gate open.
Please tell me what changed.|Please tell me what did changed.
The crew decided to wait.|The crew decided waiting.
The actor avoided stepping on the cable.|The actor avoided to step on the cable.
The attendant enjoys arranging the timetable.|The attendant enjoys to arrange the timetable.
They made the driver wait.|They made the driver to wait.
Let the visitors enter.|Let the visitors to enter.
The bus is too large to turn here.|The bus is too large turning here.
The path is wide enough for two people.|The path is enough wide for two people.
If the gate opens, we will enter.|If the gate open, we will enter.'''
gram=[]
for i,line in enumerate(grammar_raw.splitlines()):
 good,bad=line.split('|');opts=[good,bad] if i%2==0 else [bad,good];prefix='English sentence:';ids=[sp.bos_id()]+sp.encode(prefix);full=[[sp.bos_id()]+sp.encode(prefix+' '+s) for s in opts];assert all(z[:len(ids)]==ids for z in full)
 gram.append(dict(id=f'grammar-{i:02d}',source_family=f'grammar-contrast-{i:02d}',prefix=prefix,options=opts,correct_index=i%2,joint_encoding={'prefix_ids':ids,'full_ids':full,'suffix_start':len(ids),'verified_exact_prefix':True,'score':'sum_log_probability_of_joint_encoded_suffix'}))
save('grammar_contrasts.json',gram)
# Calibration additions deliberately distinguish clear errors from contested adequacy.
newraw=[
('Accept','The shuttle now leaves at 17:20, replacing 17:00. Give the current departure.','17:20.','What was the old time?','17:00.','Correct current and superseded state.'),
('Fail','The stage door is locked. The lobby door is open. Which door is open?','The stage door.','Which door is locked?','The lobby door.','Both answers contradict the supplied state.'),
('Borderline','The bus cannot enter the narrow lane. Explain why passengers walk to the main road.','The lane is unsuitable.','What prevents the bus entering?','Its size.','Vague first explanation and inferred vehicle dimension rather than stated lane width.'),
('Borderline','The rehearsal is postponed because the lights failed. Write a useful notice.','Rehearsal postponed.','Should the notice give a new time?','Not yet.','Bare notice omits cause but no explicit requirement to include cause; adequacy uncertain.'),
('Borderline','A path is wet and a dry detour is open. Suggest what a visitor could do.','Take care.','Which route avoids the wet surface?','The detour.','First advice is relevant but may be too vague to satisfy requested practical action.'),
('Borderline','The club session moved from room A to room C. Tell a late arrival where to go.','Try C.','Which room is listed now?','Room C.','Unnecessary uncertainty weakens an otherwise correct direction.'),
('Borderline','The shuttle leaves after the driver checks tickets. Explain the order.','Tickets come first.','What comes after the check?','Departure.','First answer may convey order adequately but omits explicit checking act.'),
('Borderline','The actor waits for a blue cue light. Explain what tells her to enter.','The light changing.','What color is the cue?','Blue.','Unspecified change may be adequate shorthand or insufficiently identify required cue.'),
('Borderline','The park crew leaves a gap in the barrier for workers. Explain the gap to a visitor.','Access.','Whose access?','Workers.','Single noun leaves first requested explanation materially underspecified.'),
('Borderline','Only reserved places are guaranteed at the club. Explain this to a walk-in.','You may wait.','Is a place guaranteed without a reservation?','No.','Possible waiting is compatible but does not directly explain guarantee limitation.'),
('Borderline','A spare driver is available if the first driver is delayed. Describe the backup plan.','Someone can cover.','Who is available?','The spare driver.','First answer omits triggering condition and specific backup; adequacy contested.'),
('Borderline','The stage crew mutes the speaker during a silent scene. Why?','For silence.','Does the speaker stay on?','No.','Tautological but potentially sufficient causal explanation; conservative non-pass.')]
old=json.loads((R/'restart/phase-a-2026-10-28/acceptance-examples.json').read_text());adj=json.loads((R/'restart/phase-a-2026-10-28/review-adjudication.json').read_text());by={x['anchor_id']:x for x in adj['cases']};anchors=[]
for x in old:
 z=by[x['id']];anchors.append(dict(origin=x['id'],grade=z['adjudicated_grade'],reason=z['reason'],turns=[{'user':t['user'],'assistant':t['assistant']} for t in x['turns']]))
for i,(grade,u,a,u2,a2,reason) in enumerate(newraw):anchors.append(dict(origin=f'new-{i:02d}',grade=grade,reason=reason,turns=[dict(user=u,assistant=a),dict(user=u2,assistant=a2)]))
random.Random(291029).shuffle(anchors)
blind=[];key=[]
for i,a in enumerate(anchors):
 aid=f'cal-{i+1:02d}';blind.append(dict(id=aid,turns=a['turns']));key.append(dict(id=aid,origin=a['origin'],grade=a['grade'],reason=a['reason']))
save('calibration_blind.json',blind);save('private/calibration_key.json',key)
# CPU-only context proof matches historical native serializer: BOS + separately encoded user frames + generated assistant cap.
lengths=[]
for x in dev:
 used=1
 for t in x['turns']:
  used+=len(sp.encode('User: '+t['user']+'\nAssistant:'))
  t['worst_prefix_tokens']=used;t['reference_tokens_including_eos']=len(sp.encode(t['reference']))+1
  assert t['reference_tokens_including_eos']<=32,(x['id'],t)
  used+=32
 x['worst_history_tokens_including_last_reply']=used;lengths.append(used)
 assert used<=256,(x['id'],used)
save('development.json',dev)
from collections import Counter
assert len(cont)==60 and len(ground)==120 and len(gram)==60 and len(dev)==120
assert Counter(x['domain'] for x in ground)==dict.fromkeys(texts,30),Counter(x['domain'] for x in ground)
assert Counter(x['correct_index'] for x in ground)==dict.fromkeys(range(4),30)
assert max(len(sp.encode(x['prefix'])) for x in cont)<=128
for f in functions:
 ds=[x for x in dev if x['function']==f];assert len(ds)==20 and sum(x['interruption_continuity'] for x in ds)>=5 and sum(x['answerability_contrast'] for x in ds)>=5
assert Counter(x['structure'] for x in dev)==dict.fromkeys(structures,30)
save('author_validation.json',dict(status='AUTHORED_AWAITING_INDEPENDENT_REVIEW',counts=dict(native=len(cont),grounded=len(ground),grammar=len(gram),development=len(dev),calibration=len(blind)),development_turns=sum(len(x['turns']) for x in dev),max_worst_history_tokens=max(lengths),max_native_prefix=max(len(sp.encode(x['prefix'])) for x in cont),calibration_provisional_labels=dict(Counter(x['grade'] for x in key)),teacher_calls=0,student_calls=0,tokenizer=str(R/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'),hashes={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in ['development.json','native_continuations.json','grounded_choices.json','grammar_contrasts.json','calibration_blind.json']}))
print((P/'author_validation.json').read_text())
