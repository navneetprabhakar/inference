exec(open('reports/ganesh-english-sourcing-v1/review_batch.py').read().split('judgments={')[0])
judgments={
69:('exclude','science','Planetary motion and conic sections deferred; not certified as maths/science data.'),
71:('reject','instructions','Mostly copies answers already supplied; unclear correction is brushed aside rather than clarified.'),
75:('exclude','maths','Arithmetic/percentage lesson deferred; no maths admission.'),
76:('exclude','maths','Sales percentage lesson deferred; causal praise of strategies exceeds supplied evidence.'),
77:('exclude','technical','Coding theory and Reed-Solomon claims require technical review; outside current English curriculum.'),
79:('shortlist','rewrite','First response stays within40 whitespace words; subsequent shortening and reorganisation preserve stated editing role. Limited identity-like editing mass.'),
87:('shortlist','rewrite','Preserves orientation tomorrow/start Monday across concise and formal rewrites; no invented date or location.'),
88:('shortlist','grounding','Correctly preserves deductive validity for all-dog premise and rejects conclusion under most-dog premise; useful quantifier sensitivity. Explanation is verbose.'),
89:('reject','language_explanation','Corrected sentences are right but explanation calls each a singular noun rather than a pronoun; avoid teaching inaccurate grammatical terminology.'),
92:('exclude','coding','Programming tasks outside English scope; no execution verification.'),
94:('exclude','coding','Programming tasks outside English scope; local-versus-UTC date distinction unaddressed.'),
96:('reject','capabilities','Three generic capability advertisements without performing a task; weak supervision for desired actual conversation.'),
98:('exclude','technical','Technical interface definitions deferred; not assessed for technical accuracy.'),
99:('reject','grounding','Final revision invents turn-to-first priority and removes expert qualification; changes the stated business vision.'),
102:('exclude','science','Botanical facts deferred; no factual validation.'),
103:('reject','grounding','Turns a single-swarm example into up-to bound and drops historical actuality; further edits add unsupported ecological consequences.'),
108:('exclude','maths','Number theory deferred; not maths-admitted.'),
114:('reject','instructions','Every answer adds explanation despite persistent single-revised-sentence requirement; tentative observations strengthened into certainty.'),
116:('exclude','science','Fossilisation definitions deferred; no science certification.'),
119:('exclude','science','Molecular biology deferred; no science certification.')}
exec("p=R/'semantic-review.jsonl'"+open('reports/ganesh-english-sourcing-v1/review_batch.py').read().split("p=R/'semantic-review.jsonl'")[1])
