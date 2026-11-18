"""Persist explicit author second-pass judgments; not independent review."""
import hashlib,importlib.util,json
from pathlib import Path
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('batch',R/'authored_source_b02.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
NOTES={
'weekend_without_schedule':'Final summary retains one drawer and free remainder; no productivity pressure or new task added.',
'new_neighbour_hello':'Mira is user-supplied; note preserves welcome without unsupported promises or neighbour details.',
'unfinished_hobby':'Clarifies goal before advice, distinguishes painting preference from assembly, listing honestly says unfinished.',
'rainy_window_break':'Honours no-screen and later no-productivity-advice preference; does not invent a problem needing intervention.',
'book_recommendation_missing_taste':'Clarifies taste; generic genre guidance avoids fabricated book titles. Novella/collection distinction accurate with usually qualifier.',
'meeting_time_missing_zone':'Asks for missing zone, preserves Friday 9 a.m. IST, no unrequested conversion or assumed colleague location.',
'ambiguous_pronoun_report':'Acknowledges ambiguous referent, uses user clarification, removes direct speech when asked, separates speaker from person losing report.',
'unprovided_attachment':'Does not pretend attachment access; summary uses pasted note only; unknown reopening stays unknown.',
'cafe_notice_limit':'Initial answer explicitly limits interpretation to afternoon; corrected 3 a.m. remains unknown without opening hours. Closing time not invented.',
'borrowed_review_claim':'Distinguishes anecdote, warranty and lifespan; explicitly discloses no independent listing access.',
 'ticket_payment_collection':'Separates attendee, booker, payer and current custodian. Collection never implies attendance.',
'shared_flat_shopping':'Tracks temporary job swap and explicit next-week reset; user retains unpacking role.',
'outing_transport_switch':'Bus/train/cycle updates preserve Sunday, lake and lunch; historic bus distinguished from current cycle.',
'workshop_day_override':'Corrected Wednesday retained; suggested hall does not override confirmed room until explicit confirmation.',
'packing_item_removal':'Distinguishes removed towel from packed charger; remaining list excludes both for different reasons.',
'cinema_seat_correction':'Corrects row D to F while preserving 4/5; attributes error to user reading rather than changed booking.',
'birthday_surprise_boundary':'Audience-specific secrecy survives organisational message and rain distraction; room remains unbooked; Ken plates recalled.',
'borrowed_umbrella_return':'Ownership/colour and return occasion survive vocabulary distraction; borrowed/lent perspectives correct.',
'weekend_preferences_return':'Indoors/no-crowds retained after leave-home refinement and gallery detour; no invented free-budget constraint.',
'library_reservation_update':'Central replaces west, Keira Moss unchanged across two wording turns; no inference that ID is required.'}
assert set(NOTES)=={a['group'] for a in m.ROWS}
rows=[]
for a in m.ROWS:
 messages=[dict(role=role,content=text) for pair in a['turns'] for role,text in zip(('user','assistant'),pair)]
 rows.append(dict(group=a['group'],messages_sha256=hashlib.sha256(json.dumps(messages,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),decision='shortlist',reviewer='Codex author second semantic pass',independent_review=False,assistant_turns_reviewed=len(a['turns']),rationale=NOTES[a['group']],training_admitted=False))
(R/'authored-review-b02.json').write_text(json.dumps(rows,indent=2)+'\n')
print(f'Recorded {len(rows)} author reviews; {sum(x["assistant_turns_reviewed"] for x in rows)} assistant turns')
