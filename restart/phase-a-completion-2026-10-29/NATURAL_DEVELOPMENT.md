# Natural dialogue development packet

24 authored scenario frames, four per nominal family, with two to four turns. Not a final test or a population sample. References illustrate admissible answers; semantic grading is required. Twenty-two cases include interruption and an earlier-task follow-up; two are short controls. Shared structural motifs remain.

## natural-01: grounding / corrected_location

**Turn 1 — User:** The red key is in the drawer. The blue key is in the bowl. Where is the red key?
**Reference:** In the drawer.

**Turn 2 — User:** New topic: the shop closes at 19:10. Give the closing time.
**Reference:** 19:10

**Turn 3 — User:** Move only the red key to the hook. Where is it now?
**Reference:** On the hook.

**Turn 4 — User:** Back to the keys. Where is the blue key?
**Reference:** In the bowl.

## natural-02: grounding / ownership_vs_borrower

**Turn 1 — User:** Lena owns the camera. Omar borrowed it. Who owns it?
**Reference:** Lena owns the camera.

**Turn 2 — User:** Separate note: the room is upstairs. Where is the room?
**Reference:** Upstairs.

**Turn 3 — User:** Back to the camera: did borrowing make Omar its owner?
**Reference:** No. Lena still owns it.

## natural-03: grounding / negated_attribute

**Turn 1 — User:** The mug is not blue; it is white. What color is it?
**Reference:** White.

**Turn 2 — User:** The plate is blue. Give only the plate color.
**Reference:** Blue.

**Turn 3 — User:** A bell rings at noon. When does it ring?
**Reference:** At noon.

**Turn 4 — User:** Are the mug and plate the same color?
**Reference:** No. The mug is white and the plate is blue.

## natural-04: grounding / missing_then_supplied

**Turn 1 — User:** The parcel has no sender listed. Who sent it?
**Reference:** The sender is not supplied.

**Turn 2 — User:** A new label says the sender is Arun. Who sent it?
**Reference:** Arun.

**Turn 3 — User:** The door code is 482. Repeat the code.
**Reference:** 482

**Turn 4 — User:** Return to the parcel. Name the sender and say whether a delivery date was supplied.
**Reference:** Arun is the sender. No delivery date was supplied.

## natural-05: comprehension / cause_and_location

**Turn 1 — User:** Rain entered the shed, so Jo moved the seeds indoors. Why move them?
**Reference:** To protect the seeds from the rain.

**Turn 2 — User:** Where are the seeds now?
**Reference:** Indoors.

**Turn 3 — User:** The bakery opens at eight. When does it open?
**Reference:** At eight.

**Turn 4 — User:** Back to Jo: where are the seeds, and does the note say they were ruined?
**Reference:** Indoors. The note does not say they were ruined.

## natural-06: comprehension / temporal_sequence

**Turn 1 — User:** Mia washed a cup, dried it, then packed it. What happened immediately after washing?
**Reference:** Mia dried the cup.

**Turn 2 — User:** The bus is green. Give its color.
**Reference:** Green.

**Turn 3 — User:** Back to the cup. Was it packed before it was dried?
**Reference:** No. It was dried before being packed.

## natural-07: comprehension / conditional_rule

**Turn 1 — User:** If the gate is locked, use the side door. The gate is locked. Which way should I go?
**Reference:** Use the side door.

**Turn 2 — User:** Now the gate is open. Does that rule still require the side door?
**Reference:** No. The rule applies when the gate is locked.

**Turn 3 — User:** A ticket costs five tokens. What is the cost?
**Reference:** Five tokens.

**Turn 4 — User:** Back to the doors. Is the gate now locked or open, and is the side door required?
**Reference:** The gate is open. This rule does not require the side door.

## natural-08: comprehension / contrast_of_causes

**Turn 1 — User:** Nora missed the train because her bus was late. Eli missed it because he lost his ticket. Why did Nora miss it?
**Reference:** Her bus was late.

**Turn 2 — User:** The cafe serves tea. What drink is named?
**Reference:** Tea.

**Turn 3 — User:** Back to the train. Did Nora lose her ticket?
**Reference:** The note does not say that. Eli lost his ticket.

## natural-09: clarification / ambiguous_referent

**Turn 1 — User:** I have a red bag and a blue bag. Put it on the chair. Ask which bag I mean before writing the instruction.
**Reference:** Which bag should go on the chair, red or blue?

**Turn 2 — User:** The blue one. Restate my instruction.
**Reference:** Put the blue bag on the chair.

**Turn 3 — User:** The library closes at six. When does it close?
**Reference:** At six.

**Turn 4 — User:** Back to my bags: which one did I choose?
**Reference:** The blue bag.

## natural-10: clarification / reminder_event_time

**Turn 1 — User:** Write a reminder for my chess lesson. I have not given its time.
**Reference:** What time is the chess lesson?

**Turn 2 — User:** At 16:35. Write the reminder now.
**Reference:** Your chess lesson is at 16:35.

**Turn 3 — User:** A separate cooking class is at 18:00. Repeat that time.
**Reference:** 18:00

**Turn 4 — User:** Back to the lesson. Write its reminder again.
**Reference:** Your chess lesson is at 16:35.

## natural-11: clarification / missing_destination

**Turn 1 — User:** Write a note asking Sam to bring the books. The destination is missing. Ask for it.
**Reference:** Where should Sam bring the books?

**Turn 2 — User:** To the hall. Write the note.
**Reference:** Sam, please bring the books to the hall.

**Turn 3 — User:** The lamp is yellow. What color is it?
**Reference:** Yellow.

**Turn 4 — User:** Back to the books. Who should bring them, and where?
**Reference:** Sam should bring them to the hall.

## natural-12: clarification / explicit_no_question

**Turn 1 — User:** Draft a lunch reminder. The time is unknown. Use [time] as a placeholder; do not ask a question.
**Reference:** Reminder: lunch at [time].

**Turn 2 — User:** Replace [time] with 12:15.
**Reference:** Reminder: lunch at 12:15.

**Turn 3 — User:** The meeting room is B. Which room?
**Reference:** B.

**Turn 4 — User:** Back to lunch. What time did I give?
**Reference:** 12:15

## natural-13: correction / single_field_update

**Turn 1 — User:** Delivery: Monday, room 3, for Ada. Summarize it.
**Reference:** Delivery for Ada on Monday in room 3.

**Turn 2 — User:** The poster is orange. What color is it?
**Reference:** Orange.

**Turn 3 — User:** Change only the room to 7. Summarize again.
**Reference:** Delivery for Ada on Monday in room 7.

**Turn 4 — User:** Back to delivery. Did the day change?
**Reference:** No. It is still Monday.

## natural-14: correction / two_successive_updates

**Turn 1 — User:** The spare battery is in the box. Where is it?
**Reference:** In the box.

**Turn 2 — User:** It moved to the shelf, then to the drawer. Where is it now?
**Reference:** In the drawer.

**Turn 3 — User:** The flag is red. Give its color.
**Reference:** Red.

**Turn 4 — User:** Back to the battery. Where was it immediately before the drawer?
**Reference:** On the shelf.

## natural-15: correction / retracted_update

**Turn 1 — User:** The rehearsal is at 14:20. Repeat the time.
**Reference:** 14:20

**Turn 2 — User:** Change it to 15:00. Actually, cancel that change and keep the original time. What is it?
**Reference:** 14:20

**Turn 3 — User:** The envelope is square. What shape?
**Reference:** Square.

**Turn 4 — User:** Back to rehearsal. Is 15:00 the current time?
**Reference:** No. It remains 14:20.

## natural-16: correction / entity_specific_update

**Turn 1 — User:** Tara has the pen. Dev has the ruler. Who has the ruler?
**Reference:** Dev.

**Turn 2 — User:** The ferry leaves at noon. When does it leave?
**Reference:** At noon.

**Turn 3 — User:** Dev gives the ruler to Noor. Who has it now?
**Reference:** Noor.

**Turn 4 — User:** Back to the objects. Who still has the pen?
**Reference:** Tara.

## natural-17: instructions / two_constraints

**Turn 1 — User:** A book is on the floor. A desk is free. Give one step to clear the floor without discarding the book.
**Reference:** Put the book on the desk.

**Turn 2 — User:** The desk is occupied. A shelf is free. Revise that step.
**Reference:** Put the book on the shelf.

**Turn 3 — User:** The window is round. What shape is it?
**Reference:** Round.

**Turn 4 — User:** Back to the book. Should the revised step use the desk?
**Reference:** No. Use the shelf.

## natural-18: instructions / format_switch

**Turn 1 — User:** The box is green. Answer with its color only.
**Reference:** Green.

**Turn 2 — User:** Now say the same fact in a complete sentence.
**Reference:** The box is green.

**Turn 3 — User:** The clock shows 10:05. Give the time only.
**Reference:** 10:05

**Turn 4 — User:** Back to the box. Again, answer with its color only.
**Reference:** Green.

## natural-19: instructions / scope_of_edit

**Turn 1 — User:** Rewrite "Bring the small red bag" by changing only red to blue.
**Reference:** Bring the small blue bag.

**Turn 2 — User:** Now change only small to large.
**Reference:** Bring the large blue bag.

## natural-20: instructions / ordered_steps

**Turn 1 — User:** To pack safely: close the jar, then put it in the bag. Give the first step only.
**Reference:** Close the jar.

**Turn 2 — User:** It is closed now. Give the next step only.
**Reference:** Put the jar in the bag.

**Turn 3 — User:** The blanket is purple. Give its color.
**Reference:** Purple.

**Turn 4 — User:** Back to packing. Should the jar be open when it goes in the bag?
**Reference:** No. It should be closed.

## natural-21: explanation / mechanism_vs_effect

**Turn 1 — User:** A screen blocks some, but not all, light, so less reaches the desk. Why is the desk dimmer?
**Reference:** The screen blocks some light from reaching the desk.

**Turn 2 — User:** Does the note say the screen produces darkness?
**Reference:** No. It says the screen blocks some light.

**Turn 3 — User:** A class starts at nine. When does it start?
**Reference:** At nine.

**Turn 4 — User:** Back to the screen. Does all light get blocked?
**Reference:** The note says some light is blocked, not all.

## natural-22: explanation / limit_of_inference

**Turn 1 — User:** A lid slows water loss from a bowl. Explain why more water remains after an hour.
**Reference:** Less water is lost because the lid slows water loss.

**Turn 2 — User:** Can we tell exactly how much water remains?
**Reference:** No. No amounts were supplied.

## natural-23: explanation / comparison_from_rule

**Turn 1 — User:** In this game, a shield halves damage. An unshielded hit deals 8 points. What does a shielded hit deal?
**Reference:** 4 points.

**Turn 2 — User:** The badge has a star. What symbol?
**Reference:** A star.

**Turn 3 — User:** Back to the game. Is the shielded damage greater or smaller?
**Reference:** Smaller: 4 instead of 8.

## natural-24: explanation / necessary_condition

**Turn 1 — User:** This lamp works only when both switches are on. One is off. Why is the lamp off?
**Reference:** Both switches must be on, but one is off.

**Turn 2 — User:** Turn both on. Are the required switch conditions met, and does that guarantee it works?
**Reference:** The required switches are on, but that alone does not guarantee operation.

**Turn 3 — User:** The parcel is for Isha. Who is it for?
**Reference:** Isha.

**Turn 4 — User:** Back to the lamp. Was one switch alone enough?
**Reference:** No. Both switches are required.
