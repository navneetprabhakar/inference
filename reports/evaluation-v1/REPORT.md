# Pilot evaluation — 30 October 2026

**Decision: a bounded additional 200M-token pretraining experiment is justified; a long open-ended run is not. The current model is not a usable conversational assistant or tool caller. No further pretraining was launched.**

## Loss diagnostics

128 blocks and 65,536 next-token targets per set. Lower perplexity is better; it measures token prediction, not factual correctness or instruction following. The 5M model is a separate random-seed benchmark, not an earlier checkpoint of the 100M run.

| Set | 5M perplexity | 100M perplexity | 100M NLL |
|---|---:|---:|---:|
| fineweb_validation | 346.77 | 49.43 | 3.901 |
| tinystories_validation | 24.24 | 4.96 | 1.601 |
| tinystories_unseen_shard | 32.90 | 5.99 | 1.791 |
| wikipedia_untrained_source | 493.16 | 51.86 | 3.949 |
| fineweb_exposed_train | 319.65 | 41.01 | 3.714 |
| tinystories_exposed_train | 22.50 | 4.46 | 1.495 |

Validation blocks exclude the prefix repeatedly monitored during training. New story-shard and Wikipedia documents were checked against exact normalized text hashes in the entire pilot document index. Near-duplicates, passage overlap, and universal benchmark contamination were not ruled out. New-source sampling requires at least 513 tokens per document and therefore favors longer documents. Training diagnostics use blocks actually visited by the pilot sampler. The evaluated 262,144 held-out tokens plus 131,072 exposed-training tokens are modest diagnostics, not a general capability benchmark.

## What the generations show

- Simple narrative syntax is learned, but plot/state tracking fails: the lost-puppy story changes focus; the sun/ice-cube story never describes melting.
- Adult prose repeats generic phrases. The sunlight explanation becomes an incorrect claim about light bulbs.
- Greeting and grounded-question prompts drift into unrelated text or repetitions.
- Neither direct nor one-example weather prompts emit correct full JSON in either decoding mode: 0/4 tiny diagnostic cases, not a general tool accuracy estimate.
- Some structured prompts produce non-English byte-token loops. The original monitored validation was independently reproduced, and FP32 short-context/padded-context logits agree within 1.1e-5. BF16 near-ties can change the next token; all 12 prompts were therefore also repeated with original FP32 master weights. The repetition, grounding failures, and non-English structured-output loops remain.
- Changing from greedy to sampled decoding reduces some repeated wording, but does not restore factual correctness or task compliance.
- These are base-model outputs. No conversation or tool SFT has occurred; more prose pretraining alone cannot be assumed to teach the requested API protocol.

## Is more pretraining worth it?

Yes, as one capped experiment. Fresh-source loss improves substantially relative to the 5M run, and exposed-training vs validation gaps are modest (FineWeb about 0.187 nats/token, TinyStories about 0.106). That supports further language learning rather than a conclusion of pure memorization. It does not establish the future learning curve, especially because the 5M run used another seed.

Recommended next ceiling: 300M total tokens, meaning another 200M, approximately 22.7 training hours at the measured 2,445 tokens/sec, plus preparation/evaluation overhead. Add broader, nonduplicated English rather than simply looping the 130M-token prepared pool. Keep the tokenizer and architecture fixed for a meaningful continuation; preserve optimizer state and choose an explicit continuation learning-rate schedule. Check at 200M and 300M with a new reserved holdout plus this diagnostic suite. Do not treat the current 100M-capped runner as authorization or configuration for an extension.

Proceed beyond that only if plain-text continuations become materially less repetitive and more coherent, and held-out loss continues improving. Loss dropping while the same narrative/grounding failures persist is insufficient justification for weeks of training. A 1B-total-token target would add about 4.3 nonstop days from the current checkpoint; do not commit to that yet. Conversation and execution-verified tool SFT remain separate required stages.

## Main outputs (all 24 BF16 generations, unedited)

Fixed prompts, no best-of selection. Greedy or temperature 0.8/top-k 40; maximum 96 new tokens; no repetition penalty. EOF/EOS vs token limit is recorded in generations.json. Excerpts shown in chat are drawn from these outputs.

### story — greedy

Prompt:
```text
Once upon a time, a little girl found a lost puppy. She decided to
```

Output:
```text
 take him to the park to play.
At the park, the little girl saw a big tree. She wanted to climb it, but she was scared. She asked her mom, "Mom, can we climb the tree?" Her mom said, "Yes, let's go."
They went to the tree and started to climb. The little girl was so happy. She climbed the tree and climbed the tree. She was so happy to be home. She said, "
```
Stop: length; generated tokens: 96.

### story — sampled

Prompt:
```text
Once upon a time, a little girl found a lost puppy. She decided to
```

Output:
```text
 take him to the park to play. As they walked, she saw a big dog running towards her. The little girl was scared and ran away.
The little girl was so scared that she ran back home to her mom. But as she was walking, she discovered a big dog that was lost. She was so happy to have made a new friend and she hugged him tightly.
The little girl's mom noticed her crying and asked, "What's wrong, sweetie?"
```
Stop: length; generated tokens: 96.

### causal_story — greedy

Prompt:
```text
Tom put an ice cube in a bowl and left it in the sun. After an hour,
```

Output:
```text
 Tom went to play with his friends. They all had fun playing with the ice cube.
Tom's mom saw the ice cube and said, "Tom, you need to be careful with the ice cube. It is very hot and can hurt you." Tom nodded and promised to be more careful.
Tom and his friends played with the ice cube all day. They had so much fun that Tom forgot about the ice cube. When it was time to go home, Tom said
```
Stop: length; generated tokens: 96.

### causal_story — sampled

Prompt:
```text
Tom put an ice cube in a bowl and left it in the sun. After an hour,
```

Output:
```text
 Tom went outside and took a nap. He had so much fun that he forgot about his ice cube. From then on, Tom always had his favorite ice cube to go to the park.
```
Stop: eos; generated tokens: 38.

### explanation — greedy

Prompt:
```text
Plants need sunlight because
```

Output:
```text
 of the amount of sunlight they need.
The best way to get the most out of the sun is to use a light bulb. The light bulb is a good choice for the sun.
The best way to get the sun is to use a light bulb. The light bulb is a good choice for the sun.
The best way to get the sun is to use a light bulb. The light bulb is a good choice for the sun.
The best way to get
```
Stop: length; generated tokens: 96.

### explanation — sampled

Prompt:
```text
Plants need sunlight because
```

Output:
```text
 of its high humidity. The benefits of having a light bulb are great for the garden because they can affect different plants, plants and plants.
Hemp: The Sun
As a matter of fact, we have a lot of things to do with the sun. We can be sure the sun is the best for you in the future. You can also buy green light bulbs and plants in the event you buy your own.
Hemp: On the other hand,
```
Stop: length; generated tokens: 96.

### adult_prose — greedy

Prompt:
```text
When planning a project, it is important to identify the main risks. For example,
```

Output:
```text
 if you are planning a project, you should consider the following:
- The project should be designed to be a good place to start.
- The project should be designed to be a good place to start.
- The project should be designed to be a good place to start.
- The project should be designed to be a good place to start.
- The project should be designed to be a good place to start.
- The project should be designed to
```
Stop: length; generated tokens: 96.

### adult_prose — sampled

Prompt:
```text
When planning a project, it is important to identify the main risks. For example,
```

Output:
```text
 if a project needs to be set up properly, it is important to understand the specific risks and risks of a project that might include the risks and risks.
The POI and the POI Program
The POI was the first project in the world to be completed on the same day. It is the first project to be completed in the last five years.
The POI team was developed by a group of experts from the POI’s
```
Stop: length; generated tokens: 96.

### conversation — greedy

Prompt:
```text
User: Hi, how are you?
Assistant:
```

Output:
```text
 The first thing you need to know about the history of the United States is the history of the United States.
What is the history of the United States?
The history of the United States is the history of the United States. It is the history of the United States. It is the history of the United States. It is the history of the United States. It is the history of the United States. It is the history of the United States. It is the history
```
Stop: length; generated tokens: 96.

### conversation — sampled

Prompt:
```text
User: Hi, how are you?
Assistant:
```

Output:
```text
 The Venture of Stem Cells
Alexis: A Venture of Stem Cells
The Venture of Stem Cells is a series of different things that are most commonly used by the team. Firstly a team of researchers can help you understand how and why there are different types of cells within the mouse.
What are the different types of cells in the mouse?
The most common type of cells in the mouse is the cells
```
Stop: length; generated tokens: 96.

### instruction — greedy

Prompt:
```text
User: Give me three tips for staying organized at work.
Assistant:
```

Output:
```text
 Make sure you have a good time at work.
Discover the following tips for working with a job:
- Be aware of the importance of working with a job.
- Be aware of the importance of working with a job.
- Be aware of the importance of working with a job.
- Be aware of the importance of working with a job.
- Be aware of the importance of working with a job.
- Be aware of the importance of
```
Stop: length; generated tokens: 96.

### instruction — sampled

Prompt:
```text
User: Give me three tips for staying organized at work.
Assistant:
```

Output:
```text
 Have a team member with a particular learning degree who will be able to work around those problems.
Assistant: Use a team member with a few helpful resources to improve the skills they need to work effectively.
Assistant: Have a team member with a different learning level than in a group with a different learning level and a similar learning level.
Assistant: Allow each team member with a different learning level to complete the task.
Assistant: Have a team member
```
Stop: length; generated tokens: 96.

### grounded — greedy

Prompt:
```text
Context: Maya lives in Pune and works as a teacher.
Question: Where does Maya live?
Answer:
```

Output:
```text
 The term “pune” is used to describe the term “pune” in the English language.
Question: What is the name of the term “pune”?
Answer: The term “pune” is used to describe the term “pune” in the English language.
Question: What is the name of the term “pune”?
Answer: The term “pune” is used to describe the term “pune”
```
Stop: length; generated tokens: 96.

### grounded — sampled

Prompt:
```text
Context: Maya lives in Pune and works as a teacher.
Question: Where does Maya live?
Answer:
```

Output:
```text
 I am a student in the university and I am the one for a class. I am the one for a class and I am not a student. It is a student who does not need to write a text. I am an in-class student. I can hear the music, the music and the music. I am a student who works as a student, I am not a candidate in the school. I am a student in my university. I am not a student in
```
Stop: length; generated tokens: 96.

### arithmetic — greedy

Prompt:
```text
Question: What is 7 plus 5?
Answer:
```

Output:
```text
 What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
```
Stop: length; generated tokens: 96.

### arithmetic — sampled

Prompt:
```text
Question: What is 7 plus 5?
Answer:
```

Output:
```text
 1 is not the reason why the number of individuals do and how many people use the number of people in the number of people in the number of people in the number of people in the number of people in the number of people in the number of people in the number of people in the number of people in the number of people in the number of people in the number of people in the number of people in the number of people in the number of people in the number of people in
```
Stop: length; generated tokens: 96.

### clarification — greedy

Prompt:
```text
User: What is the weather like?
Assistant:
```

Output:
```text
 The weather is a great place to start.
Due to the weather, the weather is a great place to start. The weather is a great place to start.
Due to the weather, the weather is a great place to start. The weather is a great place to start.
Due to the weather, the weather is a great place to start. The weather is a great place to start.
Due to the weather, the weather is a great
```
Stop: length; generated tokens: 96.

### clarification — sampled

Prompt:
```text
User: What is the weather like?
Assistant:
```

Output:
```text
 The weather is different. The weather is different. The weather is different. The weather is different. The weather is different.
The weather is different. The weather is different.
The weather is different. The weather is different. The weather is different. The weather is different. The weather is different. The weather is different.
The weather is different. The weather is different. The weather is different. The weather is different.
The weather is different. The weather
```
Stop: length; generated tokens: 96.

### tool — greedy

Prompt:
```text
Available tool: get_weather(city: string). Return only JSON with name and arguments.
User: What is the weather in Bengaluru?
Assistant:
```

Output:
```text
 What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant:
```
Stop: length; generated tokens: 96.

### tool — sampled

Prompt:
```text
Available tool: get_weather(city: string). Return only JSON with name and arguments.
User: What is the weather in Bengaluru?
Assistant:
```

Output:
```text
 The weather in Bengaluru is based on the image from this image and the location of the storm to come of a few inches (or 7.9 inches) of water.
Rainwater: Raw crops such as kiwi, which are grown throughout the year and are grown in the state of Rakarabali.
Rainwater: Raw crops such as Rakarabali and Rakarabali, which are
```
Stop: length; generated tokens: 96.

### tool_example — greedy

Prompt:
```text
User: Weather in Mumbai?
Assistant: {"name":"get_weather","arguments":{"city":"Mumbai"}}
User: Weather in Pune?
Assistant:
```

Output:
```text
 글츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀�
```
Stop: length; generated tokens: 96.

### tool_example — sampled

Prompt:
```text
User: Weather in Mumbai?
Assistant: {"name":"get_weather","arguments":{"city":"Mumbai"}}
User: Weather in Pune?
Assistant:
```

Output:
```text
 apole_weather":"pages". www.cosmopellet.com/articles/gate-walls."fig"number="pages":"Sound"":"city":"explain"">
"Cameric - "Sound"":"Page":"<"">"> < "Akaric - "Page"":
```
Stop: length; generated tokens: 96.

### tool_result — greedy

Prompt:
```text
User: What is 7 plus 5?
Tool result: {"result":12}
Assistant:
```

Output:
```text
 "Tool result: 글츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀
```
Stop: length; generated tokens: 96.

### tool_result — sampled

Prompt:
```text
User: What is 7 plus 5?
Tool result: {"result":12}
Assistant:
```

Output:
```text
 C.J.R. C.S. (1994)
Tool 1: pended"received: 10.1212
Tool: "Schedule 1 - How to Saw 1"received: 10.1112
Tool: "Sleasure: 5.1111
Tool: "Saw 1"reckived: 10.31212
Tool: "Saw 1"reck
```
Stop: length; generated tokens: 96.

## FP32 verification outputs (all 12, unedited)

No sampling or repetition penalty; original master weights, greedy decoding. This checks the quality conclusion against low-precision rounding.

### story — FP32 greedy

Prompt:
```text
Once upon a time, a little girl found a lost puppy. She decided to
```

Output:
```text
 take him to the park to play.
At the park, the little girl saw a big tree. She wanted to climb it, but she was scared. She asked her mom, "Mom, can we climb the tree?" Her mom said, "Yes, let's go."
They went to the tree and started to climb. The little girl was so happy. She climbed the tree and climbed the tree. She was so happy to be home. She said, "
```

### causal_story — FP32 greedy

Prompt:
```text
Tom put an ice cube in a bowl and left it in the sun. After an hour,
```

Output:
```text
 Tom went to play with his friends. They all had fun playing with the ice cube.
Tom's mom saw the ice cube and said, "Tom, you need to be careful with the ice cube. It is very hot and can hurt you." Tom nodded and promised to be more careful.
Tom and his friends played with the ice cube all day. They had so much fun that Tom forgot about the ice cube. When it was time to go home, Tom said
```

### explanation — FP32 greedy

Prompt:
```text
Plants need sunlight because
```

Output:
```text
 of the amount of sunlight they need.
The best way to get the most out of the sun is to use a light bulb. The light bulb is a good choice for the sun. It is a good choice for the sun.
The best way to get the sun is to use a light bulb. The light bulb is a good choice for the sun. It is a good choice for the sun.
The best way to get the sun is to use a light bulb
```

### adult_prose — FP32 greedy

Prompt:
```text
When planning a project, it is important to identify the main risks. For example,
```

Output:
```text
 if you are planning a project, you should consider the following:
- The project should be designed to be a good place to start.
- The project should be designed to be a good place to start.
- The project should be designed to be a good place to start.
- The project should be designed to be a good place to start.
- The project should be designed to be a good place to start.
- The project should be designed to
```

### conversation — FP32 greedy

Prompt:
```text
User: Hi, how are you?
Assistant:
```

Output:
```text
 The first person to use the word “d” is the “d” and the second person to use the word “d” to describe the word “d” and the second person to use the word “d” to describe the word “d” and the third person to use the word “d” to describe the word “d” and the third person to use the word “d” to describe the word “d” and the third person to use the word “
```

### instruction — FP32 greedy

Prompt:
```text
User: Give me three tips for staying organized at work.
Assistant:
```

Output:
```text
 Make sure you have a good time at work.
Discover the following tips for working with a job:
- Be aware of the importance of working with a job.
- Be aware of the importance of working with a job.
- Be aware of the importance of working with a job.
- Be aware of the importance of working with a job.
- Be aware of the importance of working with a job.
- Be aware of the importance of
```

### grounded — FP32 greedy

Prompt:
```text
Context: Maya lives in Pune and works as a teacher.
Question: Where does Maya live?
Answer:
```

Output:
```text
 The term “pune” is used to describe the term “pune” in the English language.
Question: What is the name of the term “pune”?
Answer: The term “pune” is used to describe the term “pune” in the English language.
Question: What is the name of the term “pune”?
Answer: The term “pune” is used to describe the term “pune”
```

### arithmetic — FP32 greedy

Prompt:
```text
Question: What is 7 plus 5?
Answer:
```

Output:
```text
 What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
Answer: What is 7 plus 5?
```

### clarification — FP32 greedy

Prompt:
```text
User: What is the weather like?
Assistant:
```

Output:
```text
 The weather is a great place to start.
Due to the weather, the weather is a great place to start. The weather is a great place to start.
Due to the weather, the weather is a great place to start. The weather is a great place to start.
Due to the weather, the weather is a great place to start. The weather is a great place to start.
Due to the weather, the weather is a great
```

### tool — FP32 greedy

Prompt:
```text
Available tool: get_weather(city: string). Return only JSON with name and arguments.
User: What is the weather in Bengaluru?
Assistant:
```

Output:
```text
 What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant: What is the weather in Bengaluru?
Assistant:
```

### tool_example — FP32 greedy

Prompt:
```text
User: Weather in Mumbai?
Assistant: {"name":"get_weather","arguments":{"city":"Mumbai"}}
User: Weather in Pune?
Assistant:
```

Output:
```text
 글츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀�
```

### tool_result — FP32 greedy

Prompt:
```text
User: What is 7 plus 5?
Tool result: {"result":12}
Assistant:
```

Output:
```text
 "Tool result: 글츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀츀
```
