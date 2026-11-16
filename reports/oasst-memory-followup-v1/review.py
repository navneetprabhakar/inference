"""Recorded manual full-path review; excluded source text is not training data."""
import json
from pathlib import Path
P=Path(__file__).parent
notes={
'N':[
['Hypothetical planet count, not personal-state memory.','Astronomy facts not independently verified for admission.','Same-topic science continuation, no retained correction or delayed user-fact retrieval.'],
['Tests not executed; technical scope.','Implementation unverified; code formatting omitted.','Fails formatting request; attributes assistant code to user and ignores return inside loop.'],
['Awkward poem syntax; source-event fidelity unverified.','New poem uses strained wording.','Requested slant rhyme but supplies repeated exact rhymes sky/spy/eye/try.'],
['Useful clarification mixed with generic advice and clearning typo.','Verbose generic answer despite supplied ages.','Calls prior assistant reply an article; no later persistence of brevity correction.']],
'R':[
['Historical claims unverified and alternate-setting constraint not addressed concretely.','Historical causal account unverified; unsuitable factual supervision.','Time-sensitive officeholder claim without date; topic switch, no memory.'],
['Roleplay uses Open Assistant identity, unsuitable Own target.','Repeats question in requested persona.','Does not keep exact sentence-ending instruction; tea-origin facts unverified.'],
['Technical Nix explanation not verified.','Package-manager comparison not verified.','Pacage typo and an isolated environments grammar; no target recall.'],
['Technical disk-repair guidance not qualified.','Does not answer whether errors are fixed or only reported.','Routine acknowledgment cannot rescue missed question.'],
['Restaurant recommendations not independently checked.','Menu and star count unverified/time-sensitive.','II typo and unsupported future-learning implication.'],
['Assembly not executed; arithmetic implementation requires separate validation.','C program not executed; out of English curriculum scope.','Broad compiler assurance unverified; no retained correction.'],
['Erotic writing outside current English curriculum; user rejects quality.','Immediate revision only.','Speculates about partner feelings; not correction-retention or delayed recall.'],
['Categorical legal answer not qualified or verified.','Categorical educational-use claim not qualified or verified.','Later caveats cannot qualify earlier targets; legal scope excluded.'],
['Package workflow not executed or checked.','Contribution workflow not verified.','Generic follow-up advice; no user-fact recall or correction retention.'],
['Technical fill-in answer not independently checked.','Repeats ambiguous former/latter wording without clarification.','It was my please grammar error.'],
['Scientific claims not independently checked.','Does not clearly distinguish unknown mechanisms from proof of a deity.','Appropriate request for clarification; no target memory.'],
['Fictional public-person persona invents release/personal claims; unsuitable curriculum.','General discussion rather than corrective retention.','Unrelated game question; facts unverified.'],
['Code not executed; technical scope.','Runtime/integration instructions not qualified.','Generic documentation link rather than function references; no target recall.'],
['Absolute unsupported counterfactual.','Expands speculation as confident claims.','Agreement does not resolve ambiguity; no target recall.'],
['Industrial-control claims not independently checked.','Technical comparison not qualified.','Malformed comparison table and unclear column ownership.'],
['Performance-history facts unverified.','Switches from mime to impersonation and includes nature link.','Continues mixed categories; no earlier user fact or correction retained.']]
}
reviews=[]
for prefix,name in [('N','sample.json'),('R','broad-sample.json')]:
 rows=json.loads((P/name).read_text())['rows'];assert len(rows)==len(notes[prefix])
 for r,ns in zip(rows,notes[prefix]):
  assert len(ns)==sum(m['role']=='assistant' for m in r['messages'])==3
  reviews.append({'review_key':r['review_key'],'source_group':r['source_group'],'path_ids':r['path_ids'],'decision':'exclude_from_target_shortlist','assistant_turn_reviews':[{'turn':i+1,'observation':n} for i,n in enumerate(ns)],'training_admitted':False})
(P/'review.json').write_text(json.dumps({'review_method':'Codex read every full trajectory; no specialist fact-check or code execution claimed','rubric':'Same as oasst-delayed-memory-v1: full-path suitability plus correction preserved in later answer or earlier user fact recalled after an intervening completed exchange without target restatement. Acknowledgments and topic continuation do not qualify.','reviewed_conversations':20,'reviewed_assistant_responses':60,'retained':0,'reviews':reviews},indent=2)+'\n')
(P/'shortlist.json').write_text(json.dumps({'rows':[],'training_admitted':False,'reason':'No fully suitable target trajectory; previous four candidates unchanged.'},indent=2)+'\n')
