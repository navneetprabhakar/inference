import json
from pathlib import Path
P=Path(__file__).parent
notes=[
['Biology claims not independently verified.','Same-topic clarification, no retained user correction.','Precise physiology quantities unverified; outside English target.'],
['Emergency advice not qualified; weak grammar.','Health claims not independently verified.','Uses hours despite user seconds unit; lowercase I and unit terminology issues.'],
['Product claims and implied search not verified.','Appropriate acknowledgment.','Generic comparison, no delayed recall.'],
['Does not clearly explain requested wordplay.','Routine acknowledgment.','Routine closing; no correction or memory.'],
['Fictional interview with inconsistent carrot characterization.','Applies identity twists but not requested self-revelation exactly.','Accurate text-only capability limit; no later retention test.'],
['Historical/technical claims unverified.','Unhelpful what instead of specific clarification.','Technical answer unverified and punctuation error.'],
['Generic deployment outline, unverified and not executable as written.','Awkward Glad you know phrasing.','Routine closing, no target memory.'],
['Journal facts not independently checked.','Advice qualified but scope not target memory.','A is a not grammar; names/roles unverified.']]
rows=json.loads((P/'sample.json').read_text())['rows'];assert len(rows)==8
reviews=[]
for r,ns in zip(rows,notes):
 assert len(r['messages'])==6
 reviews.append({'review_key':r['review_key'],'source_group':r['source_group'],'path_ids':r['path_ids'],'decision':'exclude_from_target_shortlist','assistant_turn_reviews':[{'turn':i+1,'observation':n} for i,n in enumerate(ns)],'training_admitted':False})
(P/'review.json').write_text(json.dumps({'review_method':'Full manual Codex trajectory review; specialist facts not independently verified','reviewed_conversations':8,'reviewed_assistant_responses':24,'retained':0,'reviews':reviews},indent=2)+'\n')
(P/'shortlist.json').write_text(json.dumps({'rows':[],'training_admitted':False})+'\n')
