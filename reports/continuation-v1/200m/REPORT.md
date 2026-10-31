# 200M-token evaluation

Same frozen sets and prompts across 100M/200M/300M. Legacy Wikipedia is now a held-out subset of a trained source, not an unseen domain. Loss and tiny prompt suite are diagnostic, not general capability benchmarks.

| Set | 100M perplexity | Current perplexity |
|---|---:|---:|
| legacy_fineweb_validation | 49.43 | 42.76 |
| legacy_tinystories_validation | 4.96 | 14.96 |
| legacy_tinystories_unseen_shard | 5.99 | 13.19 |
| legacy_wikipedia_untrained_source | 51.86 | 29.38 |
| legacy_fineweb_exposed_train | 41.01 | 38.37 |
| legacy_tinystories_exposed_train | 4.46 | 15.05 |
| new_fineweb | 45.10 | 38.73 |
| new_wikipedia | 50.03 | 24.84 |
| new_pressbooks | 44.55 | 33.56 |

## Actual outputs, unedited

Every fixed prompt appears below. No best-of selection. BF16 sampled mode uses temperature 0.8/top-k 40; all generations capped at 96 tokens.

### story — greedy

Prompt:
```text
Once upon a time, a little girl found a lost puppy. She decided to
```

Output:
```text
 go to the park and find a new friend.
She was a little girl, but she was not sure if she was a little girl. She was a little girl, but she was not sure if she was a little girl.
She was a little girl, but she was not sure if she was a little girl. She was a little girl, but she was not sure if she was a little girl.
She was a little girl, but she was not sure
```

### story — sampled

Prompt:
```text
Once upon a time, a little girl found a lost puppy. She decided to
```

Output:
```text
 walk to the edge of the mountain. As she walked the other way, she saw someone coming from far away.
“I was looking for a dog,” she said, in a surprise. “I’m going to ask you about it.”
“I’m going to give you a gift,” she said, “but when I’m done you’ll find a dog.”
“It was just a dog,” she said.
“Do you have any
```

### causal_story — greedy

Prompt:
```text
Tom put an ice cube in a bowl and left it in the sun. After an hour,
```

Output:
```text
 the ice cube will be in the middle of the day.
- The ice cube will be in the middle of the day.
- The ice cube will be in the middle of the day.
- The ice cube will be in the middle of the day.
- The ice cube will be in the middle of the day.
- The ice cube will be in the middle of the day.
- The ice cube will be in the middle of the day.
```

### causal_story — sampled

Prompt:
```text
Tom put an ice cube in a bowl and left it in the sun. After an hour,
```

Output:
```text
 the water starts to melt. If the water is still cold, the ice will stop working.
Limits of a Normal Time
A typical time-consuming period of time is when the water changes. If it is hot, the time that is not changed occurs. If time is slow, the time changes are called changes in time.
A Normal Time
A Normal Time is when the time changes. If time changes are in the same place,
```

### explanation — greedy

Prompt:
```text
Plants need sunlight because
```

Output:
```text
 they need sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun
```

### explanation — sampled

Prompt:
```text
Plants need sunlight because
```

Output:
```text
 they can be exposed to oxygen.
In a sample of this plant, the plant grows to about 1m or 2m. In areas of high heat, there is less sunlight than in low temperatures. This means that the plant becomes extremely comfortable with any moisture content.
Base temperature: 2.2°C
It is important to know the temperature of the plant, and what is the temperature of the plant. If you notice any of the following symptoms:
-
```

### adult_prose — greedy

Prompt:
```text
When planning a project, it is important to identify the main risks. For example,
```

Output:
```text
 if you are planning a project, you should consider the following:
- The project is not a project.
- The project is not a project.
- The project is not a project.
- The project is not a project.
- The project is not a project.
- The project is not a project.
- The project is not a project.
- The project is not a project.
- The project is not a project.
-
```

### adult_prose — sampled

Prompt:
```text
When planning a project, it is important to identify the main risks. For example,
```

Output:
```text
 if a project needs to be completed before a project is finished, it is important that the project is completed during the project.
- If a project takes too much time, the project may be completed if the project is completed during the project.
- If a project is completed during the project, the project must be completed during the project.
- If a project is finished during the project, the project must meet the project budget for the project.
Information about the
```

### conversation — greedy

Prompt:
```text
User: Hi, how are you?
Assistant:
```

Output:
```text
 I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
```

### conversation — sampled

Prompt:
```text
User: Hi, how are you?
Assistant:
```

Output:
```text

Total: $2,600
Week: $15,400
Federation: $1,200
Locations: $1,600
Operations: $1,300
Pay for a Dollar: $1,500
Briefly: $1,400
Interactive Content:
- “Why is this Interactive Content Important?”
- “What’s the Future of the Content?”
```

### instruction — greedy

Prompt:
```text
User: Give me three tips for staying organized at work.
Assistant:
```

Output:
```text
 Make sure you have a clear plan for your work.
- Make sure you have a clear plan for your work.
- Make sure you have a clear plan for your work.
- Make sure you have a clear plan for your work.
- Make sure you have a clear plan for your work.
- Make sure you have a clear plan for your work.
- Make sure you have a clear plan for your work.
- Make sure you have a
```

### instruction — sampled

Prompt:
```text
User: Give me three tips for staying organized at work.
Assistant:
```

Output:
```text
 Have a consistent schedule with your employees about how they will be expected to spend time on the road.
- Encourage families and businesses to know how their staffing will improve their health.
- Encourage children to stay engaged.
- Encourage families to take advantage of their personal and community skills.
- Encourage everyone to focus on the road.
- Encourage children to stay on the road.
- Encourage their local communities to make their own connections
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
 Maya lives in Pune and works as a teacher.
Answer: Maya lives in Pune and works as a teacher.
Answer: Maya lives in Pune and works as a teacher.
Answer: Maya lives in Pune and works as a teacher.
Answer: Maya lives in Pune and works as a teacher.
Answer: Maya lives in Pune and works as a teacher.
Answer: Maya lives in Pune
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
 I have two sons, one with one girl and one with two girls, one with two girls. They have 2 children, two with two girls and one with two boys, one with three girls and one with two girls. It is my concern that Maya can live in Pune because he wants to stay in Pune and live with them, as much as I can. I want to stay in Pune because it is not my job, but I will stay because it
```

### arithmetic — greedy

Prompt:
```text
Question: What is 7 plus 5?
Answer:
```

Output:
```text

- The number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number
```

### arithmetic — sampled

Prompt:
```text
Question: What is 7 plus 5?
Answer:
```

Output:
```text
 1
- 1 = 5
- 2 = 4
- 1 = 5
- 3 = 5
- 1 = 5
- 2 = 5
- 1 = 2
- 1 = 2
- 1 = 4
- 1 = 4
- 1 = 2
- 1 = 4
- 1 = 3
- 1 = 1
- 1 = 3
- 1 = 4
- 1 = 2
- 1 = 7
- 2 = 5
```

### clarification — greedy

Prompt:
```text
User: What is the weather like?
Assistant:
```

Output:
```text
 What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
```

### clarification — sampled

Prompt:
```text
User: What is the weather like?
Assistant:
```

Output:
```text
 What is the weather?
Assistant: What are the weather?
Assistant: What is snowfall on a snowy day?
Assistant: What does snowfall mean in the rainy season?
Assistant: What is the weather?
Assistant: What is the weather?
Assistant: What is the weather?
Assistant: What is the weather?
Assistant: What is the weather?
Assistant: What is the weather
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
 There is no weather. What is the weather in Bengaluru? What is the weather in Bengaluru? What is the weather in Bengaluru? How is the weather in Bengaluru affect the weather in Bengaluru?
Explore: What is the weather in Bengaluru? How is the weather changed in India?
Explore: What is the weather in Bengaluru? What is the weather in Bengaluru?
Saliva: What is the weather in Bengal
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
 {"name":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather"
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
 {"city":"park".
Weather: Weather in Pune?
Assistant: {"city":"city":"Park":}
Weather: Weather in Pune?
Assistant: {"person":"city":"park":}
Weather: Weather in Pune?
Assistant: {"person":"c
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
 {"result":12}
Assistant: {"result":12}
Assistant: {"result":12}
Assistant: {"result":12}
Assistant: {"result":12}
Assistant: {"result":12}
Assistant: {"result":12}
Assistant: {"result
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
 {"includes {}
Discussion: 9 + 6 = 1
- This is {} = 3 + 4 + 8 = 1
- This is {} = {} 1 + 2 = 1
- This is {} = 0+2.5 + 5 = 1
- This is {} = {} + 18 = 2.3 + 19 = 4(1) {} + 23 =
```

### story — greedy_fp32

Prompt:
```text
Once upon a time, a little girl found a lost puppy. She decided to
```

Output:
```text
 go to the park and find a new friend.
She found a new friend who was also a little girl. She was a little girl. She was a little girl. She was a little girl. She was a little girl. She was a little girl. She was a little girl. She was a little girl. She was a little girl. She was a little girl. She was a little girl. She was a little girl. She was a little girl. She
```

### causal_story — greedy_fp32

Prompt:
```text
Tom put an ice cube in a bowl and left it in the sun. After an hour,
```

Output:
```text
 the ice cube will be in the middle of the day.
- The ice cube will be in the middle of the day.
- The ice cube will be in the middle of the day.
- The ice cube will be in the middle of the day.
- The ice cube will be in the middle of the day.
- The ice cube will be in the middle of the day.
- The ice cube will be in the middle of the day.
```

### explanation — greedy_fp32

Prompt:
```text
Plants need sunlight because
```

Output:
```text
 they need sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun is a good source of sunlight.
- The sun
```

### adult_prose — greedy_fp32

Prompt:
```text
When planning a project, it is important to identify the main risks. For example,
```

Output:
```text
 if you are planning a project, you should consider the following:
- The project is not a project.
- The project is not a project.
- The project is not a project.
- The project is not a project.
- The project is not a project.
- The project is not a project.
- The project is not a project.
- The project is not a project.
- The project is not a project.
-
```

### conversation — greedy_fp32

Prompt:
```text
User: Hi, how are you?
Assistant:
```

Output:
```text
 I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
Assistant: I’m a student.
```

### instruction — greedy_fp32

Prompt:
```text
User: Give me three tips for staying organized at work.
Assistant:
```

Output:
```text
 Make sure you have a clear plan for your work.
- Make sure you have a clear plan for your work.
- Make sure you have a clear plan for your work.
- Make sure you have a clear plan for your work.
- Make sure you have a clear plan for your work.
- Make sure you have a clear plan for your work.
- Make sure you have a clear plan for your work.
- Make sure you have a
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
 Maya lives in Pune and works as a teacher.
Answer: Maya lives in Pune and works as a teacher.
Answer: Maya lives in Pune and works as a teacher.
Answer: Maya lives in Pune and works as a teacher.
Answer: Maya lives in Pune and works as a teacher.
Answer: Maya lives in Pune and works as a teacher.
Answer: Maya lives in Pune
```

### arithmetic — greedy_fp32

Prompt:
```text
Question: What is 7 plus 5?
Answer:
```

Output:
```text

- The number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number of times the number
```

### clarification — greedy_fp32

Prompt:
```text
User: What is the weather like?
Assistant:
```

Output:
```text
 What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
Assistant: What is the weather like?
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
 {"name":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather":"get_weather"
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
 {"result":12}
Assistant: {"result":12}
Assistant: {"result":12}
Assistant: {"result":12}
Assistant: {"result":12}
Assistant: {"result":12}
Assistant: {"result":12}
Assistant: {"result
```
