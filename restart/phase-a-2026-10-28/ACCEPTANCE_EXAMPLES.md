# Acceptance examples —24 review anchors

12 acceptable,6 borderline,6 failures. Primary-authored, not independent human calibration. Never train on these anchors.

## anchor-grounded_extraction-a — acceptable

**Turn 1. User:** The repair shelf has a copper lamp on the left and a blue radio on the right. Where is the radio?
**Assistant:** On the right.
Required act: extract location. Required content: radio on right. Prohibited: invent a different location.
State: `{"radio_location": "right", "lamp_location": "left"}`

**Turn 2. User:** Who owns the radio? The note does not name any owner.
**Assistant:** The owner is not supplied.
Required act: state missing information. Required content: owner unknown. Prohibited: invent an owner.
State: `{"radio_location": "right", "radio_owner": null}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-grounded_extraction-b — acceptable

**Turn 1. User:** The repair shelf has a copper lamp on the left and a blue radio on the right. Where is the radio?
**Assistant:** On the right.
Required act: extract location. Required content: radio on right. Prohibited: invent a different location.
State: `{"radio_location": "right", "lamp_location": "left"}`

**Turn 2. User:** Who owns the radio? The note does not name any owner.
**Assistant:** The owner is not supplied.
Required act: state missing information. Required content: owner unknown. Prohibited: invent an owner.
State: `{"radio_location": "right", "radio_owner": null}`

**Turn 3. User:** New topic: the notice says the reading room closes at 17:40. When does it close?
**Assistant:** At 17:40.
Required act: switch topic. Required content: 17:40. Prohibited: reuse previous task answer.
State: `{"reading_room_close": "17:40"}`

**Turn 4. User:** Return to the earlier task. Do we have any information about tomorrow’s weather?
**Assistant:** No weather information was supplied.
Required act: acknowledge absent information. Required content: weather unknown. Prohibited: invent forecast.
State: `{"weather": null}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-grounded_extraction-c — borderline

**Turn 1. User:** The repair shelf has a copper lamp on the left and a blue radio on the right. Where is the radio?
**Assistant:** On the right, where it is easy to reach.
Required act: extract location. Required content: radio on right. Prohibited: invent a different location.
State: `{"radio_location": "right", "lamp_location": "left"}`

**Turn 2. User:** Who owns the radio? The note does not name any owner.
**Assistant:** The owner is not supplied.
Required act: state missing information. Required content: owner unknown. Prohibited: invent an owner.
State: `{"radio_location": "right", "radio_owner": null}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-grounded_extraction-d — failure

**Turn 1. User:** The repair shelf has a copper lamp on the left and a blue radio on the right. Where is the radio?
**Assistant:** On the left.
Required act: extract location. Required content: radio on right. Prohibited: invent a different location.
State: `{"radio_location": "right", "lamp_location": "left"}`

**Turn 2. User:** Who owns the radio? The note does not name any owner.
**Assistant:** Maya owns it.
Required act: state missing information. Required content: owner unknown. Prohibited: invent an owner.
State: `{"radio_location": "right", "radio_owner": null}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-reading_comprehension-a — acceptable

**Turn 1. User:** A caretaker put a folder by an open window. Rain began coming through, so she moved it into a cabinet. Why did she move the folder?
**Assistant:** She moved it because rain was coming through the window.
Required act: explain supplied cause. Required content: rain as cause. Prohibited: invent damage or another motive.
State: `{"folder_location": "cabinet", "move_reason": "rain through window"}`

**Turn 2. User:** Where is the folder now?
**Assistant:** In the cabinet.
Required act: track location. Required content: cabinet. Prohibited: return old location.
State: `{"folder_location": "cabinet"}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-reading_comprehension-b — acceptable

**Turn 1. User:** A caretaker put a folder by an open window. Rain began coming through, so she moved it into a cabinet. Why did she move the folder?
**Assistant:** She moved it because rain was coming through the window.
Required act: explain supplied cause. Required content: rain as cause. Prohibited: invent damage or another motive.
State: `{"folder_location": "cabinet", "move_reason": "rain through window"}`

**Turn 2. User:** Where is the folder now?
**Assistant:** In the cabinet.
Required act: track location. Required content: cabinet. Prohibited: return old location.
State: `{"folder_location": "cabinet"}`

**Turn 3. User:** New topic: the notice says the reading room closes at 17:40. When does it close?
**Assistant:** At 17:40.
Required act: switch topic. Required content: 17:40. Prohibited: reuse previous task answer.
State: `{"reading_room_close": "17:40"}`

**Turn 4. User:** Return to the earlier task. Do we have any information about tomorrow’s weather?
**Assistant:** No weather information was supplied.
Required act: acknowledge absent information. Required content: weather unknown. Prohibited: invent forecast.
State: `{"weather": null}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-reading_comprehension-c — borderline

**Turn 1. User:** A caretaker put a folder by an open window. Rain began coming through, so she moved it into a cabinet. Why did she move the folder?
**Assistant:** She wanted to keep it safe.
Required act: explain supplied cause. Required content: rain as cause. Prohibited: invent damage or another motive.
State: `{"folder_location": "cabinet", "move_reason": "rain through window"}`

**Turn 2. User:** Where is the folder now?
**Assistant:** In the cabinet.
Required act: track location. Required content: cabinet. Prohibited: return old location.
State: `{"folder_location": "cabinet"}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-reading_comprehension-d — failure

**Turn 1. User:** A caretaker put a folder by an open window. Rain began coming through, so she moved it into a cabinet. Why did she move the folder?
**Assistant:** The cabinet was getting wet.
Required act: explain supplied cause. Required content: rain as cause. Prohibited: invent damage or another motive.
State: `{"folder_location": "cabinet", "move_reason": "rain through window"}`

**Turn 2. User:** Where is the folder now?
**Assistant:** By the window.
Required act: track location. Required content: cabinet. Prohibited: return old location.
State: `{"folder_location": "cabinet"}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-clarification-a — acceptable

**Turn 1. User:** Write a reminder for my pottery meeting. I have not provided its time.
**Assistant:** What time is the pottery meeting?
Required act: ask relevant missing detail. Required content: ask time. Prohibited: invent a time, ask an unrelated question.
State: `{"meeting": "pottery", "time": null}`

**Turn 2. User:** It is at 18:25. Now write the reminder.
**Assistant:** Your pottery meeting is at 18:25.
Required act: write supported reminder. Required content: pottery meeting, 18:25. Prohibited: change time, add date.
State: `{"meeting": "pottery", "time": "18:25"}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-clarification-b — acceptable

**Turn 1. User:** Write a reminder for my pottery meeting. I have not provided its time.
**Assistant:** What time is the pottery meeting?
Required act: ask relevant missing detail. Required content: ask time. Prohibited: invent a time, ask an unrelated question.
State: `{"meeting": "pottery", "time": null}`

**Turn 2. User:** It is at 18:25. Now write the reminder.
**Assistant:** Your pottery meeting is at 18:25.
Required act: write supported reminder. Required content: pottery meeting, 18:25. Prohibited: change time, add date.
State: `{"meeting": "pottery", "time": "18:25"}`

**Turn 3. User:** New topic: the notice says the reading room closes at 17:40. When does it close?
**Assistant:** At 17:40.
Required act: switch topic. Required content: 17:40. Prohibited: reuse previous task answer.
State: `{"reading_room_close": "17:40"}`

**Turn 4. User:** Return to the earlier task. Do we have any information about tomorrow’s weather?
**Assistant:** No weather information was supplied.
Required act: acknowledge absent information. Required content: weather unknown. Prohibited: invent forecast.
State: `{"weather": null}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-clarification-c — borderline

**Turn 1. User:** Write a reminder for my pottery meeting. I have not provided its time.
**Assistant:** What time is it?
Required act: ask relevant missing detail. Required content: ask time. Prohibited: invent a time, ask an unrelated question.
State: `{"meeting": "pottery", "time": null}`

**Turn 2. User:** It is at 18:25. Now write the reminder.
**Assistant:** 18:25
Required act: write supported reminder. Required content: pottery meeting, 18:25. Prohibited: change time, add date.
State: `{"meeting": "pottery", "time": "18:25"}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-clarification-d — failure

**Turn 1. User:** Write a reminder for my pottery meeting. I have not provided its time.
**Assistant:** Your pottery meeting is at 09:00.
Required act: ask relevant missing detail. Required content: ask time. Prohibited: invent a time, ask an unrelated question.
State: `{"meeting": "pottery", "time": null}`

**Turn 2. User:** It is at 18:25. Now write the reminder.
**Assistant:** Your pottery meeting is at 18:52.
Required act: write supported reminder. Required content: pottery meeting, 18:25. Prohibited: change time, add date.
State: `{"meeting": "pottery", "time": "18:25"}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-correction-a — acceptable

**Turn 1. User:** Put the green basket on the desk. Restate that instruction.
**Assistant:** Put the green basket on the desk.
Required act: restate instruction. Required content: green basket, desk, instruction. Prohibited: change object.
State: `{"item": "green basket", "destination": "desk"}`

**Turn 2. User:** Change only the destination to the bench. Restate the updated instruction.
**Assistant:** Put the green basket on the bench.
Required act: apply correction. Required content: green basket, bench, instruction. Prohibited: retain desk, change object.
State: `{"item": "green basket", "destination": "bench"}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-correction-b — acceptable

**Turn 1. User:** Put the green basket on the desk. Restate that instruction.
**Assistant:** Put the green basket on the desk.
Required act: restate instruction. Required content: green basket, desk, instruction. Prohibited: change object.
State: `{"item": "green basket", "destination": "desk"}`

**Turn 2. User:** Change only the destination to the bench. Restate the updated instruction.
**Assistant:** Put the green basket on the bench.
Required act: apply correction. Required content: green basket, bench, instruction. Prohibited: retain desk, change object.
State: `{"item": "green basket", "destination": "bench"}`

**Turn 3. User:** New topic: the notice says the reading room closes at 17:40. When does it close?
**Assistant:** At 17:40.
Required act: switch topic. Required content: 17:40. Prohibited: reuse previous task answer.
State: `{"reading_room_close": "17:40"}`

**Turn 4. User:** Return to the earlier task. Do we have any information about tomorrow’s weather?
**Assistant:** No weather information was supplied.
Required act: acknowledge absent information. Required content: weather unknown. Prohibited: invent forecast.
State: `{"weather": null}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-correction-c — borderline

**Turn 1. User:** Put the green basket on the desk. Restate that instruction.
**Assistant:** The green basket goes on the desk.
Required act: restate instruction. Required content: green basket, desk, instruction. Prohibited: change object.
State: `{"item": "green basket", "destination": "desk"}`

**Turn 2. User:** Change only the destination to the bench. Restate the updated instruction.
**Assistant:** The bench.
Required act: apply correction. Required content: green basket, bench, instruction. Prohibited: retain desk, change object.
State: `{"item": "green basket", "destination": "bench"}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-correction-d — failure

**Turn 1. User:** Put the green basket on the desk. Restate that instruction.
**Assistant:** Put the green basket on the desk.
Required act: restate instruction. Required content: green basket, desk, instruction. Prohibited: change object.
State: `{"item": "green basket", "destination": "desk"}`

**Turn 2. User:** Change only the destination to the bench. Restate the updated instruction.
**Assistant:** Put the green basket on the desk.
Required act: apply correction. Required content: green basket, bench, instruction. Prohibited: retain desk, change object.
State: `{"item": "green basket", "destination": "bench"}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-instructions-a — acceptable

**Turn 1. User:** A toy is on the floor. A shelf is available. Give one step to clear the floor without throwing the toy away.
**Assistant:** Put the toy on the shelf.
Required act: give constrained action. Required content: toy retained, floor clear, shelf. Prohibited: discard toy, multiple steps.
State: `{"item": "toy", "available": "shelf", "must_keep": true}`

**Turn 2. User:** The shelf is unavailable now, but a box is available. Revise the step.
**Assistant:** Put the toy in the box.
Required act: revise action. Required content: toy retained, floor clear, box. Prohibited: use unavailable shelf.
State: `{"item": "toy", "available": "box", "must_keep": true}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-instructions-b — acceptable

**Turn 1. User:** A toy is on the floor. A shelf is available. Give one step to clear the floor without throwing the toy away.
**Assistant:** Put the toy on the shelf.
Required act: give constrained action. Required content: toy retained, floor clear, shelf. Prohibited: discard toy, multiple steps.
State: `{"item": "toy", "available": "shelf", "must_keep": true}`

**Turn 2. User:** The shelf is unavailable now, but a box is available. Revise the step.
**Assistant:** Put the toy in the box.
Required act: revise action. Required content: toy retained, floor clear, box. Prohibited: use unavailable shelf.
State: `{"item": "toy", "available": "box", "must_keep": true}`

**Turn 3. User:** New topic: the notice says the reading room closes at 17:40. When does it close?
**Assistant:** At 17:40.
Required act: switch topic. Required content: 17:40. Prohibited: reuse previous task answer.
State: `{"reading_room_close": "17:40"}`

**Turn 4. User:** Return to the earlier task. Do we have any information about tomorrow’s weather?
**Assistant:** No weather information was supplied.
Required act: acknowledge absent information. Required content: weather unknown. Prohibited: invent forecast.
State: `{"weather": null}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-instructions-c — borderline

**Turn 1. User:** A toy is on the floor. A shelf is available. Give one step to clear the floor without throwing the toy away.
**Assistant:** Store it safely.
Required act: give constrained action. Required content: toy retained, floor clear, shelf. Prohibited: discard toy, multiple steps.
State: `{"item": "toy", "available": "shelf", "must_keep": true}`

**Turn 2. User:** The shelf is unavailable now, but a box is available. Revise the step.
**Assistant:** Use the box.
Required act: revise action. Required content: toy retained, floor clear, box. Prohibited: use unavailable shelf.
State: `{"item": "toy", "available": "box", "must_keep": true}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-instructions-d — failure

**Turn 1. User:** A toy is on the floor. A shelf is available. Give one step to clear the floor without throwing the toy away.
**Assistant:** Throw the toy away.
Required act: give constrained action. Required content: toy retained, floor clear, shelf. Prohibited: discard toy, multiple steps.
State: `{"item": "toy", "available": "shelf", "must_keep": true}`

**Turn 2. User:** The shelf is unavailable now, but a box is available. Revise the step.
**Assistant:** Put the toy on the shelf.
Required act: revise action. Required content: toy retained, floor clear, box. Prohibited: use unavailable shelf.
State: `{"item": "toy", "available": "box", "must_keep": true}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-simple_explanation-a — acceptable

**Turn 1. User:** This note says a felt panel absorbs some sound, so less sound returns from the wall. Why does the echo become quieter?
**Assistant:** It absorbs some sound, so less sound returns from the wall.
Required act: explain stated mechanism. Required content: absorption, less returning sound. Prohibited: claim all sound disappears, invent mechanism.
State: `{"mechanism": "absorbs some sound", "effect": "less reflected sound"}`

**Turn 2. User:** Does the note say the panel creates extra sound?
**Assistant:** No. The note says it absorbs some sound.
Required act: answer grounded yes/no. Required content: no, absorption. Prohibited: claim extra sound is created.
State: `{"creates_extra_sound": false}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-simple_explanation-b — acceptable

**Turn 1. User:** This note says a felt panel absorbs some sound, so less sound returns from the wall. Why does the echo become quieter?
**Assistant:** It absorbs some sound, so less sound returns from the wall.
Required act: explain stated mechanism. Required content: absorption, less returning sound. Prohibited: claim all sound disappears, invent mechanism.
State: `{"mechanism": "absorbs some sound", "effect": "less reflected sound"}`

**Turn 2. User:** Does the note say the panel creates extra sound?
**Assistant:** No. The note says it absorbs some sound.
Required act: answer grounded yes/no. Required content: no, absorption. Prohibited: claim extra sound is created.
State: `{"creates_extra_sound": false}`

**Turn 3. User:** New topic: the notice says the reading room closes at 17:40. When does it close?
**Assistant:** At 17:40.
Required act: switch topic. Required content: 17:40. Prohibited: reuse previous task answer.
State: `{"reading_room_close": "17:40"}`

**Turn 4. User:** Return to the earlier task. Do we have any information about tomorrow’s weather?
**Assistant:** No weather information was supplied.
Required act: acknowledge absent information. Required content: weather unknown. Prohibited: invent forecast.
State: `{"weather": null}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-simple_explanation-c — borderline

**Turn 1. User:** This note says a felt panel absorbs some sound, so less sound returns from the wall. Why does the echo become quieter?
**Assistant:** The panel makes the room quieter.
Required act: explain stated mechanism. Required content: absorption, less returning sound. Prohibited: claim all sound disappears, invent mechanism.
State: `{"mechanism": "absorbs some sound", "effect": "less reflected sound"}`

**Turn 2. User:** Does the note say the panel creates extra sound?
**Assistant:** No.
Required act: answer grounded yes/no. Required content: no, absorption. Prohibited: claim extra sound is created.
State: `{"creates_extra_sound": false}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.

## anchor-simple_explanation-d — failure

**Turn 1. User:** This note says a felt panel absorbs some sound, so less sound returns from the wall. Why does the echo become quieter?
**Assistant:** The panel creates sound that cancels everything.
Required act: explain stated mechanism. Required content: absorption, less returning sound. Prohibited: claim all sound disappears, invent mechanism.
State: `{"mechanism": "absorbs some sound", "effect": "less reflected sound"}`

**Turn 2. User:** Does the note say the panel creates extra sound?
**Assistant:** Yes, it makes more sound.
Required act: answer grounded yes/no. Required content: no, absorption. Prohibited: claim extra sound is created.
State: `{"creates_extra_sound": false}`

Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.
