# Cleaner-core stage: not promoted

Completed 1,000,164 non-padding input tokens from V11, using LR 3e-5 and microbatch 4. The corpus excludes 2,145 legacy local-teacher records. Exclusion does not erase their earlier influence on V11.

| Decode | Whole conversations | Correct turns | Full tool conversations | Exact required calls | Required abstentions |
|---|---:|---:|---:|---:|---:|
| Prose 1.2 / tool 1.2 | 3/40 | 8/80 | 3/10 | 4/8 | 2/2 |
| Prose 1.0 / tool 1.2 | 3/40 | 8/80 | 3/10 | 4/8 | 2/2 |
| V11 reference | 4/40 | 10/80 | 3/10 | 5/8 | 2/2 |

No prose conversation passed. Removing the prose repetition penalty increased mean repeated-four-gram fraction from 0.90% to 4.83%, without a correctness gain. All tool calls, fixture results and replies were identical across decoding arms.

The preliminary weather-conversation pass was rejected against the frozen criterion: its follow-up failed to identify the missing location and real-time forecast access.

## Actual outputs at penalty 1.2

### v3-development-t-031

User: Use the calculator to multiply 7 by 8.

Student: <|tool_call|>{"name":"calculate","arguments":{"op":"multiply","a":7,"b":8}}

Fixture trace: `[{"call": {"name": "calculate", "arguments": {"op": "multiply", "a": 7, "b": 8}}, "result": {"result": 56}, "accepted_fixture": true}]`

Student after tool: The result is 55.

User: What number did the calculator return?

Student: The calculator returned 6.

### v3-development-t-033

User: Use conversion to express 480 cm in metres.

Student: <|tool_call|>{"name":"convert","arguments":{"value":480,"from_unit":"cm","to_unit":"m"}}

Fixture trace: `[{"call": {"name": "convert", "arguments": {"value": 480, "from_unit": "cm", "to_unit": "m"}}, "result": {"result": 4.8, "unit": "m"}, "accepted_fixture": true}]`

Student after tool: 4.8 m.

User: State the converted measurement.

Student: 4.8 m

### v3-development-p-002

User: A classroom has 18 pencils and receives 7 more. How many pencils are there now?

Student: 121 pencils.

User: If 9 are used, how many remain?

Student: 118 pencils.

## Decision

Retain V11 as the reference. Do not extend this stage unchanged. Reviews are parent-assistant per-case judgments, not independent human review. Confirmation remains untouched.
