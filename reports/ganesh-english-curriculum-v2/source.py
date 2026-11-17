"""Codex-authored, scenario-disjoint pilot curriculum. No name-substitution expansion.
Each tuple: source group, family, explicit user/assistant pairs, semantic review.
Train/development assignments precede materialization. No sealed release content.
"""
TRAIN = [
('rainy_walk','ordinary',[
('I had planned a walk, but it has started raining. I am disappointed.','That is disappointing when you were looking forward to it. Would you like an indoor alternative or would you rather wait for a break in the rain?'),
('An indoor alternative, but nothing involving a screen.','You could read a few pages, sketch something nearby, or listen to music while stretching.'),
('Pick something that needs no supplies.','Try a few gentle stretches in a comfortable space.')], 'Acknowledges disappointment without diagnosis; screen-free and supply-free constraints survive refinement.'),
('borrowed_pan','ordinary',[
('My neighbour returned my baking pan with some biscuits. What could I say?','Thank you for returning the pan, and for the biscuits. That was thoughtful of you.'),
('Less formal, please.','Thanks for bringing the pan back—and for the biscuits!'),
('Keep the warmth but remove the exclamation mark.','Thanks for bringing the pan back—and for the biscuits.')], 'Natural thanks; follows tone and punctuation changes without inventing a relationship.'),
('blank_page','ordinary',[
('I want to write a story, but I keep staring at a blank page.','Start with a small moment instead of the whole plot. Who is there, and what unexpected thing happens?'),
('A caretaker finds a key under a chair. Give me an opening.','The caretaker lifted the chair and found a small key caught beneath one leg.'),
('Do not describe the key as small.','The caretaker lifted the chair and found a key caught beneath one leg.')], 'Creative premise remains fictional; removes only the rejected adjective.'),
('quiet_company','ordinary',[
('I have had a busy afternoon. Can we just chat for a bit?','Of course. Would you like to talk about your afternoon or something unrelated?'),
('Something unrelated. Ask me about music.','What kind of music do you usually enjoy?'),
('Mostly acoustic songs.','Is there an acoustic song you have been coming back to lately?')], 'Conversation advances naturally; no fabricated taste or unsolicited advice.'),
('unseen_draft','ordinary',[
('Does my draft sound welcoming?','Please paste the draft so I can read it.'),
('Here it is: Visitors should approach reception immediately.','The wording sounds quite formal. You could say: Please stop by reception when you arrive.'),
('Use welcome as the first word.','Welcome! Please stop by reception when you arrive.')], 'Requests missing input first; judges provided text only; obeys opening word.'),
('empty_message','ordinary',[
('Someone sent me a message saying only "fine". Are they upset?','That word alone does not tell us. They might be upset, busy, or simply being brief.'),
('Help me ask without assuming they are angry.','I am not sure how to read your message. Is everything okay?'),
('Make it gentler.','Just checking in—is everything okay?')], 'Maintains uncertainty; avoids reading emotions as established facts.'),
('catalogue_label','instructions',[
('Rewrite "This cupboard is for materials that are awaiting sorting" more simply.','This cupboard holds materials waiting to be sorted.'),
('Now make it a label of three words.','Materials awaiting sorting'),
('Use sentence case and a full stop.','Materials awaiting sorting.')], 'Three words checked; punctuation does not change word count.'),
('window_notice','instructions',[
('Write a notice asking people to leave this window shut because of dust outside.','Please keep this window shut to keep the dust outside.'),
('Remove the reason and start with Kindly.','Kindly keep this window shut.'),
('No full stop.','Kindly keep this window shut')], 'Editing constraints applied cumulatively; no added reason.'),
('picnic_list','instructions',[
('Suggest two things to pack for a picnic. Use two bullet points.','- Drinking water\n- A picnic blanket'),
('Replace the blanket with something edible.','- Drinking water\n- Sandwiches'),
('Now put those same items on one line, separated by a comma.','Drinking water, sandwiches')], 'Referents are actual earlier suggestions; exact two-item formatting retained.'),
('river_sentence','instructions',[
('Use "river" and "lantern" in one short sentence.','A lantern glowed beside the river.'),
('Make it a question.','Did a lantern glow beside the river?'),
('Answer that question using only "yes" or "no". This is an imaginary scene and the lantern did glow.','yes')], 'Fiction establishes answer; lowercase single word is intentional.'),
('door_summary','instructions',[
('Summarize this in one sentence: The shop door is blue. It opens onto a courtyard. A bell hangs above it.','A blue shop door with a bell above it opens onto a courtyard.'),
('Mention only the colour and the bell.','The shop door is blue and has a bell above it.'),
('What detail did you remove?','That the door opens onto a courtyard.')], 'Every claim grounded in supplied text; remembers requested deletion.'),
('invitation_scope','instructions',[
('Invite Sam to a board-game evening without suggesting a date.','Hi Sam, would you like to come over for a board-game evening?'),
('Add that beginners are welcome.','Hi Sam, would you like to come over for a board-game evening? Beginners are welcome.'),
('Shorten it, but keep that reassurance.','Sam, fancy a board-game evening? Beginners are welcome.')], 'No date invented; reassurance survives shortening.'),
('parcel_shelf','correction',[
('The parcel for Nila is on shelf B. Remember that for this conversation.','Nila’s parcel is on shelf B.'),
('Correction: it is on shelf E, not B.','Nila’s parcel is on shelf E.'),
('Write a short label for the parcel.','For Nila'),
('Which shelf should Nila check? Give only the letter.','E')], 'Newest shelf wins after an intervening label request; original B must not return.'),
('book_club_lead','correction',[
('Arun is leading the book discussion. Bea is taking notes.','Arun leads the discussion, and Bea takes notes.'),
('They have swapped roles.','Bea now leads the discussion, and Arun takes notes.'),
('Suggest a neutral title for the notes.','Book Discussion Notes'),
('Who is taking notes now?','Arun.')], 'Role swap applied to both people and retained after unrelated naming task.'),
('ticket_name','correction',[
('The ticket is booked under Dev Mehta.','The booking name is Dev Mehta.'),
('The surname was entered incorrectly. It should be Menon.','The correct booking name is Dev Menon.'),
('I have not asked anyone to change the actual booking yet.','Understood. I can use the corrected name here, but I have not changed the booking.'),
('Give me the name to put in my correction request.','Dev Menon')], 'Textual state update does not claim a real-world booking mutation.'),
('display_order','correction',[
('Put the exhibits in this order: pottery, textiles, photographs.','Pottery, textiles, photographs.'),
('Move photographs to the front and leave the others in their relative order.','Photographs, pottery, textiles.'),
('Give the display a short title.','Made and Remembered'),
('Which exhibit comes second now?','Pottery.')], 'Relative-order update is correct; title is creative rather than a factual assertion.'),
('collection_day','correction',[
('The collection was planned for Wednesday.','The planned collection day was Wednesday.'),
('It has moved to Saturday. Please use that day from now on.','I will use Saturday as the collection day in this conversation.'),
('Draft a note saying the day changed, without naming either day.','Please note that the collection day has changed.'),
('What is the current collection day? One word.','Saturday')], 'Current day retained despite a note intentionally omitting dates.'),
('plant_choice','correction',[
('For my fictional shop display, I chose a fern and a cactus.','The display includes a fern and a cactus.'),
('Replace the cactus with an orchid. Keep the fern.','The display now includes a fern and an orchid.'),
('Suggest a two-word display title.','Green Corner'),
('List the plants in the current display.','Fern and orchid.')], 'Replacement is not addition; cactus removed while fern retained.'),
('tea_preference','memory',[
('When we plan the refreshments here, remember that I prefer tea without sugar.','For this conversation, I will keep your preference for unsweetened tea in mind.'),
('What is a friendly way to greet guests?','Welcome! It is lovely to have you here.'),
('Make that greeting more casual.','Hi, great to see you!'),
('What did I say about sugar in my tea?','You prefer your tea without sugar.')], 'Delayed user preference retrieval; bounded to current conversation, no persistent-memory claim.'),
('repair_colour','memory',[
('The chair I am describing has a green seat and black legs.','The chair has a green seat and black legs.'),
('Suggest a heading for a repair note about it.','Chair Repair Note'),
('I want the heading in lowercase.','chair repair note'),
('Which part of the chair is black?','The legs.')], 'Retrieves the correct attribute after formatting distraction.'),
('museum_bag','memory',[
('In my story, Leela leaves a striped bag at the museum desk.','Leela leaves a striped bag at the museum desk.'),
('Give the scene a calm opening sentence.','The museum was quiet when Leela walked inside.'),
('Make the sentence shorter.','Leela entered the quiet museum.'),
('Where did she leave her bag in the story?','At the museum desk.')], 'Fictional elaboration does not change the established bag location.'),
('borrow_return','memory',[
('I borrowed a ladder from Omar. I lent a rake to Priya.','You borrowed Omar’s ladder and lent your rake to Priya.'),
('Write a neutral heading for a list tracking these items.','Borrowed and Lent Items'),
('Make the heading shorter.','Item Tracker'),
('Who has the rake?','Priya.')], 'Tracks direction of lending separately from borrowing across distractors.'),
('nickname_boundary','memory',[
('Call me Finch in this conversation. It is a nickname, not your name.','Sure, I will call you Finch here.'),
('Can you suggest a title for my sketchbook?','Small Things, Closely Seen'),
('Give me a shorter title.','Close Looking'),
('What nickname did I ask you to use for me?','Finch.')], 'User nickname distinguished from model identity; no real-world identity inference.'),
('task_constraint','memory',[
('Help me choose an indoor activity. I do not want anything noisy.','You could read, draw, or put together a puzzle.'),
('I have no puzzle.','Reading or drawing could still work.'),
('I have a notebook and a pen. Choose one activity.','Try drawing something you can see from where you are sitting.'),
('Why did you avoid recommending music?','You asked for an activity that is not noisy.')], 'Retains original constraint and available materials; rationale references user request.')]

DEV = [
('small_success','ordinary',[
('I finally organised a drawer I kept putting off.','That sounds satisfying. Was it easier to find things afterwards?'),
('Yes. Help me write a modest caption about it.','One drawer sorted, and a little less clutter.'),
('Remove the reference to clutter.','One drawer sorted.')], 'Modest caption and deletion, distinct situation from training.'),
('missing_photo','ordinary',[
('Is the frame in my photograph crooked?','I do not have the photograph here. Please share it or describe what you are seeing.'),
('The left corner is lower than the right.','From your description, the frame is tilted rather than level.'),
('Can you say which way it slopes without claiming you saw it?','Based on your description, it slopes downward to the left.')], 'No false visual access; conditional spatial inference is supported.'),
('gentle_disagreement','ordinary',[
('My friend prefers the first title, but I prefer the second. How can I say that kindly?','I can see why you like the first title. I am leaning towards the second one.'),
('Remove the opening acknowledgement.','I am leaning towards the second title.'),
('Make it a little less certain.','I think I might prefer the second title.')], 'Tone change without unsupported argument or claim.'),
('weather_wording','instructions',[
('Make "The weather was characterised by a lack of wind" easier to read.','There was no wind.'),
('Use exactly two words.','No wind'),
('Add a full stop without adding words.','No wind.')], 'Two-word count and punctuation explicitly checked.'),
('poster_emphasis','instructions',[
('Write a short poster line about a fictional evening of stories. Do not give a location.','Join us for an evening of stories.'),
('Start with Discover.','Discover an evening of stories.'),
('Replace stories with poetry.','Discover an evening of poetry.')], 'Ordered edits preserved; no invented location.'),
('spare_key','correction',[
('The spare key is in the blue tin.','The spare key is in the blue tin.'),
('I moved it to the desk drawer. The tin is empty now.','The spare key is now in the desk drawer, and the blue tin is empty.'),
('Suggest a label for the empty tin.','Empty'),
('Where should I look for the key?','In the desk drawer.')], 'Location changes without treating old container as still valid.'),
('stage_part','correction',[
('In our play, Mira is the narrator and Ishan is the traveller.','Mira is the narrator, and Ishan is the traveller.'),
('Ishan will narrate instead. Mira will play the traveller.','Ishan is now the narrator, and Mira is the traveller.'),
('Suggest a neutral heading for the cast list.','Cast'),
('Who plays the traveller now?','Mira.')], 'Both roles updated; no confusion from dialogue order.'),
('printing_finish','correction',[
('My order notes say matte paper and a red cover.','Your notes specify matte paper and a red cover.'),
('Change only the cover colour to cream.','The notes now specify matte paper and a cream cover.'),
('Please do not claim that an order was actually submitted.','I have only updated the description in this conversation; I have not submitted an order.'),
('What paper finish is still in the notes?','Matte.')], 'Changed and unchanged attributes separated; no fake external action.'),
('train_window','memory',[
('For the scene I am writing, the passenger is sitting by the window with a yellow scarf.','The passenger sits by the window and wears a yellow scarf.'),
('Suggest a title for this scene.','Between Stations'),
('Can you make the title three words?','Somewhere Between Stations'),
('What colour is the scarf in my scene?','Yellow.')], 'Retrieves original colour after title changes; creative title remains hypothetical.'),
('folder_contents','memory',[
('The amber folder holds recipes. The grey folder holds receipts.','Recipes are in the amber folder; receipts are in the grey folder.'),
('Suggest a heading for my organisation notes.','Folder Guide'),
('Turn the heading into a question about finding things.','Where Does Everything Go?'),
('Which folder contains receipts?','The grey folder.')], 'Similar words recipes/receipts deliberately distinguished.'),
('visitor_limit','memory',[
('For this imaginary gathering, invitations are for adults only.','The invitations are for adults only.'),
('Write a welcoming opening line for the invitation.','We would love you to join us for a relaxed gathering.'),
('Shorten that opening.','We would love you to join us.'),
('Would a children’s craft table fit the invitation restriction I gave?','No. You specified an adults-only gathering.')], 'Uses stated scenario rule without giving broad social judgement.'),
('speaker_details','memory',[
('In this fictional announcement, Noor presents the photographs and Vik reads the poems.','Noor presents the photographs, and Vik reads the poems.'),
('Give the event a simple name.','Pictures and Poems'),
('Make the name lowercase.','pictures and poems'),
('Who reads the poems?','Vik.')], 'Delayed actor-role retrieval after editing distractors.')]
