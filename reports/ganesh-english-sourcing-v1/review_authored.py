"""Explicit second-pass judgments for the24 original, fully read trajectories."""
import hashlib,importlib.util,json
from pathlib import Path
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('source',R/'authored_source.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
notes={
'balcony_first_seedling':'Basil and breakfast motivation preserved; caption requested, no unsolicited horticultural fact.',
'quiet_bus_journey':'Paraphrases observed shops/phone contrast without claiming a location or purpose; final simplification direct.',
'finished_photo_album':'Does not invent missing dates; asks aunt through a drafted message rather than claiming to contact her.',
'missing_invitation_place':'Asks only missing venue, then incorporates supplied location and bring-friend change.',
'ambiguous_lent_camera':'Ownership initially unknown despite lending; ownership supplied in turn2; reminder invents no deadline. Replaced gendered ambiguous setup before finalisation.',
'unknown_notice_audience':'Clarifies audience/time; preserves unknown reopening instead of inventing finishing time.',
'two_line_shop_notice':'Two lines then thank-you replacement, followed by one sentence with neither courtesy clause; exact line structure checked.',
'no_question_evening':'Warm replies contain no questions; one quiet home activity and shorter imperative preserve instruction.',
'three_item_plain_list':'Three comma-separated items in each domain, then exact second item pencil with no punctuation.',
'museum_notice_exceptions':'Distinguishes museum schedule from garden; closing time remains unknown; final summary contains only supplied garden fact.',
'parcel_tracking_unknown':'Departure is not delivery; newer reception delivery updates state; signer remains unknown.',
'lost_property_description':'Announces only supplied facts, refuses unsupported ownership, disambiguates label colour from scarf.',
'choir_keys_custody':'Ownership and possession tracked separately through handoffs; final reminder names correct owner.',
'pottery_order_collection':'Orderer remains Elena; Mei replaces collector Arun; drafted message preserves roles.',
'book_swap_ownership':'Weekend loan changes possession, not ownership; both returns interpreted correctly.',
'picnic_entry_change':'East gate replaced by pond entrance in all subsequent drafts and final recall; blanket added only when requested.',
'repair_delivery_address':'Hill Road replaced by Lake View flat C; remove-home request retains address; final question explicitly asks superseded address.',
'guest_list_replacement':'Ben replaced with Tomas; Saira late does not remove her; final removed guest correct.',
'tea_preference_distractor':'Peppermint tea retained through arrival update and vocabulary distractor; no switch to coffee.',
'rehearsal_room_colour':'Orange door survives music-sheet rewrite; edits only requested second sentence; final door correct.',
'train_platform_update':'New platformtwo distinguished from historicalsix; final question asks old platform, answeredsix. No live transport claim.',
'tentative_roof_repair':'May remains uncertain through rewrite and explicit confirmation question; no promise.',
'negative_attendance_note':'Negative attendance preserved; requested removal of thanks and absence of reason respected.',
'preserve_reason_not_supplied':'Initial source explicitly supplies reason for going home after review fix; why library closed stays unknown. Later removes causal link on request, then retains only action.'}
assert set(notes)=={x['group'] for x in m.ROWS}
out=[]
for r in m.ROWS:
 messages=[{'role':role,'content':text} for pair in r['turns'] for role,text in zip(('user','assistant'),pair)]
 out.append({'group':r['group'],'messages_sha256':hashlib.sha256(json.dumps(messages,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'decision':'shortlist','reviewer':'Codex author, second semantic pass','independent_review':False,'assistant_turns_reviewed':len(r['turns']),'rationale':notes[r['group']],'training_admitted':False})
(R/'authored-review.json').write_text(json.dumps(out,indent=2)+'\n');print('24 full trajectories second-pass reviewed; not independent and not admitted')
