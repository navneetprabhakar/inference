# Semantic review packet

Unreviewed candidate. Check fact/reference consistency, ambiguity, missingness, state updates and both sides of each pair. This selection is illustrative, not a random estimate of corpus quality. No author quality ratings are supplied.

## clarification-033-before — view 0

**user:** Which question would get the missing meeting time? Use it as your reply. Meeting time: not supplied. Meeting place: not supplied.

**assistant:** What time is the meeting?

**user:** The meeting is at 00:33. Now write the reminder.

**assistant:** The meeting is at 00:33.

## clarification-033-after — view 0

**user:** Which question would get the missing meeting time? Use it as your reply. Meeting time: not supplied. Meeting place: not supplied.

**assistant:** What time is the meeting?

**user:** The meeting is at 09:04. Now write the reminder.

**assistant:** The meeting is at 09:04.

## clarification-176-before — view 1

**user:** Meeting time: not supplied. Meeting place: not supplied. Before writing my meeting reminder, ask a question to obtain its time.

**assistant:** What time is the meeting?

**user:** The meeting is at 02:56. Now write the reminder.

**assistant:** The meeting is at 02:56.

## clarification-176-after — view 1

**user:** Meeting time: not supplied. Meeting place: not supplied. Before writing my meeting reminder, ask a question to obtain its time.

**assistant:** What time is the meeting?

**user:** The meeting is at 11:27. Now write the reminder.

**assistant:** The meeting is at 11:27.

## distractor-033-before — view 0

**user:** Please check the scarf and tell me its color without a sentence. lantern: black; owner Isaac Foster; on the drawer. scarf: white; owner Bruno Carver; on the cabinet. Meeting: 00:33. Delivery: 11:50.

**assistant:** white

## distractor-033-after — view 0

**user:** Please check the scarf and tell me its color without a sentence. lantern: black; owner Isaac Foster; on the drawer. scarf: black; owner Bruno Carver; on the cabinet. Meeting: 00:33. Delivery: 11:50.

**assistant:** black

## distractor-176-before — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is pink, with owner Alice Lane, on the cabinet. The meeting is at 02:56; delivery is at 13:13. Which color belongs to the scarf rather than the suitcase? Return the color alone.

**assistant:** pink

## distractor-176-after — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is blue, with owner Alice Lane, on the cabinet. The meeting is at 02:56; delivery is at 13:13. Which color belongs to the scarf rather than the suitcase? Return the color alone.

**assistant:** blue

## format-033-before — view 0

**user:** Use the scarf entry to answer its color query. Answer with the color word only. lantern: black; owner Isaac Foster; on the drawer. scarf: white; owner Bruno Carver; on the cabinet. Meeting: 00:33. Delivery: 11:50.

**assistant:** white

## format-033-after — view 0

**user:** Use the scarf entry to answer its color query. Answer with the color word only. lantern: black; owner Isaac Foster; on the drawer. scarf: black; owner Bruno Carver; on the cabinet. Meeting: 00:33. Delivery: 11:50.

**assistant:** black

## format-176-before — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is pink, with owner Alice Lane, on the cabinet. The meeting is at 02:56; delivery is at 13:13. Which color describes the scarf? Answer with exactly one sentence: The ITEM is COLOR.

**assistant:** The scarf is pink.

## format-176-after — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is blue, with owner Alice Lane, on the cabinet. The meeting is at 02:56; delivery is at 13:13. Which color describes the scarf? Answer with exactly one sentence: The ITEM is COLOR.

**assistant:** The scarf is blue.

## location-033-before — view 0

**user:** For the scarf, what location is recorded? No extra words. lantern: black; owner Isaac Foster; on the drawer. scarf: white; owner Bruno Carver; on the cabinet. Meeting: 00:33. Delivery: 11:50.

**assistant:** cabinet

## location-033-after — view 0

**user:** For the scarf, what location is recorded? No extra words. lantern: black; owner Isaac Foster; on the drawer. scarf: white; owner Bruno Carver; on the drawer. Meeting: 00:33. Delivery: 11:50.

**assistant:** drawer

## location-176-before — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is pink, with owner Alice Lane, on the cabinet. The meeting is at 02:56; delivery is at 13:13. Which place is the scarf on? Return only that place name.

**assistant:** cabinet

## location-176-after — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is pink, with owner Alice Lane, on the chair. The meeting is at 02:56; delivery is at 13:13. Which place is the scarf on? Return only that place name.

**assistant:** chair

## missing-033-before — view 0

**user:** Reply solely with the scarf owner’s complete name when supplied, else Unknown. lantern: black; owner Isaac Foster; on the drawer. scarf: white; owner not supplied; on the cabinet. Meeting: 00:33. Delivery: 11:50.

**assistant:** Unknown

## missing-033-after — view 0

**user:** Reply solely with the scarf owner’s complete name when supplied, else Unknown. lantern: black; owner Isaac Foster; on the drawer. scarf: white; owner Bruno Carver; on the cabinet. Meeting: 00:33. Delivery: 11:50.

**assistant:** Bruno Carver

## missing-176-before — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is pink, with owner not supplied, on the cabinet. The meeting is at 02:56; delivery is at 13:13. Is an owner named for the scarf? Reply with their full name if so, otherwise Unknown.

**assistant:** Unknown

## missing-176-after — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is pink, with owner Alice Lane, on the cabinet. The meeting is at 02:56; delivery is at 13:13. Is an owner named for the scarf? Reply with their full name if so, otherwise Unknown.

**assistant:** Alice Lane

## name-033-before — view 0

**user:** Which full name should go beside the scarf in the owner list? Write nothing else. lantern: black; owner Isaac Foster; on the drawer. scarf: white; owner Bruno Carver; on the cabinet. Meeting: 00:33. Delivery: 11:50.

**assistant:** Bruno Carver

## name-033-after — view 0

**user:** Which full name should go beside the scarf in the owner list? Write nothing else. lantern: black; owner Isaac Foster; on the drawer. scarf: white; owner Gavin Jensen; on the cabinet. Meeting: 00:33. Delivery: 11:50.

**assistant:** Gavin Jensen

## name-176-before — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is pink, with owner Alice Lane, on the cabinet. The meeting is at 02:56; delivery is at 13:13. Extract the owner name for the scarf; include every part of the name, with no explanation.

**assistant:** Alice Lane

## name-176-after — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is pink, with owner Freya Carver, on the cabinet. The meeting is at 02:56; delivery is at 13:13. Extract the owner name for the scarf; include every part of the name, with no explanation.

**assistant:** Freya Carver

## state-033-before — view 0

**user:** Tell me the latest known color of the scarf, with no other words. lantern: black; owner Isaac Foster; on the drawer. scarf: white; owner Bruno Carver; on the cabinet. Meeting: 00:33. Delivery: 11:50.

**assistant:** white

**user:** Correction: the scarf is purple, not white. What color is the scarf now?

**assistant:** purple

**user:** The lantern is now purple. What color is the scarf now?

**assistant:** purple

## state-033-after — view 0

**user:** Tell me the latest known color of the scarf, with no other words. lantern: black; owner Isaac Foster; on the drawer. scarf: purple; owner Bruno Carver; on the cabinet. Meeting: 00:33. Delivery: 11:50.

**assistant:** purple

**user:** Correction: the scarf is white, not purple. What color is the scarf now?

**assistant:** white

**user:** The lantern is now purple. What color is the scarf now?

**assistant:** white

## state-176-before — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is pink, with owner Alice Lane, on the cabinet. The meeting is at 02:56; delivery is at 13:13. Which color currently applies to the scarf? No extra text.

**assistant:** pink

**user:** Correction: the scarf is blue, not pink. What color is the scarf now?

**assistant:** blue

**user:** The suitcase is now blue. What color is the scarf now?

**assistant:** blue

## state-176-after — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is blue, with owner Alice Lane, on the cabinet. The meeting is at 02:56; delivery is at 13:13. Which color currently applies to the scarf? No extra text.

**assistant:** blue

**user:** Correction: the scarf is pink, not blue. What color is the scarf now?

**assistant:** pink

**user:** The suitcase is now blue. What color is the scarf now?

**assistant:** pink

## time-033-before — view 0

**user:** What should the meeting clock display read? State only the scheduled HH:MM. lantern: black; owner Isaac Foster; on the drawer. scarf: white; owner Bruno Carver; on the cabinet. Meeting: 00:33. Delivery: 11:50.

**assistant:** 00:33

## time-033-after — view 0

**user:** What should the meeting clock display read? State only the scheduled HH:MM. lantern: black; owner Isaac Foster; on the drawer. scarf: white; owner Bruno Carver; on the cabinet. Meeting: 06:56. Delivery: 11:50.

**assistant:** 06:56

## time-176-before — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is pink, with owner Alice Lane, on the cabinet. The meeting is at 02:56; delivery is at 13:13. Extract the meeting time. Your entire answer must be HH:MM.

**assistant:** 02:56

## time-176-after — view 1

**user:** The suitcase is white, with owner Hazel Orton, on the drawer. The scarf is pink, with owner Alice Lane, on the cabinet. The meeting is at 08:19; delivery is at 13:13. Extract the meeting time. Your entire answer must be HH:MM.

**assistant:** 08:19

