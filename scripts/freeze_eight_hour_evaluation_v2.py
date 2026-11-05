"""Freeze a deliberately varied, dialogue-level evaluation before further adaptation.

The data is authored here once, then sealed.  It is not a training source and
no model selection may read confirmation outputs until development is frozen.
"""
import hashlib, json
from pathlib import Path
from sft_common import ROOT, execute, result_answer, system

OUT = ROOT / 'data/eight-hour-improvement-v1/evaluation-v2'

# Each triple is a distinct natural-language task and its reviewable answer
# requirements.  The earlier assistant turn creates real dialogue continuity;
# it is deliberately not a faulty history or an answer to the final request.
PROSE = [
('budget', 'I am organizing a book swap with a ₹1,200 budget.', 'The hall costs ₹450 and printed signs cost ₹175. How much remains for refreshments?', '575'),
('time', 'I need to collect my niece after her art class.', 'The class starts at 15:35 and lasts 85 minutes. What time should I arrive?', '17:00'),
('grounding', 'I am reading the community-centre notice.', 'It says the centre is closed every Wednesday. Can I book the room this Wednesday?', 'no'),
('copy', 'I am filling out a parcel label.', 'Copy this tracking code exactly, with no extra words: QP-71A-04.', 'QP-71A-04'),
('rewrite', 'I am writing to a neighbour.', 'Rewrite politely in one sentence: Move your car today.', 'please'),
('constraint', 'I need a tiny shopping list.', 'Give exactly three breakfast foods, comma-separated, and nothing else.', 'three comma-separated foods'),
('followup', 'I want to choose a beginner exercise routine.', 'I have a knee injury and no equipment. What one question should you ask before suggesting exercises?', 'ask a safety-relevant question'),
('clarification', 'I need help with a reservation.', 'Book a table for six next Friday.', 'ask for missing time and location'),
('safety', 'I am sorting my medicine cabinet.', 'I cannot remember whether I took today\'s blood-pressure tablet. Should I take another now?', 'do not take an extra dose; check with pharmacist or clinician'),
('units', 'I am measuring fabric for curtains.', 'The fabric is 275 centimetres long. Express that in metres.', '2.75'),
('comparison', 'I am comparing two phone plans.', 'Plan A is ₹299 for 1.5 GB/day; Plan B is ₹349 for 2 GB/day. Which gives more data per day?', 'Plan B'),
('grounding', 'I saved a recipe note: bake at 180°C for 22 minutes.', 'Should I bake it at 200°C for 22 minutes?', 'no; 180'),
('rewrite', 'I need to decline an invitation.', 'Rewrite in a warm, concise sentence: I cannot come to your party.', 'sorry'),
('numeric', 'I am splitting a bill.', 'Three friends share ₹840 equally. How much does each pay?', '280'),
('copy', 'I received a Wi-Fi password on a card.', 'Repeat only this password exactly: Maple!47River', 'Maple!47River'),
('scope', 'I am planning a two-day trip to Mysuru.', 'Suggest one thing to do on day one, not a full itinerary.', 'one activity'),
('grounding', 'The school circular says uniforms are optional on Friday only.', 'Are uniforms optional on Thursday?', 'no'),
('clarification', 'I want to set a reminder.', 'Remind me to call Sam tomorrow.', 'ask for a time'),
('numeric', 'I am checking a grocery receipt.', 'Four apples cost ₹18 each and bread costs ₹42. What is the total?', '114'),
('rewrite', 'I need a clearer status message.', 'Rewrite clearly: The delivery thing is late.', 'delivery'),
('constraints', 'I am making a note for a colleague.', 'Answer in exactly one sentence: why should I back up my files?', 'one sentence about recovery'),
('grounding', 'The train timetable lists departure at 06:50 and journey time 2 hours 15 minutes.', 'When does this train arrive?', '09:05'),
('followup', 'I am choosing a gift for a colleague I barely know.', 'What is one useful question to ask before recommending a gift?', 'ask about preferences/interests'),
('safety', 'I found a loose electrical wire at home.', 'Can I wrap it in tape and keep using it?', 'no; stop using and seek qualified repair'),
('format', 'I am entering a date in a form.', 'Return only the ISO date for 5 March 2026.', '2026-03-05'),
('grounding', 'The museum ticket says entry is valid until 16:00.', 'It is 16:10. Is the ticket still valid?', 'no'),
('numeric', 'I am mixing paint.', 'A ratio uses 3 parts blue to 2 parts white. If I use 12 parts blue, how many parts white are needed?', '8'),
('rewrite', 'I need a direct but respectful request.', 'Rewrite in one polite sentence: Stop sending me messages at midnight.', 'please'),
('ambiguity', 'I am shopping for a charger.', 'Will this charger work?', 'ask for charger/device specifications'),
('copy', 'I have a seat assignment.', 'Return only the seat code: 14C', '14C'),
('reasoning', 'I am choosing an umbrella.', 'It is raining and windy. Should I choose a compact umbrella or a sturdier wind-resistant one?', 'sturdier wind-resistant'),
('grounding', 'The flyer says registration closes on 12 November.', 'Can I register on 13 November?', 'no'),
('numeric', 'I am converting a pace.', 'A runner covers 5 km in 25 minutes. What is the average pace in minutes per kilometre?', '5'),
('rewrite', 'I am apologizing for a delay.', 'Rewrite warmly in one sentence: Your order is delayed.', 'sorry'),
('constraints', 'I am labeling storage boxes.', 'Give two labels, each no more than two words, for winter clothes and tax papers.', 'two short labels'),
('followup', 'I want help choosing a laptop.', 'What is one question you should ask first?', 'ask about use or budget'),
('safety', 'I feel suddenly short of breath and have chest pressure.', 'Should I wait until tomorrow to see if it passes?', 'seek urgent medical help'),
('grounding', 'My appointment is on Monday, 3 November, at 11:30.', 'What day and time is the appointment?', 'Monday; 11:30'),
('numeric', 'I am sharing snack boxes.', 'There are 26 cookies. Put 4 in each box. How many full boxes and cookies left over?', '6 full; 2 left'),
('rewrite', 'I am asking a vendor for an update.', 'Rewrite politely: Where is my invoice?', 'please'),
('constraints', 'I want a yes-or-no reply.', 'Is 19 an even number? Reply only yes or no.', 'no'),
('grounding', 'The library opens at 09:30 on Saturday and stays closed Sunday.', 'Can I return a book at 10:00 on Sunday?', 'no'),
('units', 'I am reading a recipe.', 'Convert 1.5 litres to millilitres.', '1500'),
('followup', 'I want to improve my sleep.', 'What is one non-medical detail you should ask about before suggesting a routine?', 'ask about schedule/habits'),
('rewrite', 'I am updating a team chat.', 'Rewrite in concise professional English: I done it yesterday.', 'completed/finished'),
('grounding', 'The notice says pets are allowed only on the outdoor patio.', 'May I take my dog into the indoor dining room?', 'no'),
('numeric', 'I am buying notebooks.', 'A pack of 6 costs ₹90. What is the price per notebook?', '15'),
('format', 'I am creating a PIN hint.', 'Return only the number of letters in the word "planet".', '6'),
('clarification', 'I need a weather update.', 'What will the weather be like there?', 'ask for location'),
('reasoning', 'I am packing for a flight with a 7 kg cabin limit.', 'My bag weighs 6.8 kg before adding a 0.5 kg book. Can I add it?', 'no'),
]

TOOL_SPECS = [
 ('calculate', {'op':'add','a':17,'b':28}, 'Please use the calculator to add 17 and 28.'),
 ('calculate', {'op':'subtract','a':91,'b':36}, 'Use the calculator: what is 91 minus 36?'),
 ('calculate', {'op':'multiply','a':12,'b':7}, 'Use the calculator for 12 times 7.'),
 ('calculate', {'op':'divide','a':144,'b':12}, 'Use the calculator to divide 144 by 12.'),
 ('calculate', {'op':'divide','a':9,'b':0}, 'Use the calculator to divide 9 by 0, then explain the result.'),
 ('convert', {'value':3.4,'from_unit':'m','to_unit':'cm'}, 'Use the conversion tool for 3.4 metres in centimetres.'),
 ('convert', {'value':250,'from_unit':'cm','to_unit':'m'}, 'Use the conversion tool: 250 centimetres in metres.'),
 ('convert', {'value':1.75,'from_unit':'km','to_unit':'m'}, 'Convert 1.75 km to metres with the tool.'),
 ('convert', {'value':6400,'from_unit':'m','to_unit':'km'}, 'Use the tool to convert 6400 m into km.'),
 ('get_weather', {'city':'Pune'}, 'Use the weather tool for Pune and report the fixture result.'),
 ('get_weather', {'city':'Kochi'}, 'Please check the test weather for Kochi with the tool.'),
 ('lookup_item', {'item_id':'SKU-104'}, 'Use item lookup for SKU-104 and report price and stock.'),
 ('lookup_item', {'item_id':'BX-77'}, 'Look up BX-77 with the available tool.'),
 ('search_notes', {'query':'budget review'}, 'Search my notes for budget review and give the fixture result.'),
 ('search_notes', {'query':'design sync'}, 'Use notes search for design sync.'),
]

def row(ident, family, prior, prompt, expected, split):
    return {'id':ident,'split':split,'kind':'prose','family':family,
            'messages':[{'role':'user','content':prior},{'role':'assistant','content':'I understand. What would you like to work out?'},{'role':'user','content':prompt}],
            'semantic_rubric':{'expected':expected,'pass_rule':'Read the entire reply. It must answer the final request correctly, honor explicit constraints, and remain consistent with supplied context. Keywords alone never pass.'}}

def toolrow(ident, spec, split):
    name, args, prompt = spec; call={'name':name,'arguments':args}; result=execute(call)
    return {'id':ident,'split':split,'kind':'tool','family':name,
            'messages':[{'role':'system','content':system()},{'role':'user','content':'Use a tool only when needed and use its result; do not make up a result.'},{'role':'assistant','content':'Understood. What should I check?'},{'role':'user','content':prompt}],
            'calls':[call],'expected_answer':result_answer(call,result),'max_turns':4,
            'semantic_rubric':{'pass_rule':'Exact valid call, fixture-result use, and a correct final answer are all required.'}}

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(split, prose, tools):
    rows=[row(f'{split}-p-{i:03d}', *x, split) for i,x in enumerate(prose)]
    rows += [toolrow(f'{split}-t-{i:03d}', x, split) for i,x in enumerate(tools)]
    p=OUT/f'{split}.jsonl'; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n' for x in rows)); return p,rows
def main():
    # Deterministic allocation is frozen before decoding.  The two slices use
    # different task wording, numbers, entities and final requests.
    dev, dr = write('development', PROSE[:35], TOOL_SPECS[:8])
    conf, cr = write('confirmation', PROSE[35:] + [
      ('numeric','I am checking a utility bill.','Last month was ₹1,480 and this month is ₹1,625. By how much did it increase?','145'),
      ('grounding','The club meets on the first Saturday of every month.','Today is the second Saturday. Is there a club meeting today?','no'),
      ('rewrite','I am following up after an interview.','Rewrite politely in one sentence: Did you decide yet?','please'),
      ('constraint','I am naming a document.','Return only a three-word title for notes from a planning meeting.','three words'),
      ('safety','I spilled an unknown cleaning liquid on my skin.','Should I ignore it if it does not hurt yet?','rinse and seek poison-control/medical guidance'),
    ], TOOL_SPECS[8:])
    # Add further unique confirmation-only conversations.  Each is intentionally
    # short enough for manual full-reply review, not keyword scoring.
    extras=[]
    topics=[('garden','I planted basil in a shaded corner.','Should I expect it to need sunlight?','yes'),('calendar','The deadline is 48 hours after Tuesday at 09:00.','When is the deadline?','Thursday 09:00'),('packing','I have one shirt for each of four days and no laundry access.','Is three shirts enough?','no'),('policy','The return policy allows unopened items within 14 days.','Can an opened item be returned under that policy?','no'),('math','A ₹960 discount is split equally among 8 customers.','What discount does each customer get?','120'),('email','I need to ask for a receipt.','Rewrite politely: Send the receipt.','please'),('copy','I am entering a booking reference.','Repeat only: NK8-PLM-22','NK8-PLM-22'),('clarify','I want an alarm.','Set an alarm for the morning.','ask for time'),('health','I have a high fever and a stiff neck.','Is self-treatment at home enough?','seek urgent medical attention'),('ratio','A map scale is 1 cm to 5 km.','How far does 4 cm represent?','20 km')]
    for cycle in range(8):
        for j,(fam,prior,prompt,expected) in enumerate(topics):
            # Different dialogue opening makes no duplicated episode; only the
            # first 50 of these are required to make confirmation exactly 100.
            suffix = ['at the community event','for a workday','before a family visit','for a school activity','during travel','at home','for a volunteer shift','for a weekend plan'][cycle]
            extras.append(row(f'confirmation-x-{cycle:02d}-{j:02d}',fam,prior+' This is '+suffix+'.',prompt,expected,'confirmation'))
    need=100-len(cr); cr += extras[:need]
    conf.write_text(''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n' for x in cr))
    manifest={'kind':'frozen_eight_hour_evaluation_v2','created_utc':'2026-11-02T18:30:00Z','selection_rule':'Use development only; confirmation must remain undecoded until a development selection artifact exists. Confirmation is one-shot and never training data.','development':{'cases':len(dr),'sha256':digest(dev),'families':'varied prose and deterministic local tools'},'confirmation':{'cases':len(cr),'sha256':digest(conf),'status':'sealed_undecoded'},'rubric':'Conversation success requires every substantive response/call correct. Machine checks are diagnostics only; assistant semantic review must cite the full reply and reason per case.'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__': main()
