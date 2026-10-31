# 100M-token evaluation

Same frozen sets and prompts across 100M/200M/300M. Legacy Wikipedia is now a held-out subset of a trained source, not an unseen domain. Loss and tiny prompt suite are diagnostic, not general capability benchmarks.

| Set | 100M perplexity | Current perplexity |
|---|---:|---:|
| legacy_fineweb_validation | 49.43 | 49.43 |
| legacy_tinystories_validation | 4.96 | 4.96 |
| legacy_tinystories_unseen_shard | 5.99 | 5.99 |
| legacy_wikipedia_untrained_source | 51.86 | 51.86 |
| legacy_fineweb_exposed_train | 41.01 | 41.01 |
| legacy_tinystories_exposed_train | 4.46 | 4.46 |
| new_fineweb | 45.10 | 45.10 |
| new_wikipedia | 50.03 | 50.03 |
| new_pressbooks | 44.55 | 44.55 |

## Actual outputs, unedited

Every fixed prompt appears below. No best-of selection. BF16 sampled mode uses temperature 0.8/top-k 40; all generations capped at 96 tokens.

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

### causal_story — sampled

Prompt:
```text
Tom put an ice cube in a bowl and left it in the sun. After an hour,
```

Output:
```text
 Tom went outside and took a nap. He had so much fun that he forgot about his ice cube. From then on, Tom always had his favorite ice cube to go to the park.
```

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

### story — greedy_fp32

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

### causal_story — greedy_fp32

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

### explanation — greedy_fp32

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

### adult_prose — greedy_fp32

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

### conversation — greedy_fp32

Prompt:
```text
User: Hi, how are you?
Assistant:
```

Output:
```text
 The first person to use the word “d” is the “d” and the second person to use the word “d” to describe the word “d” and the second person to use the word “d” to describe the word “d” and the third person to use the word “d” to describe the word “d” and the third person to use the word “d” to describe the word “d” and the third person to use the word “
```

### instruction — greedy_fp32

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

### grounded — greedy_fp32

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

### arithmetic — greedy_fp32

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

### clarification — greedy_fp32

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

### tool — greedy_fp32

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

### tool_example — greedy_fp32

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

### tool_result — greedy_fp32

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
