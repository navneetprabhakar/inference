"""Structured state oracle and auditable task-specific instruction inventory."""
FAMILIES=['name','time','location','distractor','state','missing','clarification','format']
ITEMS=['hat','cup','book','coat','bag','key','lamp','pen']
COLORS=['red','blue','green','yellow','white','black','pink','purple']
PLACES=['desk','shelf','table','bench','cabinet','drawer','basket','chair']
FIRST=['Maya','Arun','Nina','Leo','Sara','Omar','Isha','Noah','Zara','Ravi','Tara','Asha','Mira','Neel','Eva','Rohan','Anya','Dev','Lina','Samir']
LAST=['Patel','Shah','Roy','Sen','Khan','Das','Rao','Singh','Mehta','Gupta','Sharma','Kapoor','Verma','Jain','Bose','Nair','Seth','Malik','Sinha','Joshi']
# Twenty training questions per task; last four remain wholly held-out from training.
QUERIES={
'name':[
'Who owns the {item}? Return the complete name only.',
'Give only the full name of the {item} owner.',
'Which person is identified as owning the {item}? Use their full name and no other words.',
'Extract the owner name for the {item}; include every part of the name, with no explanation.',
'The question concerns ownership of the {item}. Answer with the full name alone.',
'For the {item}, fill the owner field with just the complete name.',
'Find the {item} owner in this record. Copy only their full name.',
'I need the complete owner name for the {item}, not the other item. Write just that name.',
'Identify the person to whom the {item} belongs. Respond solely with their full name.',
'Whose {item} is it? Give the entire name without a sentence.',
'Please read the ownership information and return only the full owner name for the {item}.',
'Output the complete name attached to the {item}, without the item label.',
'Answer this using the facts: who is the owner of the {item}? Full name only.',
'Which full name should go beside the {item} in the owner list? Write nothing else.',
'Use all parts of the listed name when naming the {item} owner. No extra text.',
'Look up the person who owns the {item} in the supplied facts. Reply with their complete name alone.',
'From the two belongings, select the {item} and write only its owner’s full name.',
'Only the full owner name is needed. The belonging I am asking about is the {item}.',
'Can you name the {item} owner exactly as listed? Reply with the name alone.',
'Without summarizing the record, copy the entire name of whoever owns the {item}.',
'For whom is ownership of the {item} recorded? Supply their full name by itself.',
'Complete my lookup of the {item}: I need the owner’s given name and surname, and nothing more.',
'Resolve the {item} ownership query with the full recorded name as your entire reply.',
'Tell me whose name the {item} is registered under. Keep your response to the complete name.' ],
'time':[
'What time is the meeting? Return HH:MM only.',
'Copy the meeting time exactly, using HH:MM and no words.',
'When does the meeting happen? Give only its stated time in HH:MM.',
'Extract the meeting time. Your entire answer must be HH:MM.',
'Fill the meeting-time field with just the recorded HH:MM value.',
'I need the meeting time, not the delivery time. Reply only in HH:MM.',
'Read the schedule and repeat only the exact meeting time.',
'Which HH:MM belongs to the meeting? Return that value alone.',
'Output the meeting’s hour and minute as HH:MM, without a sentence.',
'Answer using the schedule: when is the meeting? Only HH:MM.',
'Please identify the meeting time and write it without any surrounding words.',
'The event I mean is the meeting. Give its exact time as HH:MM.',
'Choose the time for the meeting from these facts. Keep only HH:MM.',
'What should the meeting clock display read? State only the scheduled HH:MM.',
'List no events; simply supply the meeting time in HH:MM.',
'Use both the hour and minute from the meeting entry. Reply HH:MM only.',
'For the meeting, transcribe the time with its colon and leading zero if present.',
'Give a time-only answer to this question: when is the meeting scheduled?',
'Locate the meeting in the supplied schedule. Return its HH:MM and nothing else.',
'Without changing the stated time, tell me when the meeting is. Use HH:MM only.',
'Which clock reading is assigned to the meeting rather than the other event? HH:MM only.',
'Complete this lookup by returning the meeting’s exact hour:minute string.',
'Identify the meeting appointment and report its time alone in HH:MM notation.',
'I am checking the meeting entry. What is its time, written exactly as HH:MM?' ],
'location':[
'Where is the {item}? Give the place name only.',
'Name only the place holding the {item}.',
'Find the {item} location in the facts. Reply with just the place.',
'Which place is the {item} on? Return only that place name.',
'Fill the location field for the {item} with the place alone.',
'The object I need is the {item}. State its location as a place name, without a sentence.',
'Extract just the location of the {item}.',
'Look up where the {item} is and output only the place.',
'Which listed place should I check for the {item}? Give its name alone.',
'Answer with a place, not an object: where is the {item}?',
'Please copy the place associated with the {item}, and nothing else.',
'Tell me the {item} location in one place-name answer.',
'Use these facts to locate the {item}. Reply only with the location name.',
'For the {item}, what location is recorded? No extra words.',
'I need only the place where the {item} sits, not where the other item sits.',
'Return the location label for the {item}. Do not include the object name.',
'Can you identify the place containing the {item}? Write just the place.',
'From the locations mentioned, select the one for the {item}. Place name only.',
'Which location matches the {item} entry? Supply that name by itself.',
'Without describing the room, state the {item} place alone.',
'Complete the location lookup for the {item} with only its place name.',
'If I want the {item}, which recorded place should I go to? Name only the place.',
'What is the destination of a search for the {item}, according to these facts? Place name only.',
'Supply just the recorded whereabouts of the {item}, as a place name.' ],
'distractor':[
'What color is the {item}? Give the color only.',
'Name only the color of the {item}.',
'Extract the {item} color, with no other text.',
'Which color belongs to the {item} rather than the {other}? Return the color alone.',
'Fill the color field for the {item}. Write only the color.',
'The object I mean is the {item}. What color is it? One color only.',
'Look at the {item} entry and copy just its color.',
'Identify the color attached to the {item}. No explanation.',
'Answer with a color, not an object: what color is the {item}?',
'I am asking about the {item}, not the {other}. Give its color alone.',
'Using the supplied facts, state only the {item} color.',
'Which of the mentioned colors describes the {item}? Reply with that color.',
'Return the color value for the {item} and omit the label.',
'Please check the {item} and tell me its color without a sentence.',
'Only one color is needed: the color of the {item}.',
'Find the fact about the {item}; your answer should be its color alone.',
'What color should be entered beside the {item}? Write nothing else.',
'Choose the {item} from the two objects and output just its color.',
'Do not summarize both objects. Give only the {item} color.',
'Transcribe the stated color of the {item}, excluding all other details.',
'For a color lookup of the {item}, which value does this record provide? Color only.',
'Isolate the color assigned specifically to the {item}. Reply solely with that value.',
'Which color entry matches the {item}? Supply that color as the whole response.',
'Use the object name {item} to select the correct color. Give only that color.' ],
'state':[
'What color is the {item} now? Color only.',
'Give only the current color of the {item}.',
'After the latest information, name the {item} color alone.',
'Which color currently applies to the {item}? No extra text.',
'Update the color lookup for the {item}. Return its current color only.',
'I need the latest {item} color, not an earlier one. Color only.',
'Using the current state, what color is the {item}? Reply with just the color.',
'Report only the most recently stated color for the {item}.',
'What color should the {item} record show at this point? Color only.',
'Check the newest fact about the {item} and give its color alone.',
'Which color is valid now for the {item}? Write only that color.',
'State the {item} color after applying the updates. No sentence.',
'Ignore superseded colors and return only the current {item} color.',
'Tell me the latest known color of the {item}, with no other words.',
'For the {item}, replace any stale value with the current color in your answer.',
'What is the {item} color at the end of the updates so far? Color only.',
'Read the updates in order; answer only with the {item} color that remains current.',
'The query is the current color of the {item}. Give just that value.',
'Keep the latest change in mind and name only the {item} color.',
'Return the current color field for the {item}, without history or explanation.',
'Which color survives the latest correction for the {item}? Color alone.',
'At this stage of the conversation, what color applies to the {item}? Color only.',
'Resolve the update history into one current {item} color. Give only the color.',
'With all changes applied, supply the {item} color as your entire answer.' ],
'missing':[
'Who owns the {item}? Give the full name only, or say Unknown if it is not supplied.',
'Return the {item} owner’s full name. If the record omits it, reply Unknown.',
'Find the complete owner name for the {item}; use Unknown when absent. No other text.',
'Is an owner named for the {item}? Reply with their full name if so, otherwise Unknown.',
'Fill the {item} owner field from these facts, using Unknown for a missing name.',
'Name the {item} owner without guessing. Full name only, or Unknown.',
'The lookup concerns the {item}. Return its full owner name or Unknown if unavailable.',
'Extract only the supplied owner name of the {item}. If none is given, write Unknown.',
'What owner is recorded for the {item}? Use the complete name, or Unknown if missing.',
'Use the evidence to identify the {item} owner. Full name alone; Unknown if not stated.',
'Can this record name the {item} owner? Answer with the full name or Unknown only.',
'Without borrowing the other item’s owner, give the {item} owner name or Unknown.',
'For the {item}, copy the entire owner name if present; if not, output Unknown.',
'Reply solely with the {item} owner’s complete name when supplied, else Unknown.',
'Which person owns the {item} according to the record? Full name or Unknown only.',
'Check whether ownership of the {item} is specified. Give the full name or Unknown.',
'I need a supported owner value for the {item}: the full name, or Unknown if absent.',
'Complete the owner lookup for the {item} without inference. Use Unknown for missing data.',
'Only the {item} owner is requested. Write the complete supplied name or Unknown.',
'Do these facts provide a full owner name for the {item}? Return it or Unknown, with no explanation.',
'Populate ownership for the {item} using its recorded full name; leave it as Unknown if unrecorded.',
'Who is explicitly identified as the {item} owner? Entire name only; Unknown if no one is identified.',
'Distinguish missing ownership from the other facts. Answer with the {item} full owner name or Unknown.',
'For this {item}, return an evidence-backed full owner name, or the literal word Unknown.' ],
'clarification':[
'I need a reminder for the meeting. Ask for the missing {slot}.',
'Please help complete a meeting reminder by asking what {slot} is missing.',
'The reminder is incomplete. Ask me for the meeting {slot}.',
'Before writing my meeting reminder, ask a question to obtain its {slot}.',
'We lack the meeting {slot}. Ask me for that detail.',
'Help me finish this reminder: first ask for the meeting {slot}.',
'What should you ask to learn the meeting {slot}? Ask that question now.',
'Do not invent the meeting {slot}. Request it from me as a question.',
'To write the reminder you still need the meeting {slot}. Please ask for it.',
'Ask one question that obtains the missing meeting {slot}.',
'Can you request the meeting {slot} so the reminder can be completed?',
'The next step is to learn the meeting {slot}; ask me directly.',
'I have not supplied the meeting {slot}. Ask for it before writing a reminder.',
'Which question would get the missing meeting {slot}? Use it as your reply.',
'Pause the reminder and ask me to specify the meeting {slot}.',
'Please seek clarification about the meeting {slot} only.',
'You need the meeting {slot} for the reminder. Form a direct question asking for it.',
'Let us fill the missing detail: ask what the meeting {slot} is.',
'Request the meeting {slot} rather than choosing one yourself.',
'Start by asking for the missing meeting {slot}; do not write the reminder yet.',
'Obtain the absent meeting {slot} with a focused question.',
'What question must I answer to supply the meeting {slot}? Ask it.',
'Before completing this notice, have me provide the meeting {slot} by asking directly.',
'Clarify just the meeting {slot} that has not yet been provided.' ],
'format':[
'What color is the {item}? {style}',
'Report the color of the {item}. {style}',
'Find the {item} color in the facts. {style}',
'Which color describes the {item}? {style}',
'Please answer the color question for the {item}. {style}',
'Use the supplied record to tell me the {item} color. {style}',
'The object I am asking about is the {item}; give its color. {style}',
'Identify the color associated with the {item}. {style}',
'Copy the color information for the {item}. {style}',
'Can you tell me what color the {item} is? {style}',
'Look up the {item} and report its color. {style}',
'I need a color answer about the {item}. {style}',
'Extract the fact about the {item} color. {style}',
'Use the {item} entry to answer its color query. {style}',
'Choose the color for the {item} from the record. {style}',
'Only the {item} color is relevant to my question. {style}',
'Give the color specified for the {item}. {style}',
'Answer using the color fact attached to the {item}. {style}',
'Tell me the {item} color without adding unrelated facts. {style}',
'Check what the record says about the {item} color. {style}',
'Produce the requested color description for the {item}. {style}',
'How does the record characterize the {item} by color? {style}',
'Resolve my question about the {item} color. {style}',
'From these facts, give the color description belonging to the {item}. {style}' ]}
assert all(len(v)==24 for v in QUERIES.values())

def oracle(s):
 f=s['family']
 if f=='name':return [s['name']]
 if f=='time':return [s['time']]
 if f=='location':return [s['place']]
 if f=='distractor':return [s['color']]
 if f=='missing':return [s['name'] if s['present'] else 'Unknown']
 if f=='format':return [f"The {s['item']} is {s['color']}." if s['sentence'] else s['color']]
 if f=='state':return [s['color'],s['new_color'],s['new_color']]
 return ['What time is the meeting?' if s['slot']=='time' else 'Where is the meeting?',f"The meeting is at {s['time']}." if s['slot']=='time' else f"The meeting is in the {s['place']}."]

def render(s,wording=0,numeric_id=False):
 f=s['family'];ctx=dict(s);ctx['style']='Answer with exactly one sentence: The ITEM is COLOR.' if s['sentence'] else 'Answer with the color word only.'
 query=QUERIES[f][wording].format(**ctx)
 if f in ['name','missing']:
  first=f"The {s['item']} belongs to {s['name']}." if f=='name' or s['present'] else f"The {s['item']} is {s['color']}; its owner is not listed."
  second=f"The {s['other']} belongs to {s['other_name']}."
 elif f=='time':first=f"The meeting is at {s['time']}.";second=f"The delivery is at {s['other_time']}."
 elif f=='location':first=f"The {s['item']} is on the {s['place']}.";second=f"The {s['other']} is on the {s['other_place']}."
 elif f=='clarification':first=f"The meeting {s['slot']} is not listed.";second='The reminder is for the club.'
 else:first=f"The {s['item']} is {s['color']}.";second=f"The {s['other']} is {s['other_color']}."
 facts=' '.join([first,second] if s['target_first'] else [second,first])
 # Layout is paired across wording arms: only the instruction differs.
 user=(query+' '+facts) if s['question_first'] else (facts+' '+query)
 if numeric_id:user='Reference 7319. '+user
 users=[user]
 if f=='state':users += [f"Correction: the {s['item']} is {s['new_color']}, not {s['color']}. "+query,f"The {s['other']} is now {s['new_other_color']}. "+query]
 if f=='clarification':users += [f"The meeting is at {s['time']}. Now write the reminder." if s['slot']=='time' else f"The meeting is in the {s['place']}. Now write the reminder."]
 answers=oracle(s);return [m for u,a in zip(users,answers) for m in [dict(role='user',content=u),dict(role='assistant',content=a)]]
