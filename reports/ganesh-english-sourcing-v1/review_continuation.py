"""Explicit second-pass review evidence. Same author, not independent admission."""
import hashlib,importlib.util,json
from pathlib import Path
R=Path(__file__).resolve().parent
# Group: substantive semantic judgment, exact final answer, optional (last supporting turn, recall probe turn).
REVIEWS={
'b03':{
'bakery_order_flavour':('Vanilla supersedes lemon; day and inscription preserved. Chocolate question is not an order. Original flavour retained only as historical fact.','Lemon.'),
'volunteer_shift_pending':('Pending afternoon request does not change shift. Decline draft not treated as sent. Explicit later yes changes shift while desk remains; old rota is stale.','No. The change became agreed when you said yes.'),
'dog_walker_key':('Detects inaccessible key location; explicit handover to Luis resolves access. Tracks porch to drawer to Luis without inventing a second key.','Luis.'),
'poster_date_typo':('16 June was always intended. Correction avoids false postponement, preserves venue and recalls erroneous 14 June.','14 June.'),
'garden_watering_exclusion':('Exception binds plant plus patio location, not all striped pots. Mint is separately added; final answer preserves cactus exception.','The cactus in the striped pot on the patio.'),
'hotel_arrival_not_departure':('Tuesday replaces arrival only; Thursday retained. Bag question neither grants storage nor early check-in. Final answer distinguishes departure.','No. It is still Thursday.'),
'project_title_reverted':('Tracks original, trial and revert. Mood is tentative interpretation. Bare title obeys format; discarded title is historical.','Winter Seeds.'),
'lunch_allergy_scope':('Preserves Mina peanut allergy versus Sol raw-onion preference; no dish or safety guarantee; unknown peanut status for Sol stays unknown.','No. The ingredients and preparation need to be checked with the people involved.'),
'archive_box_location':('Box/contents/shelf retained across labelling, preservation, sister message and envelope discussion. Does not invent shelf for postcards.','No. You identified the green box but did not give its shelf.',(1,6)),
'walking_route_preference':('Avoid-steps preference survives two photo exchanges. Suggested climbing is identified as conflict; photos are not incorrectly excluded.','No. You were interested in taking photos; it was the steep steps you wanted to avoid.',(1,4)),
'radio_show_callback':('Programme title and Wednesday preserved through encouragement and interview questions; does not infer morning start time from title.','You have not told me the start time.',(1,5)),
'costume_colour_commitment':('Found gold scarf is not a committed change. Purple remains after return-question detour; silver gloves attributed to Theo.','The silver gloves.',(1,6)),
'recipe_no_oven':('Advice fits supplied frying pan; no assumed toaster. Crisp/burnt distinction accurate; equipment restriction recalled.','No. You mentioned a frying pan, not a toaster.',(1,5)),
'ferry_meeting_landmark':('Red clock retained through reassurance, ticket check, unknown gate and arrival-message detour. Never invents gate; ticket machines explicitly excluded.','No. You specifically chose the red clock instead.',(1,6)),
'gift_keep_receipt':('Receipt moved to drawer, not discarded; card preference forbids daily-writing message. Location persists after card and grammar exchanges.','No. You specifically wanted to keep it.',(2,5)),
'house_sitting_cat_rule':('Study restriction survives parcel and arrival messages; no reopening permission inferred from cat waiting. Parcel remains pending and destination retained.','On the kitchen table.',(1,5))},
'b04':{
'interview_remote_location':('Video supersedes office attendance; Anil retained. Link request not fabricated link, interviewer not changed.','The video-call link.'),
'delivery_recipient_not_owner':('Corrects recipient to Bea, keeps Ada as purchaser; possession moves Finn to Ada. Message speakers and recipient roles consistent.','No. You described Finn receiving and passing on Bea’s parcel, not ordering for himself.'),
'photo_credit_correction':('Swaps artist roles explicitly; subsequent abbreviation/line format does not revert credits. Single photographer kept distinct from frame designer.','You named one photographer, Rose. Nabil designed the frame.'),
'club_vote_not_final':('Popularity is not decision. Confirmed Friday starts next month, not this week; announcement respects effective date.','The chair confirmed the change and specified that it starts next month.'),
'camp_tent_assignment':('Tracks Kim to green and Pat to cabin; Jules stays blue, no invented new tentmate. Bare-name format correct.','Kim.'),
'reading_order_exception':('Move-to-end preserves remaining order, then explicit interview-first overrides. Final poem position and historical never-first are correct.','No. It started second and then moved to the end.'),
 'theatre_refund_request':('Refund replaces exchange. Draft asks eligibility, supplies no reference number, and never treats request as approval.','No reply or promise from the theatre has been shared.'),
'laundry_label_revision':('Different-item label correction supersedes washing advice. Explaining old phrase does not reinstate old instruction.','You were reading the other scarf’s label.'),
'repair_quote_not_permission':('Quote, inspection and repair permission separated. Desire for affordable repair is not approval or spending limit. Cost remains unconfirmed.','No. Repairs and replacement parts have not been authorised.',(2,5)),
'choir_pronunciation_note':('Person-specific AH-na preference retained through welcome/introduction tasks; user is another singer not conductor; no universal name claim.','No. We are following this Ana’s stated preference; other people may pronounce their names differently.',(1,6)),
'shared_studio_storage':('Shared shelves do not imply shared drawers. B remains user drawer after two cleaning-sign turns; A remains Wren’s.','No. You said drawer A belongs to Wren and the drawers should stay separate.',(2,5)),
'visitor_access_instruction':('Side bell survives wait request and phrasing detour. Combined message uses correct bell; front failure is user-supplied.','You said the front bell is broken.',(1,5)),
'lost_ring_search_boundary':('Last remembered wearing location is not loss location. Checked counter not expanded to whole kitchen. Separate uncertainty and search coverage.','The kitchen counter.',(2,6)),
 'trip_no_early_start':('Earliest departure ten retained through browsing detour. Seven fails preference; ten is not return deadline.','No. Ten was your earliest departure time, not a time to be home.',(2,5)),
'concert_earplug_pocket':('New bag does not move items. Earplugs inside, tickets outside coat, preserved after message phrasing task.','You said the tickets are in the outer coat pocket and that nothing had been moved into the bag.',(2,5)),
'letter_private_detail':('Context can be recalled privately but omitted from recipient note. Warmth added without gift, no family-disagreement leak in final note.','Thank you so much for feeding my fish while I was away. It meant a lot to know they were being looked after.',(2,5))},
'b05':{
'recording_consent_withdrawn':('Withdraws recording permission as requested, online prohibition remains. Message is wording only, not enforcement or cancellation of talk.','No. It concerns recording, not cancelling the talk.'),
'catering_guest_count_unknown':('Double-count correction yields seven including user; possible extra not counted as confirmed. Incidental count tracking, not a maths curriculum item.','You had been counted twice.'),
'exhibition_caption_author':('Hana artist, Farid owner; title retained. Caption excludes ownership on request, later owner query correctly separates roles.','No. It is still Evening Boats.'),
'book_donation_exception':('Exception is dictionary, not all red books; removal resolves box donation instruction. Current kept-book location is desk.','On your desk.'),
'parcel_collect_after_notice':('Expected readiness not confirmation, delay supersedes estimate, received notice releases wait. Closing time remains unknown.','No closing time has been shared.'),
'room_noise_priority':('Updated quiet priority overrides original view, balcony remains optional. Comparative response follows latest preference, history retained.','The view.'),
'mentor_feedback_scope':('Grammar correction and separate tone task do not bleed together. Original sentence deliberately quoted when requested, corrected version distinguished.','No. It concerned the tone of “Send it now,” not the earlier sentence about volunteers.'),
'address_old_new_comparison':('13 corrects mistyped 31 only, old 8 Willow untouched. Form preserves old/new, final history does not turn typo into old address.','No. It was the mistyped new house number.'),
'plant_label_not_species':('Nickname does not identify species. Caption personification described as figurative; no taxonomy inferred from pot or name.','Your nickname for the plant on your desk.',(1,5)),
'meeting_topic_parked':('Today reading plus snacks, fees explicitly next week. Vocabulary detour does not pull deferred topic into current agenda.','It is deferred to next week.',(2,5)),
'bakery_pickup_delegate':('Order identity Ellis Ward distinct from collector Noor; confirmation requirement retained; wording changes do not rename purchaser.','Yours, Ellis Ward. Noor is collecting it.',(1,5)),
'photo_album_no_dates':('Place/action known, year/posing unknown; captions exclude both invented year and unsupported candid claim.','You have not supplied the year, and we agreed not to guess dates.',(1,6)),
'weather_plan_conditional':('Forecast not final location. Text update commitment preserved; explicit Sunday rain plus confirmation selects hall, garden remains counterfactual.','The garden.',(1,7)),
'rental_return_accessory':('Projector/cable packed, remote left on sofa. Missing control not speaker fault. Return completeness survives shop-feedback and timing detours.','No. You said all three rented items need to go back.',(2,6)),
'volunteer_language_preference':('Plain-English audience constraint retained. Dena and centre grounded; jargon rejected and simple final note supplied.','You asked for plain English for people who are still learning it.',(1,6)),
'story_character_knowledge':('Character-specific knowledge enforced until explicit text disclosure. Reader knowledge not assigned to Ben; final answer distinguishes initial from current.','Lia knew; Ben had not been told.',(1,6))},
'b06':{
'market_payment_method':('Cards as well adds option, not replaces cash. User preference separate from stall capability. Final history cash only.','Cash only.'),
'school_trip_permission_status':('Completed, sent and acknowledged are different states. Acknowledgment appears only after explicit reply; initial blocker submission.','Submission. You had filled in the form but had not sent it.'),
'garage_item_keep':('Withdrawn sale status applies before physical move; neither move nor missing price means sold. Correct event order.','Its sale status. You decided to keep it before moving it indoors.'),
'flight_pickup_direction':('From replaces to airport; Friday retained, Max acceptance unknown. No post-airport destination invented.','No. You have not specified where Max would take you after collecting you.'),
'festival_location_pending':('Removing square yields unknown venue until field confirmed. Mentioned option not commitment; interval with no confirmed venue preserved.','Yes. After the square was ruled out and before the school field was confirmed.'),
'shared_calendar_private':('Public label hides dentist while chat retains context. Explicitly no calendar action; model does not falsely claim execution.','The dentist appointment.'),
'painting_finish_selection':('Matte replaces finish only, colour warm white retained. Explanation does not mutate colour; original glossy recalled.','Glossy.'),
'host_name_misspelling':('Rina correction retained through expansion and casual tone. Reena not new person, final name-only response obeys format.','Rina'),
'swim_bag_locker_key':('Different keys remain in distinct places after towel move and vocabulary detour; no transfer into carrier inferred.','No. Your house key is in your jacket.',(2,5)),
'debate_position_attribution':('Nia evenings and Owen before-work reasons kept separate from neutral user. No claim all members benefit without schedules.','No. You said you had not taken a side.',(1,7)),
'poem_image_constraint':('No boats/ships and later no bird persist through poetry explanation and title addition; final list recalls cumulative exclusions.','Ships, boats and the bird.',(2,5)),
'bread_storage_note':('Rye stays freezer and white stays bin; intent to use rye is not actual movement. Irregular plural correct.','No. You explicitly said you had not moved it.',(2,5)),
'walking_group_pace':('Relaxed pace and architectural pauses retained across vocabulary task; slower group selected, no distance maximisation invented.','No. You asked for a relaxed pace and time to look at buildings.',(2,5)),
'neighbour_parcel_permission':('Receive permission distinct from open permission and ownership; courier flat grounded. No implied inspection authorisation.','It is still your parcel; Eden is holding it for you.',(1,5)),
'museum_audio_language':('English user/Spanish sister/headphones retained through independent-use and pickup questions. Museum rules explicitly unknown.','No. You said both of you prefer headphones.',(2,7)),
'weekend_cabin_boundary':('Bedroom sharing acceptable, communal bathroom not. Private-bath listing fits supplied constraints; en suite definition does not imply bed count.','Sharing a bedroom with your sister.',(2,5))}}
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
REVIEWS['b07']=json.loads((R/'review_b07_notes.json').read_text())
for batch,notes in REVIEWS.items():
 spec=importlib.util.spec_from_file_location(batch,R/f'authored_source_{batch}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 assert set(notes)=={a['group'] for a in m.ROWS}
 out=[]
 for a in m.ROWS:
  note=notes[a['group']];assert a['turns'][-1][1]==note[1],a['group']
  messages=[dict(role=role,content=text) for pair in a['turns'] for role,text in zip(('user','assistant'),pair)]
  row=dict(group=a['group'],messages_sha256=digest(messages),decision='shortlist',reviewer='Codex author second semantic pass',independent_review=False,assistant_turns_reviewed=len(a['turns']),reviewed_turn_numbers=list(range(1,len(a['turns'])+1)),rationale=note[0],training_admitted=False,checks=[dict(turn=len(a['turns']),expected_assistant_exact=note[1])])
  if len(note)>2:
   support,probe=note[2];assert 1<=support<probe<=len(a['turns'])
   row['recall_probe']={'last_supporting_turn':support,'probe_turn':probe,'intervening_complete_turns':probe-support-1,'expected_assistant_exact':a['turns'][probe-1][1],'annotation_scope':'This one probe only; author assessed support, not an independent memory benchmark.'}
  out.append(row)
 (R/f'authored-review-{batch}.json').write_text(json.dumps(out,indent=2)+'\n')
 print(batch,len(out),'conversations',sum(x['assistant_turns_reviewed'] for x in out),'reviewed replies')
