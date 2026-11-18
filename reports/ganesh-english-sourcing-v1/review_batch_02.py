exec(open('reports/ganesh-english-sourcing-v1/review_batch.py').read().split('judgments={')[0])
judgments={
20:('shortlist','instructions','All three responses acknowledge the evolving feedback-label preference accurately; no actual paragraph edit occurs, so count as clarification/preference only, not demonstrated delayed recall.'),
21:('reject','instructions','Initial concise request gets a long restatement of the supplied answer; weak instructional value and repetitive explanation.'),
23:('reject','instructions','One-sentence collaborative story gets extra conversational scaffolding; lengthy speculative genre list adds little grounded supervision.'),
24:('exclude','maths','Unit-conversion lesson deferred, no maths admission.'),
25:('reject','instructions','First single-sentence request receives additional explanatory paragraph; unsuitable strict instruction gold.'),
26:('reject','grounding','Adds unverified song-origin claim to a simple editing request; avoid external-knowledge distraction.'),
27:('exclude','medical','Medical reassurance and quote attribution require specialised review; outside English curriculum scope.'),
33:('exclude','gambling','Betting-rule descriptions outside ordinary English scope; no rule accuracy certification.'),
37:('reject','reasoning','Fails to flag impossible premise of ten mutually distinct weekday preferences among seven days; later maths is deferred.'),
39:('reject','identity','Generalises a training cutoff as inability to absorb any new information; problematic capability wording for context-aware model.'),
43:('shortlist','rewrite','Corrects missing article, then adds scene detail only when asked and supplies a street name when requested; verbose but coherent evolving creative edit.'),
50:('exclude','roleplay','Antique-shop persona and unverified appraisal assertions; outside ordinary assistant dialogue.'),
53:('reject','grounding','Changes unspecified impact/affect to damage/reduce/harm without establishing negative direction; alters supplied meaning.'),
54:('shortlist','language_explanation','Active/passive examples and both requested transformations are correct; beginner-level explanation, no tool need.'),
55:('reject','instructions','Four-words-per-line constraint violated by copying the user example with1/3/3/2 words; first exact phrase also expanded.'),
58:('exclude','science','Botany explanation deferred; scientific detail not independently verified.'),
60:('reject','grounding','Rewrites deaths into widespread population decline and responsible into linked; does not preserve original claim precisely.'),
62:('reject','language','Changes new coffee machine to barely new, an unnatural and misleading edit.'),
66:('reject','grounding','Rewrites many students as some and confidence-or-preparedness as both; meaning changes under an editing request.'),
67:('shortlist','rewrite','Three edits preserve the user-provided editing-assistant description and interaction process; first-person role comes from supplied text. Verbose scaffolding, limited curriculum share.')}
exec(open('reports/ganesh-english-sourcing-v1/review_batch.py').read().split("p=R/'semantic-review.jsonl'")[1].join(["p=R/'semantic-review.jsonl'",'']))
