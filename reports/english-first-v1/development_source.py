"""Codex-authored development scenarios, never training or pristine release."""
SCENARIOS = [
('quiet_evening','preferences',[
('I have had a noisy day and want a quiet evening at home. I do not want to look at a screen. Suggest something simple.','You could sit somewhere comfortable and read a book, or listen to gentle music with the screen off.'),
('I would rather do something with my hands, and I have paper and pencils.','Try sketching something nearby, such as a cup or a plant. It does not need to be detailed.'),
('What preference from my first message should you still respect?','You wanted a quiet activity at home without looking at a screen.')]),
('neighbor_chat','social_response',[
('I am new in my building and feel awkward starting a conversation with a neighbor. How could I begin?','A simple greeting is enough: "Hi, I have just moved in. How long have you lived here?"'),
('That question feels a little personal. Could I start without asking anything?','You could say, "Hi, I have just moved in and wanted to introduce myself."'),
('Would that guarantee they want to talk?','No. It gives them an opening, but they may be busy or prefer to keep the exchange brief.')]),
('hobby_restart','preferences',[
('I used to enjoy drawing, but now I keep waiting until I can make something good. What is a small way to restart?','Try a quick sketch of an ordinary object without trying to make it polished. The aim is simply to draw again.'),
('Please avoid setting a timer or giving me a daily challenge.','Choose an object that catches your eye and draw it when you feel like it. You can stop after a few lines.'),
('Can you sum up that approach in one sentence?','Make a small, imperfect sketch when you feel like drawing, without a schedule or performance target.')]),
('speaker_feedback','social_response',[
('My friend showed me a short story. I liked the opening, but the ending confused me. How can I say that kindly?','You could say, "The opening drew me in, but I was not sure what happened at the end. Could you tell me what you intended?"'),
('Do not ask them to explain it; I just want to give feedback.','The opening drew me in, but I found the ending hard to follow.'),
('Did I say the whole story was confusing?','No. You said the ending confused you and that you liked the opening.')]),
('plant_care_note','grounding',[
('My housemate left this note: "The balcony door sticks. Lift the handle before pulling." Explain what I should do using only that note.','Lift the handle, then pull the balcony door.'),
('Does the note say the lock is broken?','No. It says the door sticks, but does not say the lock is broken.'),
('Would pushing the door follow the note?','No. The note says to pull it after lifting the handle.')]),
('visit_uncertainty','grounding',[
('My cousin said, "I might visit after the festival." Should I tell everyone the visit is confirmed?','No. "Might" means the visit is still uncertain.'),
('She has now written, "I have booked my journey and will arrive on Saturday." What changed?','She has now confirmed her travel and given Saturday as her arrival day.'),
('Do we know her arrival time?','No. She gave a day, but no arrival time.')]),
('reading_place','state',[
('I put my bookmark in the green novel, then moved it into the travel diary. Where should I look for it?','In the travel diary.'),
('The green novel is now on the desk. I have not moved the bookmark again. Does that change your answer?','No. The bookmark is still in the travel diary.'),
('Actually, I have just taken the bookmark out and put it in my bag. Where is it now?','In your bag.')]),
('shared_umbrella','state',[
('Nisha owns an umbrella. Omar borrowed it and is carrying it today. Who owns it, and who has it?','Nisha owns the umbrella; Omar currently has it.'),
('Omar returned it to Nisha. Did ownership change?','No. Nisha still owns it, and now she has it back.'),
('Nisha then gave it to Dev as a gift. Who owns it now?','Dev.')]),
('recipe_missing','clarification',[
('Can you tell me whether this recipe uses an oven?','Please share the recipe or its instructions so I can check.'),
('The instructions say to mix the ingredients, put them in a pan, and cook on the stove until thick.','Those instructions use the stove and do not mention an oven.'),
('What temperature should I set the oven to?','The instructions do not call for an oven or give an oven temperature.')]),
('ambiguous_choice','clarification',[
('Which one should I keep?','What are you choosing between, and what matters most to you?'),
('Two notebooks: one fits in my pocket; the other has more room for sketches. I want to carry it on walks.','The pocket-sized notebook sounds better suited to carrying on walks, if its pages are large enough for what you want to note.'),
('Now my priority is large drawings at home. Would your advice change?','Yes. The notebook with more room for sketches would better fit that priority.')]),
('topic_return','conversation_memory',[
('Help me name a little reading corner. I want a calm name, not something grand.','How about "Quiet Corner"?'),
('A different question: what does "borrow" mean?','To borrow something is to use it temporarily with permission and then return it.'),
('Back to the reading corner: what name did you suggest?','Quiet Corner.')]),
('closing_exchange','conversation_memory',[
('I finally finished sorting the cupboard I had been avoiding.','That sounds like a relief to have it done.'),
('It is. I am not looking for another task, just sharing.','Understood. You can enjoy having that one finished.'),
('Thanks, that is all for now.','You are welcome. Take care.')]),
]
