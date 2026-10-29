# Instruction inventory — review required

Primary-authored questions; first20 are training candidates, last4 are development-only.

## name

00 (train): Who owns the {item}? Return the complete name only.
01 (train): Give only the full name of the {item} owner.
02 (train): Which person is identified as owning the {item}? Use their full name and no other words.
03 (train): Extract the owner name for the {item}; include every part of the name, with no explanation.
04 (train): The question concerns ownership of the {item}. Answer with the full name alone.
05 (train): For the {item}, fill the owner field with just the complete name.
06 (train): Find the {item} owner in this record. Copy only their full name.
07 (train): I need the complete owner name for the {item}, not the other item. Write just that name.
08 (train): Identify the person to whom the {item} belongs. Respond solely with their full name.
09 (train): Whose {item} is it? Give the entire name without a sentence.
10 (train): Please read the ownership information and return only the full owner name for the {item}.
11 (train): Output the complete name attached to the {item}, without the item label.
12 (train): Answer this using the facts: who is the owner of the {item}? Full name only.
13 (train): Which full name should go beside the {item} in the owner list? Write nothing else.
14 (train): Use all parts of the listed name when naming the {item} owner. No extra text.
15 (train): Look up the person who owns the {item} in the supplied facts. Reply with their complete name alone.
16 (train): From the two belongings, select the {item} and write only its owner’s full name.
17 (train): Only the full owner name is needed. The belonging I am asking about is the {item}.
18 (train): Can you name the {item} owner exactly as listed? Reply with the name alone.
19 (train): Without summarizing the record, copy the entire name of whoever owns the {item}.
20 (development): For whom is ownership of the {item} recorded? Supply their full name by itself.
21 (development): Complete my lookup of the {item}: I need the owner’s given name and surname, and nothing more.
22 (development): Resolve the {item} ownership query with the full recorded name as your entire reply.
23 (development): Tell me whose name the {item} is registered under. Keep your response to the complete name.

## time

00 (train): What time is the meeting? Return HH:MM only.
01 (train): Copy the meeting time exactly, using HH:MM and no words.
02 (train): When does the meeting happen? Give only its stated time in HH:MM.
03 (train): Extract the meeting time. Your entire answer must be HH:MM.
04 (train): Fill the meeting-time field with just the recorded HH:MM value.
05 (train): I need the meeting time, not the delivery time. Reply only in HH:MM.
06 (train): Read the schedule and repeat only the exact meeting time.
07 (train): Which HH:MM belongs to the meeting? Return that value alone.
08 (train): Output the meeting’s hour and minute as HH:MM, without a sentence.
09 (train): Answer using the schedule: when is the meeting? Only HH:MM.
10 (train): Please identify the meeting time and write it without any surrounding words.
11 (train): The event I mean is the meeting. Give its exact time as HH:MM.
12 (train): Choose the time for the meeting from these facts. Keep only HH:MM.
13 (train): What should the meeting clock display read? State only the scheduled HH:MM.
14 (train): List no events; simply supply the meeting time in HH:MM.
15 (train): Use both the hour and minute from the meeting entry. Reply HH:MM only.
16 (train): For the meeting, transcribe the time with its colon and leading zero if present.
17 (train): Give a time-only answer to this question: when is the meeting scheduled?
18 (train): Locate the meeting in the supplied schedule. Return its HH:MM and nothing else.
19 (train): Without changing the stated time, tell me when the meeting is. Use HH:MM only.
20 (development): Which clock reading is assigned to the meeting rather than the other event? HH:MM only.
21 (development): Complete this lookup by returning the meeting’s exact hour:minute string.
22 (development): Identify the meeting appointment and report its time alone in HH:MM notation.
23 (development): I am checking the meeting entry. What is its time, written exactly as HH:MM?

## location

00 (train): Where is the {item}? Give the place name only.
01 (train): Name only the place holding the {item}.
02 (train): Find the {item} location in the facts. Reply with just the place.
03 (train): Which place is the {item} on? Return only that place name.
04 (train): Fill the location field for the {item} with the place alone.
05 (train): The object I need is the {item}. State its location as a place name, without a sentence.
06 (train): Extract just the location of the {item}.
07 (train): Look up where the {item} is and output only the place.
08 (train): Which listed place should I check for the {item}? Give its name alone.
09 (train): Answer with a place, not an object: where is the {item}?
10 (train): Please copy the place associated with the {item}, and nothing else.
11 (train): Tell me the {item} location in one place-name answer.
12 (train): Use these facts to locate the {item}. Reply only with the location name.
13 (train): For the {item}, what location is recorded? No extra words.
14 (train): I need only the place where the {item} sits, not where the other item sits.
15 (train): Return the location label for the {item}. Do not include the object name.
16 (train): Can you identify the place containing the {item}? Write just the place.
17 (train): From the locations mentioned, select the one for the {item}. Place name only.
18 (train): Which location matches the {item} entry? Supply that name by itself.
19 (train): Without describing the room, state the {item} place alone.
20 (development): Complete the location lookup for the {item} with only its place name.
21 (development): If I want the {item}, which recorded place should I go to? Name only the place.
22 (development): What is the destination of a search for the {item}, according to these facts? Place name only.
23 (development): Supply just the recorded whereabouts of the {item}, as a place name.

## distractor

00 (train): What color is the {item}? Give the color only.
01 (train): Name only the color of the {item}.
02 (train): Extract the {item} color, with no other text.
03 (train): Which color belongs to the {item} rather than the {other}? Return the color alone.
04 (train): Fill the color field for the {item}. Write only the color.
05 (train): The object I mean is the {item}. What color is it? One color only.
06 (train): Look at the {item} entry and copy just its color.
07 (train): Identify the color attached to the {item}. No explanation.
08 (train): Answer with a color, not an object: what color is the {item}?
09 (train): I am asking about the {item}, not the {other}. Give its color alone.
10 (train): Using the supplied facts, state only the {item} color.
11 (train): Which of the mentioned colors describes the {item}? Reply with that color.
12 (train): Return the color value for the {item} and omit the label.
13 (train): Please check the {item} and tell me its color without a sentence.
14 (train): Only one color is needed: the color of the {item}.
15 (train): Find the fact about the {item}; your answer should be its color alone.
16 (train): What color should be entered beside the {item}? Write nothing else.
17 (train): Choose the {item} from the two objects and output just its color.
18 (train): Do not summarize both objects. Give only the {item} color.
19 (train): Transcribe the stated color of the {item}, excluding all other details.
20 (development): For a color lookup of the {item}, which value does this record provide? Color only.
21 (development): Isolate the color assigned specifically to the {item}. Reply solely with that value.
22 (development): Which color entry matches the {item}? Supply that color as the whole response.
23 (development): Use the object name {item} to select the correct color. Give only that color.

## state

00 (train): What color is the {item} now? Color only.
01 (train): Give only the current color of the {item}.
02 (train): After the latest information, name the {item} color alone.
03 (train): Which color currently applies to the {item}? No extra text.
04 (train): Update the color lookup for the {item}. Return its current color only.
05 (train): I need the latest {item} color, not an earlier one. Color only.
06 (train): Using the current state, what color is the {item}? Reply with just the color.
07 (train): Report only the most recently stated color for the {item}.
08 (train): What color should the {item} record show at this point? Color only.
09 (train): Check the newest fact about the {item} and give its color alone.
10 (train): Which color is valid now for the {item}? Write only that color.
11 (train): State the {item} color after applying the updates. No sentence.
12 (train): Ignore superseded colors and return only the current {item} color.
13 (train): Tell me the latest known color of the {item}, with no other words.
14 (train): For the {item}, replace any stale value with the current color in your answer.
15 (train): What is the {item} color at the end of the updates so far? Color only.
16 (train): Read the updates in order; answer only with the {item} color that remains current.
17 (train): The query is the current color of the {item}. Give just that value.
18 (train): Keep the latest change in mind and name only the {item} color.
19 (train): Return the current color field for the {item}, without history or explanation.
20 (development): Which color survives the latest correction for the {item}? Color alone.
21 (development): At this stage of the conversation, what color applies to the {item}? Color only.
22 (development): Resolve the update history into one current {item} color. Give only the color.
23 (development): With all changes applied, supply the {item} color as your entire answer.

## missing

00 (train): Who owns the {item}? Give the full name only, or say Unknown if it is not supplied.
01 (train): Return the {item} owner’s full name. If the record omits it, reply Unknown.
02 (train): Find the complete owner name for the {item}; use Unknown when absent. No other text.
03 (train): Is an owner named for the {item}? Reply with their full name if so, otherwise Unknown.
04 (train): Fill the {item} owner field from these facts, using Unknown for a missing name.
05 (train): Name the {item} owner without guessing. Full name only, or Unknown.
06 (train): The lookup concerns the {item}. Return its full owner name or Unknown if unavailable.
07 (train): Extract only the supplied owner name of the {item}. If none is given, write Unknown.
08 (train): What owner is recorded for the {item}? Use the complete name, or Unknown if missing.
09 (train): Use the evidence to identify the {item} owner. Full name alone; Unknown if not stated.
10 (train): Can this record name the {item} owner? Answer with the full name or Unknown only.
11 (train): Without borrowing the other item’s owner, give the {item} owner name or Unknown.
12 (train): For the {item}, copy the entire owner name if present; if not, output Unknown.
13 (train): Reply solely with the {item} owner’s complete name when supplied, else Unknown.
14 (train): Which person owns the {item} according to the record? Full name or Unknown only.
15 (train): Check whether ownership of the {item} is specified. Give the full name or Unknown.
16 (train): I need a supported owner value for the {item}: the full name, or Unknown if absent.
17 (train): Complete the owner lookup for the {item} without inference. Use Unknown for missing data.
18 (train): Only the {item} owner is requested. Write the complete supplied name or Unknown.
19 (train): Do these facts provide a full owner name for the {item}? Return it or Unknown, with no explanation.
20 (development): Populate ownership for the {item} using its recorded full name; leave it as Unknown if unrecorded.
21 (development): Who is explicitly identified as the {item} owner? Entire name only; Unknown if no one is identified.
22 (development): Distinguish missing ownership from the other facts. Answer with the {item} full owner name or Unknown.
23 (development): For this {item}, return an evidence-backed full owner name, or the literal word Unknown.

## clarification

00 (train): I need a reminder for the meeting. Ask for the missing {slot}.
01 (train): Please help complete a meeting reminder by asking what {slot} is missing.
02 (train): The reminder is incomplete. Ask me for the meeting {slot}.
03 (train): Before writing my meeting reminder, ask a question to obtain its {slot}.
04 (train): We lack the meeting {slot}. Ask me for that detail.
05 (train): Help me finish this reminder: first ask for the meeting {slot}.
06 (train): What should you ask to learn the meeting {slot}? Ask that question now.
07 (train): Do not invent the meeting {slot}. Request it from me as a question.
08 (train): To write the reminder you still need the meeting {slot}. Please ask for it.
09 (train): Ask one question that obtains the missing meeting {slot}.
10 (train): Can you request the meeting {slot} so the reminder can be completed?
11 (train): The next step is to learn the meeting {slot}; ask me directly.
12 (train): I have not supplied the meeting {slot}. Ask for it before writing a reminder.
13 (train): Which question would get the missing meeting {slot}? Use it as your reply.
14 (train): Pause the reminder and ask me to specify the meeting {slot}.
15 (train): Please seek clarification about the meeting {slot} only.
16 (train): You need the meeting {slot} for the reminder. Form a direct question asking for it.
17 (train): Let us fill the missing detail: ask what the meeting {slot} is.
18 (train): Request the meeting {slot} rather than choosing one yourself.
19 (train): Start by asking for the missing meeting {slot}; do not write the reminder yet.
20 (development): Obtain the absent meeting {slot} with a focused question.
21 (development): What question must I answer to supply the meeting {slot}? Ask it.
22 (development): Before completing this notice, have me provide the meeting {slot} by asking directly.
23 (development): Clarify just the meeting {slot} that has not yet been provided.

## format

00 (train): What color is the {item}? {style}
01 (train): Report the color of the {item}. {style}
02 (train): Find the {item} color in the facts. {style}
03 (train): Which color describes the {item}? {style}
04 (train): Please answer the color question for the {item}. {style}
05 (train): Use the supplied record to tell me the {item} color. {style}
06 (train): The object I am asking about is the {item}; give its color. {style}
07 (train): Identify the color associated with the {item}. {style}
08 (train): Copy the color information for the {item}. {style}
09 (train): Can you tell me what color the {item} is? {style}
10 (train): Look up the {item} and report its color. {style}
11 (train): I need a color answer about the {item}. {style}
12 (train): Extract the fact about the {item} color. {style}
13 (train): Use the {item} entry to answer its color query. {style}
14 (train): Choose the color for the {item} from the record. {style}
15 (train): Only the {item} color is relevant to my question. {style}
16 (train): Give the color specified for the {item}. {style}
17 (train): Answer using the color fact attached to the {item}. {style}
18 (train): Tell me the {item} color without adding unrelated facts. {style}
19 (train): Check what the record says about the {item} color. {style}
20 (development): Produce the requested color description for the {item}. {style}
21 (development): How does the record characterize the {item} by color? {style}
22 (development): Resolve my question about the {item} color. {style}
23 (development): From these facts, give the color description belonging to the {item}. {style}
