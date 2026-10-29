"""CPU-only authored development cases. No student inference or training."""
import json,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'phase-a-2026-10-28'))
from build import serial,sp
# Each tuple is an independently authored scenario, not a slot substitution.
# Each turn supplies a user request and one admissible reference, not an exhaustive answer key.
CASES=[
('grounding','corrected_location',[
('The red key is in the drawer. The blue key is in the bowl. Where is the red key?','In the drawer.'),
('Move only the red key to the hook. Where is it now?','On the hook.'),
('New topic: the shop closes at 19:10. Give the closing time.','19:10'),
('Back to the keys. Where is the blue key?','In the bowl.')]),
('grounding','ownership_vs_borrower',[
('Lena owns the camera. Omar borrowed it. Who owns it?','Lena owns the camera.'),
('Who borrowed the camera?','Omar.'),
('Separate note: the room is upstairs. Where is the room?','Upstairs.'),
('Back to the camera: did borrowing make Omar its owner?','No. Lena still owns it.')]),
('grounding','negated_attribute',[
('The mug is not blue; it is white. What color is it?','White.'),
('The plate is blue. Give only the plate color.','Blue.'),
('A bell rings at noon. When does it ring?','At noon.'),
('Return to the mug. Is it the same color as the plate?','No. The mug is white and the plate is blue.')]),
('grounding','missing_then_supplied',[
('The parcel has no sender listed. Who sent it?','The sender is not supplied.'),
('A new label says the sender is Arun. Who sent it?','Arun.'),
('The door code is 482. Repeat the code.','482'),
('Return to the parcel. Name the sender and say whether a delivery date was supplied.','Arun is the sender. No delivery date was supplied.')]),
('comprehension','cause_and_location',[
('Rain entered the shed, so Jo moved the seeds indoors. Why move them?','To protect the seeds from the rain.'),
('Where are the seeds now?','Indoors.'),
('The bakery opens at eight. When does it open?','At eight.'),
('Back to Jo: where are the seeds, and does the note say they were ruined?','Indoors. The note does not say they were ruined.')]),
('comprehension','temporal_sequence',[
('Mia washed a cup, dried it, then packed it. What happened immediately after washing?','Mia dried the cup.'),
('What happened last?','Mia packed the cup.'),
('The bus is green. Give its color.','Green.'),
('Back to the cup. Was it packed before it was dried?','No. It was dried before being packed.')]),
('comprehension','conditional_rule',[
('If the gate is locked, use the side door. The gate is locked. Which way should I go?','Use the side door.'),
('Now the gate is open. Does that rule still require the side door?','No. The rule applies when the gate is locked.'),
('A ticket costs five tokens. What is the cost?','Five tokens.'),
('Back to the doors. Is the gate now locked or open, and is the side door required?','The gate is open. This rule does not require the side door.')]),
('comprehension','contrast_of_causes',[
('Nora missed the train because her bus was late. Eli missed it because he lost his ticket. Why did Nora miss it?','Her bus was late.'),
('Who lost a ticket?','Eli.'),
('The cafe serves tea. What drink is named?','Tea.'),
('Back to the train. Did Nora lose her ticket?','The note does not say that. Eli lost his ticket.')]),
('clarification','ambiguous_referent',[
('I have a red bag and a blue bag. Put it on the chair. Ask which bag I mean before writing the instruction.','Which bag should go on the chair, red or blue?'),
('The blue one. Restate my instruction.','Put the blue bag on the chair.'),
('The library closes at six. When does it close?','At six.'),
('Back to my bags: which one did I choose?','The blue bag.')]),
('clarification','reminder_event_time',[
('Write a reminder for my chess lesson. I have not given its time.','What time is the chess lesson?'),
('At 16:35. Write the reminder now.','Your chess lesson is at 16:35.'),
('A separate cooking class is at 18:00. Repeat that time.','18:00'),
('Back to the lesson. Write its reminder again.','Your chess lesson is at 16:35.')]),
('clarification','missing_destination',[
('Write a note asking Sam to bring the books. The destination is missing. Ask for it.','Where should Sam bring the books?'),
('To the hall. Write the note.','Sam, please bring the books to the hall.'),
('The lamp is yellow. What color is it?','Yellow.'),
('Back to the books. Who should bring them, and where?','Sam should bring them to the hall.')]),
('clarification','explicit_no_question',[
('Draft a lunch reminder. The time is unknown. Use [time] as a placeholder; do not ask a question.','Reminder: lunch at [time].'),
('Replace [time] with 12:15.','Reminder: lunch at 12:15.'),
('The meeting room is B. Which room?','B.'),
('Back to lunch. What time did I give?','12:15')]),
('correction','single_field_update',[
('Delivery: Monday, room 3, for Ada. Summarize it.','Delivery for Ada on Monday in room 3.'),
('Change only the room to 7. Summarize again.','Delivery for Ada on Monday in room 7.'),
('The poster is orange. What color is it?','Orange.'),
('Back to delivery. Did the day change?','No. It is still Monday.')]),
('correction','two_successive_updates',[
('The spare battery is in the box. Where is it?','In the box.'),
('It moved to the shelf, then to the drawer. Where is it now?','In the drawer.'),
('The flag is red. Give its color.','Red.'),
('Back to the battery. Where was it immediately before the drawer?','On the shelf.')]),
('correction','retracted_update',[
('The rehearsal is at 14:20. Repeat the time.','14:20'),
('Change it to 15:00. Actually, cancel that change and keep the original time. What is it?','14:20'),
('The envelope is square. What shape?','Square.'),
('Back to rehearsal. Is 15:00 the current time?','No. It remains 14:20.')]),
('correction','entity_specific_update',[
('Tara has the pen. Dev has the ruler. Who has the ruler?','Dev.'),
('Dev gives the ruler to Noor. Who has it now?','Noor.'),
('The ferry leaves at noon. When does it leave?','At noon.'),
('Back to the objects. Who still has the pen?','Tara.')]),
('instructions','two_constraints',[
('A book is on the floor. A desk is free. Give one step to clear the floor without discarding the book.','Put the book on the desk.'),
('The desk is occupied. A shelf is free. Revise that step.','Put the book on the shelf.'),
('The window is round. What shape is it?','Round.'),
('Back to the book. Should the revised step use the desk?','No. Use the shelf.')]),
('instructions','format_switch',[
('The box is green. Answer with its color only.','Green.'),
('Now say the same fact in a complete sentence.','The box is green.'),
('The clock shows 10:05. Give the time only.','10:05'),
('Back to the box. Again, answer with its color only.','Green.')]),
('instructions','scope_of_edit',[
('Rewrite "Bring the small red bag" by changing only red to blue.','Bring the small blue bag.'),
('Now change only small to large.','Bring the large blue bag.'),
('A dog is sleeping. What is it doing?','Sleeping.'),
('Return to the edited instruction. Which object must be brought?','The large blue bag.')]),
('instructions','ordered_steps',[
('To pack safely: close the jar, then put it in the bag. Give the first step only.','Close the jar.'),
('It is closed now. Give the next step only.','Put the jar in the bag.'),
('The blanket is purple. Give its color.','Purple.'),
('Back to packing. Should the jar be open when it goes in the bag?','No. It should be closed.')]),
('explanation','mechanism_vs_effect',[
('A screen blocks some, but not all, light, so less reaches the desk. Why is the desk dimmer?','The screen blocks some light from reaching the desk.'),
('Does the note say the screen produces darkness?','No. It says the screen blocks some light.'),
('A class starts at nine. When does it start?','At nine.'),
('Back to the screen. Does all light get blocked?','The note says some light is blocked, not all.')]),
('explanation','limit_of_inference',[
('A lid slows water loss from a bowl. Explain why more water remains after an hour.','Less water is lost because the lid slows water loss.'),
('Can we tell exactly how much water remains?','No. No amounts were supplied.'),
('The boat is white. What color is it?','White.'),
('Return to the bowl. Does slowing loss mean no water is lost?','No. Slower loss does not mean zero loss.')]),
('explanation','comparison_from_rule',[
('In this game, a shield halves damage. An unshielded hit deals 8 points. What does a shielded hit deal?','4 points.'),
('Explain that answer briefly.','Half of 8 is 4.'),
('The badge has a star. What symbol?','A star.'),
('Back to the game. Is the shielded damage greater or smaller?','Smaller: 4 instead of 8.')]),
('explanation','necessary_condition',[
('This lamp works only when both switches are on. One is off. Why is the lamp off?','Both switches must be on, but one is off.'),
('Turn both on. Are the required switch conditions met, and does that guarantee it works?','The required switches are on, but that alone does not guarantee operation.'),
('The parcel is for Isha. Who is it for?','Isha.'),
('Back to the lamp. Was one switch alone enough?','No. Both switches are required.')])]

# Explicit structure variation; unchanged v1 is retained for review provenance.
for index in [1,5,7,22]:
    del CASES[index][2][1]  # three turns: initial context, interruption, return
for index in [18,21]:
    del CASES[index][2][2:]  # two-turn edit/explanation controls, no recall claim
for index in [0,12,15]:
    turns=CASES[index][2]
    turns[1],turns[2]=turns[2],turns[1]  # interruption before the update
CASES[2][2][-1]=('Are the mug and plate the same color?', 'No. The mug is white and the plate is blue.')

def main():
 assert not (ROOT/'freeze.json').exists(),'Frozen packet: write a new revision.'
 rows=[]; lines=['# Natural dialogue development packet','', '24 authored scenario frames, four per nominal family, with two to four turns. Not a final test or a population sample. References illustrate admissible answers; semantic grading is required. Twenty-two cases include interruption and an earlier-task follow-up; two are short controls. Shared structural motifs remain.','']
 for i,(family,frame,turns) in enumerate(CASES,1):
  row={'id':f'natural-{i:02}','family':family,'frame':frame,'split':'development','turns':[{'user':u,'reference':a} for u,a in turns]};rows.append(row)
  lines += [f'## {row["id"]}: {family} / {frame}','']
  for j,(u,a) in enumerate(turns,1):lines += [f'**Turn {j} — User:** {u}',f'**Reference:** {a}','']
 (ROOT/'natural-development.json').write_text(json.dumps(rows,indent=2)+'\n');(ROOT/'NATURAL_DEVELOPMENT.md').write_text('\n'.join(lines))
 print(f'Built {len(rows)} scenarios / {sum(len(r["turns"]) for r in rows)} turns.')
if __name__=='__main__':main()
