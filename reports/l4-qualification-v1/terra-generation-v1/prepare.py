import json
from pathlib import Path
from cloud_training.nano_tool_lessons import build_lessons
r=Path('runs/terra-conversation-v1');sources=build_lessons('train',per_family=1,seed=7103);(r/'tool-seeds.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2))
def obj(properties):return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
def arr(items):return {'type':'array','items':items}
string={'type':'string'}
message=obj({'role':{'type':'string','enum':['user','assistant']},'content':string})
schema=obj({'conversations':arr(obj({'family':string,'messages':arr(message)})),'tool_rewrites':arr(obj({'session_id':string,'user_messages':arr(string)}))})
(r/'schema.json').write_text(json.dumps(schema))
prompt='''Generate candidate training data for a small English assistant. Do not use tools, shell, repository reads, network, agents, or file edits. Return only the required JSON final response. Produce16 diverse conversations, each2-3 user/assistant pairs, brief natural responses under60 words each. Include changed facts, changed preferences, clarification, practical planning, exact requested output, and grounding in supplied text. Each conversation must be self-contained and correct. Avoid external factual knowledge, personal data, current events and coding. Separately rewrite user messages of all8 supplied tool lessons into diverse phrasing, preserving EVERY number, entity, operation, order, unit, missing-information constraint, permission and requested output. Return original session_id and one rewritten text per original user turn. Do not produce assistant messages or results for tool lessons; those come from real broker execution. These are training candidates, not evaluation cases.\nSEEDS:\n'''+json.dumps([{'session_id':s['session_id'],'family':s['family'],'messages':s['messages']} for s in sources],ensure_ascii=False)
(r/'prompt.txt').write_text(prompt)
