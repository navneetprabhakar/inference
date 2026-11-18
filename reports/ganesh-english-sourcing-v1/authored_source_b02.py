"""Original English scenarios, assigned in authoring-plan-b02.json before writing."""
ROWS=[]
def add(family,group,*turns):
 ROWS.append(dict(family=family,group=group,turns=turns))
add('ordinary','weekend_without_schedule',
('I finally have a free Saturday, but now I feel I should make it productive.','You could leave part of it unplanned. A free day does not need to become another list of jobs.'),
('I do want to do one useful thing. The rest can wait.','Pick a small job with a clear end, then leave the rest of the day open.'),
('Sorting one drawer sounds manageable.','One drawer gives you a stopping point. You do not have to turn it into cleaning the whole room.'),
('Remind me what I decided, without adding suggestions.','Sort one drawer and leave the rest of Saturday open.'))
add('ordinary','new_neighbour_hello',
('A new neighbour moved in. I want to say hello without making it awkward.','A brief introduction when you cross paths is enough: “Hi, I live next door. Welcome to the building.”'),
('I would rather leave a note. I am called Mira.','Hi, I am Mira from next door. Welcome to the building!'),
('Should I promise to help with anything?','Only if you mean it. A welcome can be friendly without an open-ended promise.'),
('Then keep it just as a welcome.','Hi, I am Mira from next door. Welcome to the building!'))
add('ordinary','unfinished_hobby',
('My half-finished model boat has been on the shelf for months.','Are you hoping to finish it, or deciding whether you still want to?'),
('Deciding. I liked painting it but hated assembling the tiny parts.','You might prefer a painting project next time. Enjoying one part of the hobby does not mean you have to enjoy all of it.'),
('I feel bad giving the boat away unfinished.','You can describe it honestly as an unfinished kit. Someone who enjoys assembly may be happy to take it.'),
('Give me a short listing title.','Unfinished model boat kit'))
add('ordinary','rainy_window_break',
('It is raining and I have ten minutes before my next call. I do not want to look at another screen.','You could sit by a window and watch the rain for a few minutes.'),
('That is what I am doing. It is quieter than I expected.','A quiet pause sounds welcome between calls.'),
('Please do not turn this into advice about productivity.','We can leave it as a quiet moment by the window.'),
('Exactly.','No need to make anything more of it.'))
add('clarification','book_recommendation_missing_taste',
('What kind of book should I try next?','What have you enjoyed recently, and are you looking for something similar or different?'),
('I liked a gentle story about neighbours. Something similar, but shorter.','A short story collection about everyday relationships could suit you. You could also look for a novella with a small cast and a quiet setting.'),
('What is a novella?','A novella is a work of fiction longer than a short story and shorter than a typical novel.'),
('Which of those options is one continuous story?','A novella usually tells one continuous story. A collection contains separate stories.'))
add('clarification','meeting_time_missing_zone',
('Tell my colleague our online meeting is at nine. We are in different countries.','Which day and time zone should the message specify?'),
('Friday, nine in the morning in my time zone.','What is your time zone? “My time” could leave your colleague unsure.'),
('India Standard Time. Do not convert it.','Our online meeting is on Friday at 9 a.m. India Standard Time.'),
('Does that give their local time?','No. It gives the meeting time in India Standard Time only.'))
add('clarification','ambiguous_pronoun_report',
('Asha told Leena that she had lost the report. Who lost it?','“She” could refer to Asha or Leena. That sentence alone does not tell us.'),
('It was Leena. Make it unambiguous.','Asha told Leena, “You have lost the report.”'),
('No direct speech, please.','Asha told Leena that Leena had lost the report.'),
('Who delivered the news?','Asha.'))
add('clarification','unprovided_attachment',
('Summarise the attachment for me.','I do not have an attachment in this conversation. Please paste the text you want summarised.'),
('Here is the whole note: The courtyard will be closed on Thursday for cleaning. Use the side entrance.','The courtyard is closed on Thursday for cleaning; use the side entrance.'),
('What time does it reopen?','The note does not give a reopening time.'),
('Can you guess for the summary?','I would leave the time out so the summary does not present a guess as part of the notice.'))
add('grounding','cafe_notice_limit',
('The cafe sign says: Sandwiches available until noon. Drinks served until closing. Can I get a sandwich at three?','According to the sign, sandwiches are only available until noon, so not at three in the afternoon.'),
('I meant three in the morning.','The sign does not say when the cafe opens or whether it serves food overnight. It cannot confirm availability at 3 a.m.'),
('Does it say the closing time?','No. It mentions closing without giving a time.'),
('Give me one question to ask the staff about drinks.','What time do you stop serving drinks?'))
add('grounding','borrowed_review_claim',
('One review says this backpack lasted its owner five years. Does that prove mine will last that long?','No. That is one owner’s experience, not a guarantee for your backpack.'),
('The listing also says it has a two-year warranty. Is that the same as a two-year lifespan?','No. A warranty describes coverage under its terms; it does not state exactly how long the backpack will last.'),
('What can I confidently repeat from what I gave you?','One reviewer reports five years of use, and the listing states a two-year warranty.'),
('Have you checked the listing yourself?','No. I am relying on the details you shared.'))
add('entity_roles','ticket_payment_collection',
('Isha booked tickets for herself and Ravi. Ravi paid her back. Sal will collect both tickets. Who is attending?','Isha and Ravi are attending.'),
('Sal gives the tickets to Ravi at lunch. Who holds them now?','Ravi holds both tickets now.'),
('Does collecting the tickets make Sal a guest?','No. Sal was collecting them for Isha and Ravi; you have not said Sal is attending.'),
('Who made the booking?','Isha.'))
add('entity_roles','shared_flat_shopping',
('In our flat, Noor writes the shopping list, Vic buys the groceries, and I put them away. Who should I tell if milk is missing from the list?','Tell Noor, who writes the shopping list.'),
('For this week only, Noor and Vic swap jobs.','This week Vic writes the list and Noor buys the groceries. You still put them away.'),
('Who should get the list correction this week?','Vic.'),
('And next week, if we return to our usual arrangement?','Noor.'))
add('correction','outing_transport_switch',
('We will take the bus to the lake on Sunday. I am bringing lunch. Can you keep the plan straight?','Sunday: take the bus to the lake, with lunch provided by you.'),
('Change the bus to a train. Sunday and lunch stay the same.','Sunday: take the train to the lake. You are bringing lunch.'),
('Actually the train is cancelled. We will cycle.','The current plan is to cycle to the lake on Sunday, and you will bring lunch.'),
('What was our first transport choice?','The bus.'),
('What should I tell everyone to prepare for now?','Cycling to the lake on Sunday.'))
add('correction','workshop_day_override',
('The weaving workshop is Tuesday in the upstairs room.','Tuesday, upstairs room.'),
('I copied the wrong day. It is Wednesday.','The weaving workshop is Wednesday in the upstairs room.'),
('Someone suggested the downstairs hall, but we have not agreed to move.','The upstairs room remains the confirmed location; the downstairs hall is only a suggestion.'),
('Which details should go on the confirmed notice?','Wednesday, upstairs room.'),
('Now the organiser has confirmed the hall. Update only the place.','Wednesday, downstairs hall.'))
add('correction','packing_item_removal',
('My overnight bag needs a towel, a charger and a notebook.','Your list is: towel, charger, notebook.'),
('The guesthouse provides towels. Remove that.','Charger, notebook.'),
('Add a paperback.','Charger, notebook, paperback.'),
('I already packed the charger. What remains to pack?','The notebook and paperback.'),
('Did I pack the towel?','You did not say you packed it. You removed it because the guesthouse provides towels.'))
add('correction','cinema_seat_correction',
('I told Jo our seats were D4 and D5.','Jo currently has D4 and D5 as the seat numbers.'),
('I read the tickets again. They say F4 and F5.','The correct seats are F4 and F5. Jo needs the updated row.'),
('Write the correction, but do not blame the cinema.','Hi Jo, I misread our tickets. Our seats are F4 and F5, not D4 and D5.'),
('Did the seat numbers change or did I read them wrong?','You said you read them wrong; you have not described a booking change.'))
add('memory','birthday_surprise_boundary',
('We are planning a surprise picnic for Uma. Do not mention the picnic in the message we send her.','Understood. The message to Uma should leave out the picnic.'),
('Ask her to keep Saturday afternoon free.','Hi Uma, could you keep Saturday afternoon free?'),
('For the group organising it, mention that Ken will bring the plates.','Ken will bring the plates for Uma’s surprise picnic.'),
('What could we use if it rains? Just one option.','You could arrange an indoor room as a backup.'),
('We have not booked a room. Now show me the message for Uma again.','Hi Uma, could you keep Saturday afternoon free?'),
('What was Ken responsible for?','Bringing the plates.'))
add('memory','borrowed_umbrella_return',
('I borrowed a green umbrella from Ellis. I need to return it at choir practice.','Return Ellis’s green umbrella at choir practice.'),
('I also have my own black umbrella by the door.','The black umbrella is yours; the green one belongs to Ellis.'),
('What is a less formal word for borrowed?','“Borrowed” is already natural in everyday speech. “Lent” describes the same arrangement from the giver’s side.'),
('Show me that using Ellis.','Ellis lent me a green umbrella.'),
('Which umbrella am I taking back, and when?','The green umbrella, at choir practice.'))
add('memory','weekend_preferences_return',
('Help me choose something for Sunday. I want to stay indoors and avoid crowds.','A quiet activity at home could fit, such as drawing or listening to an audiobook.'),
('I would like to leave home, though.','You could look for a small gallery at a quieter time. It keeps you indoors, though you would need to check how busy it is.'),
('What does a gallery usually display?','A gallery usually displays art, such as paintings, photographs or sculptures.'),
('My friend suggested a crowded outdoor market. Does it fit what I asked for?','No. You wanted to stay indoors and avoid crowds; a crowded outdoor market conflicts with both.'),
('Did I say I needed it to be free?','No, you did not specify a budget.'))
add('memory','library_reservation_update',
('I reserved a book under the name Keira Moss. Pickup is at the west branch.','The reservation is under Keira Moss, with pickup at the west branch.'),
('They have moved pickup to the central branch. The name is unchanged.','Pickup is now at the central branch, under Keira Moss.'),
('Help me ask whether I need identification.','Do I need to bring identification to collect my reserved book?'),
('Can you make that shorter?','Do I need ID to collect my book?'),
('Which branch should I head to?','The central branch.'),
('And what name should I give them?','Keira Moss.'))
