"""Persist explicit semantic judgments after reading complete source conversations."""
import hashlib,json
from pathlib import Path
R=Path('reports/ganesh-english-sourcing-v1');P=Path('runs/ganesh-english-sourcing-v1/source-candidates.jsonl')
rows=[json.loads(x) for x in P.read_text().splitlines()]
judgments={
0:('exclude','roleplay','Invented royal permission and violent roleplay; outside current ordinary-English curriculum.'),
1:('shortlist','rewrite','All three rewrites preserve the requested scene and progressively shorten it; explanatory scaffolding is verbose. Cap editing mass; not a brevity gold example.'),
2:('reject','grounding','Last reply invents historical negotiation and oversight details rather than preserving supplied text; historical assertions unverified.'),
3:('exclude','maths','Statistics outside current English scope; quantile terminology is imprecise. Not maths-admitted.'),
4:('exclude','maths','Analytic geometry outside current English scope; no maths admission or executable verification claimed.'),
5:('exclude','roleplay','Repeated persona switching with invented medical/police scene details, not ordinary assistant dialogue.'),
6:('reject','grounding','Rumours and invented personal facts presented as fact; unsuitable style and grounding supervision.'),
7:('exclude','coding','JavaScript implementation tasks; defer coding, no execution or correctness certification.'),
8:('shortlist','rewrite','Responds to request for less detail and corrects subject pronouns; user supplies the few-customers paraphrase. Editing-only, not delayed-memory evidence.'),
9:('reject','instructions','Single-sentence request gets prefatory commentary; introduces extra scene details during revision.'),
10:('exclude','roleplay','Fictional 1985 persona and invented itinerary; no reliable ordinary-context supervision.'),
11:('exclude','coding','Programming constraints outside scope; no execution certification.'),
12:('exclude','roleplay','Pilot persona with invented passengers/aircraft; not grounded assistant memory.'),
13:('exclude','roleplay','Repeated role prompts and invented trail facts; poor natural multi-turn training example.'),
14:('exclude','maths','Derivative lessons deferred; no maths admission.'),
15:('exclude','coding','Programming/maths conversion tasks deferred; no execution certification.'),
16:('shortlist','clarification','Requests missing edit text; fixes duplicate subject/to-too and me-I/to-too correctly. Verbose but substantive explanations; max reply budget must be verified.'),
17:('reject','capabilities','Unverified broad expertise claim plus programming content; missing-code clarification alone cannot rescue full trajectory.'),
18:('exclude','coding','Programming tasks deferred; contradictory reaction to explicitly requested function repetition also undesirable.'),
19:('reject','instructions','Final answer repeats derivation despite request to stop at answer; earlier explanation of angle cancellation is misleading.')}
p=R/'semantic-review.jsonl'
existing={x['id']:x for x in [json.loads(l) for l in p.read_text().splitlines()]} if p.exists() else {}
for i,(decision,family,note) in judgments.items():
 row=rows[i]; n=len(row['messages'])//2
 existing[row['id']]={'id':row['id'],'candidate_index':i,'source_messages_sha256':hashlib.sha256(json.dumps(row['messages'],ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'reviewer':'Codex primary agent','review_scope':'all user and assistant messages read','assistant_turns_read':n,'decision':decision,'family':family,'rationale':note,'independent_review':False,'training_admitted':False}
p.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in sorted(existing.values(),key=lambda x:x['candidate_index'])))
print('Reviewed',len(existing),'shortlisted',sum(x['decision']=='shortlist' for x in existing.values()))
