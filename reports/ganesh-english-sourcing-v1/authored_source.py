"""Original full trajectories; no programmatic variants or borrowed source answers."""
ROWS=[]
def add(family,group,*turns):
 ROWS.append({'family':family,'group':group,'turns':turns})
add('ordinary','balcony_first_seedling',
('The first seedling on my balcony has finally appeared. I kept checking the pot every morning.','That must have been a satisfying little surprise after all that waiting. What are you growing?'),
('Basil. I mostly wanted something green to look at while I have breakfast.','A small pot of basil sounds like a lovely addition to that routine.'),
('Can you write a caption for a photo? Nothing grand.','A little green company for breakfast.'))
add('ordinary','quiet_bus_journey',
('My bus was almost empty today, and I actually enjoyed the journey.','An unexpectedly quiet journey can be a welcome pause in the day.'),
('I watched the shops opening. Usually I just scroll on my phone.','It sounds as though you noticed a part of the morning you normally miss.'),
('Say that more simply.','You noticed things you usually scroll past.'))
add('ordinary','finished_photo_album',
('I finally put the old family photos in an album. There are still some without dates.','The album is finished even if a few dates are missing. You can leave space to add them later.'),
('I was thinking of asking my aunt about them next time we meet.','You could bring the album and ask whether she remembers when those photos were taken.'),
('Help me write her a casual message.','I put the old family photos in an album. Could we look through it together next time? I am missing a few dates.'))
add('clarification','missing_invitation_place',
('Write a short invitation to our reading group this Saturday at eleven. Include where we meet.','Where is the group meeting?'),
('The small room behind the library desk.','Join our reading group this Saturday at eleven in the small room behind the library desk.'),
('Actually, make it an invitation to bring a friend too.','Join our reading group this Saturday at eleven in the small room behind the library desk, and feel free to bring a friend.'))
add('clarification','ambiguous_lent_camera',
('Rosa lent Nikhil a camera. Who owns the camera?','The sentence says Rosa lent it to Nikhil, but it does not say who owns it.'),
('It belongs to Rosa. Who should Nikhil return it to?','Rosa.'),
('Write a friendly reminder from Rosa, without a deadline.','Hi Nikhil, could you return my camera when you have a chance? Thanks!'))
add('clarification','unknown_notice_audience',
('Help me write a notice about the lift being unavailable.','Who is the notice for, and when will the lift be unavailable?'),
('For residents. Tomorrow morning, with no confirmed finishing time.','Notice to residents: The lift will be unavailable tomorrow morning. A finishing time has not yet been confirmed.'),
('Can you add when it will reopen?','There is no confirmed reopening time to add. You could say: We will share an update when a reopening time is confirmed.'))
add('instructions','two_line_shop_notice',
('Write a notice using exactly two lines. Say the shop closes early today, then apologise. No heading.','The shop closes early today.\nSorry for the inconvenience.'),
('Replace the apology with a thank-you. Keep the two lines.','The shop closes early today.\nThank you for your understanding.'),
('Now make it one sentence, with no thank-you or apology.','The shop closes early today.'))
add('instructions','no_question_evening',
('I have had a long day. Please reply warmly, but do not ask me a question.','I hope you get a little time to rest this evening.'),
('Suggest one quiet thing I could do at home. Still no questions.','You could sit comfortably and listen to a favourite album.'),
('Make the suggestion shorter.','Listen to a favourite album.'))
add('instructions','three_item_plain_list',
('Give me three things to take on a short walk in warm weather. Use a plain comma-separated list, not bullets.','water, hat, sunscreen'),
('I will be indoors instead. Keep the same format and give me things for a drawing session.','paper, pencil, eraser'),
('Now give only the second item, with no punctuation.','pencil'))
add('grounding','museum_notice_exceptions',
('The notice says: The museum opens on Tuesday and Thursday. The garden opens daily. Is the museum open on Wednesday according to this notice?','No. The notice lists Tuesday and Thursday for the museum; only the garden opens daily.'),
('Does it tell us when the garden closes?','No, it does not give a closing time.'),
('Summarise just the garden information.','The garden opens daily.'))
add('grounding','parcel_tracking_unknown',
('My tracking page says the parcel left the depot this morning. Does that mean it has arrived?','No. Leaving the depot does not confirm that it has arrived.'),
('There is a new entry: Delivered to reception. Where should I ask about it?','At reception.'),
('Who signed for it?','The information you shared does not say who signed for it.'))
add('grounding','lost_property_description',
('Lost-property note: A grey scarf with a yellow label was found beside the fountain. Write a short announcement using only those facts.','A grey scarf with a yellow label was found beside the fountain.'),
('Can you say it belongs to a visitor?','The note does not say who owns it, so I would leave that out.'),
('What colour is the label, not the scarf?','Yellow.'))
add('entity_roles','choir_keys_custody',
('The rehearsal-room keys belong to the caretaker. Jaya borrowed them and then handed them to Omar. Who has them now?','Omar has the keys now.'),
('Omar gives them back to Jaya. Has ownership changed?','No. The keys still belong to the caretaker; Jaya now has them.'),
('Write Jaya a reminder to return them to their owner.','Jaya, please return the rehearsal-room keys to the caretaker.'))
add('entity_roles','pottery_order_collection',
('Elena ordered a bowl from Dev. Her brother Arun will collect it. Who made the order?','Elena made the order.'),
('Arun cannot go, so Elena asks Mei to collect it instead. Who should Dev expect?','Mei.'),
('Write a short message from Elena to Dev explaining the change.','Hi Dev, Mei will collect my bowl instead of Arun.'))
add('entity_roles','book_swap_ownership',
('Nora owns the atlas and Yusuf owns the cookbook. They exchange books for the weekend. Which book is Nora borrowing?','Nora is borrowing Yusuf\'s cookbook.'),
('On Sunday they return both books. What does Yusuf have now?','His cookbook.'),
('Did the atlas ever become Yusuf\'s property?','No. It remained Nora\'s atlas; Yusuf only borrowed it.'))
add('correction','picnic_entry_change',
('Write a message saying we will meet at the park\'s east gate for the picnic.','Let\'s meet at the park\'s east gate for the picnic.'),
('The east gate is closed. Change it to the entrance beside the pond.','Let\'s meet at the park entrance beside the pond for the picnic.'),
('Add that I will bring a blanket.','Let\'s meet at the park entrance beside the pond for the picnic. I will bring a blanket.'),
('Where are we meeting now?','At the park entrance beside the pond.'))
add('correction','repair_delivery_address',
('Please draft a note: Deliver the repaired lamp to my office on Hill Road.','Please deliver the repaired lamp to my office on Hill Road.'),
('Wait, I will be at home. The address is Lake View, flat C. Use that instead.','Please deliver the repaired lamp to my home at Lake View, flat C.'),
('Keep the address but remove the word home.','Please deliver the repaired lamp to Lake View, flat C.'),
('Which address did we replace?','Your office on Hill Road.'))
add('correction','guest_list_replacement',
('The guests are Lila, Ben and Saira. Write the names on one line.','Lila, Ben, Saira'),
('Ben cannot come. Replace him with Tomas.','Lila, Tomas, Saira'),
('Saira will arrive late. Does that change who is invited?','No. The guests are still Lila, Tomas and Saira; Saira will arrive late.'),
('Who is no longer attending?','Ben.'))
add('memory','tea_preference_distractor',
('For our meeting, I would like peppermint tea rather than coffee. Draft a quick note to the host.','Could I have peppermint tea rather than coffee at our meeting, please?'),
('Also, I may arrive a little early. Add that.','Could I have peppermint tea rather than coffee at our meeting, please? I may arrive a little early.'),
('What is a more casual way to say arrive?','Get there.'),
('Which drink did I ask for at the beginning?','Peppermint tea.'))
add('memory','rehearsal_room_colour',
('We booked the room with the orange door for rehearsal. Write a reminder.','Rehearsal is in the room with the orange door.'),
('Add that everyone should bring their music sheets.','Rehearsal is in the room with the orange door. Please bring your music sheets.'),
('Make just the second sentence more casual.','Bring your music sheets along.'),
('Which door should a new member look for?','The orange door.'))
add('memory','train_platform_update',
('My note says platform six, but the new display says platform two. Which one should I put in the message to my friend?','Platform two, based on the newer information you shared.'),
('Write the message, and mention that I am near the front of the train.','The platform has changed to two. I am near the front of the train.'),
('Can you make that sound less formal?','It\'s platform two now. I\'m near the front of the train.'),
('What was the old platform?','Platform six.'))
add('rewrite','tentative_roof_repair',
('Shorten this without making it certain: The roof repairs may be finished by the end of the week.','The roof repairs may finish this week.'),
('Make it clear that this is not confirmed.','The roof repairs may finish this week, but this is not confirmed.'),
('Are we promising they will be finished this week?','No. The wording leaves the finishing time uncertain.'))
add('rewrite','negative_attendance_note',
('Make this polite without changing the answer: I am not coming to the dinner.','Thank you for inviting me, but I will not be coming to the dinner.'),
('Remove the thank-you and give no reason.','I will not be attending the dinner.'),
('Does the message explain why?','No, it does not give a reason.'))
add('rewrite','preserve_reason_not_supplied',
('Rewrite this more smoothly: We went home because the library was closed. Do not invent why it was closed.','The library was closed, so we went home.'),
('Avoid implying that one event caused the other.','The library was closed, and we went home.'),
('Now mention only what happened to us.','We went home.'))
