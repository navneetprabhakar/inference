"""One authorized prelaunch repair batch; never run after v2 receipt exists."""
from pathlib import Path
P=Path(__file__).resolve().parent
assert not (P/'repair_v2.json').exists()
p=P/'build.py';s=p.read_text()
s=s.replace("elif f=='instructions':t=[(p+' Answer briefly: '+q,a),('In a complete sentence: '+c,e)]", "elif f=='instructions':t=[(p+' Answer briefly: '+q,a),('In a complete sentence: '+c,full_explanations[scenes.index(s)])]")
insert="""full_explanations=[
'The road is closed.', 'The main van is loading.', 'Mira checks tickets before the doors close.',
'The local bus leaves earlier.', 'The silver route does not accept bicycles.',
'Scenery occupies the right wing.', 'The curtain falls last.', 'The white light marks the opening.',
'The lead actor is away.', 'The next scene uses two microphones.',
'A fallen branch blocks the path.', 'Watering is delayed so the crew can walk on dry ground.',
'The east fountain is off, so both fountains are not running.', 'Visitors can still use the benches.',
'The leaf pile must avoid the drains.', 'The terrace is booked.',
'The sessions do not overlap because the beginner session ends first.', 'Members can reserve on Monday.',
'Another person cannot join the morning class because it is full.', 'Nia covers the warm-up, not the final stretch.']
"""
s=s.replace("functions=['grounding'",insert+"functions=['grounding'")
s=s.replace("mean_log_probability_of_joint_encoded_suffix","sum_log_probability_of_joint_encoded_suffix")
s=s.replace("ids=sp.encode(x['prefix']);joint=[sp.encode(x['prefix']+s) for s in x['suffixes']]", "ids=[sp.bos_id()]+sp.encode(x['prefix']);joint=[[sp.bos_id()]+sp.encode(x['prefix']+s) for s in x['suffixes']]")
s=s.replace("ids=sp.encode(prefix);full=[sp.encode(prefix+s) for s in x['suffixes']]", "ids=[sp.bos_id()]+sp.encode(prefix);full=[[sp.bos_id()]+sp.encode(prefix+s) for s in x['suffixes']]")
s=s.replace("ids=sp.encode(prefix);full=[sp.encode(prefix+' '+s) for s in opts]", "ids=[sp.bos_id()]+sp.encode(prefix);full=[[sp.bos_id()]+sp.encode(prefix+' '+s) for s in opts]")
# Seven procedural and seven narrative passages: real instruction/order and event prose, not relabeling.
insert="""register_passages={
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
"""
s=s.replace("grows=[x.split('|') for x in graw.splitlines()]", "grows=[x.split('|') for x in graw.splitlines()]\n"+insert)
s=s.replace("d,p,*vals=row\n for j,", "d,p,*vals=row\n p=register_passages.get(i,p)\n for j,")
s=s.replace("domain=d if i<28 else list(texts)[j//2+2*(i-28)]", """domain=d if i<28 else list(texts)[j//2+2*(i-28)]
  if i==28 and domain=='procedural':
   p='At the bus turning circle, Rosa should remove the empty crate after unloading because it blocks the next vehicle. Clear the crate before calling that vehicle forward.'
  if i==29 and domain=='explanatory':
   p='At the fly rail, Theo checks the rope labels before setup to avoid raising the wrong backdrop. The labels identify which rope moves each backdrop, preventing a mistaken selection.'
  if i==29 and domain=='narrative':
   p='Before setup, Theo reached the fly rail and paused over two similar ropes. Theo checked the rope labels at the fly rail to avoid raising the wrong backdrop, then selected the correct rope.'""")
s=s.replace("# Domain is prose presentation register; last bundles are explicitly labeled mixed short notices.","# Domain is actual prose register. Last two event bundles have explicit per-question register renderings.")
p.write_text(s)
