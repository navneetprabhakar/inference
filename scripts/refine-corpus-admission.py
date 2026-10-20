"""Record failed broad admission; freeze narrower population and fresh audit."""
# Creator: Navneet Prabhakar
import json,sqlite3
from pathlib import Path
from collections import Counter
from slm.data.english_eligibility import reasons,RULE
from slm.data.schema import digest
from slm.data.stream_hash import sha
old=Path('data/english-corpus-admission-review-v1');out=Path('data/english-corpus-admission-review-v2')
if out.exists():raise FileExistsError(out)
# Only read complete records count as reviewed. Long partially delivered record9 is deferred, not claimed read.
notes={0:('consider','Coherent dictionary senses and examples; limited breadth.'),1:('exclude','Unrelated search-result fragments and incomplete question.'),2:('consider','Coherent attributed historical news; factual recency unverified.'),3:('exclude','Search-result fragments/ellipses; incomplete sentences.'),4:('consider','Coherent historical explanation; footer and dated claims remain.'),5:('consider','Museum-history prose with explicit source; repeated introduction is minor.'),6:('exclude','Forum spam, truncation and coursework promotion contaminate explanation.'),7:('consider','Mostly coherent product history; broken introduction/footer remain residual defects.'),8:('exclude','Promotional clinical guidance and public business telephone; unsuitable recovery scope.'),9:('defer','Long record delivery was truncated; full review not completed, table extraction also incomplete.'),10:('exclude','Unverified home-treatment/cure guidance; quarantine clinical treatment.'),11:('consider','Coherent historical encyclopedia prose; dated political numbers, not current-fact certification.'),12:('defer','Only chapter introduction/first subsection with unverified citation; incomplete promised coverage.'),13:('exclude','Synthetic biographical assertions not grounded in retained source; birthplace/date require verification.'),14:('consider','Readable simplified radio-frequency explanation; analogies are approximate.'),15:('exclude','Conflates qualities with substances and overstates immaterial categories; broken-vase explanation misleading.'),16:('consider','Readable religious/social explanation; organizational comparisons remain unverified.'),17:('consider','Readable simplified Mars-resource explanation; engineering claims unverified.'),18:('consider','Coherent faith-specific instructional prose; unreferenced research claim remains a limitation.'),19:('consider','Coherent SIEM overview; attributed quotation unverified.'),20:('consider','Coherent scheduling/delegation lesson with an explicit example.'),21:('exclude','Synthetic clinical intervention/pharmacotherapy advice outside verified recovery scope.'),22:('exclude','Specific breach/botnet/statistic attributions unverified and potentially mischaracterized.'),23:('defer','Detailed synthetic real-person life/award assertions lack independent grounding.'),24:('consider','Complete simple fictional bargain and resolution.'),25:('exclude','Unnatural grammar: friends number around; malformed story.'),26:('consider','Complete simple shopping exchange and follow-up.'),27:('consider','Clear cause/consequence story; unhappy ending is allowed.'),28:('consider','Complete simple sharing story; repetitive source style disclosed.'),29:('consider','Coherent zoo visit and dialogue.'),30:('consider','Readable fictional discovery and resolution; fanciful bird allowed.'),31:('consider','Coherent fictional cooperation and shared outcome.'),32:('exclude','Literal wind blows away a fake smile; incoherent emotional-state causality.'),33:('exclude','Ride already accepted/begun then repeats unasked offer; state contradiction.'),34:('consider','Coherent party preparation and behavior follow-through.'),35:('consider','Complete anthropomorphic friendship story with explicit moral.')}
rows=[json.loads(l) for l in (old/'samples.jsonl').read_text().splitlines()];judgments=[]
for i,r in enumerate(rows):
 decision,note=notes[i];judgments.append(dict(sid=r['sid'],source=r['source'],content_sha256=r['content_sha256'],decision=decision,reason=note,full_record_read=i!=9,human_attestation=False,authority='delegated_expert'))
(old/'judgments.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in judgments))
stats={s:dict(Counter(r['decision'] for r in judgments if r['source']==s)) for s in ['general','explanatory','narrative']}
(old/'decision.json').write_text(json.dumps(dict(creator='Navneet Prabhakar',training_approved=False,statistics=stats,source_admission=dict(general='rejected',explanatory='rejected',narrative='conditional_finite_research_only'),scope='General and explanatory exceed frozen25% nonapproval limit; no broad admission. Narrative at25%, still needs grouping and exact release. New narrower population uses a fresh sample; original failures preserved.'),indent=2)+'\n')
out.mkdir();db=sqlite3.connect('file:'+str(Path('data/global-exact-families-v2/families.sqlite').resolve())+'?mode=ro',uri=True)
blocked={r['sid'] for r in judgments if r['decision']!='consider'};selected=[];population={};denials=Counter()
for source in ['general','explanatory','narrative']:
 eligible=[]
 for sid,data in db.execute('SELECT sid,data FROM records WHERE ingredient=? AND candidate=1 AND fixed=0 AND blocked=0',(source,)):
  record=json.loads(data);bad=reasons(record)
  if sid in blocked:bad.append('observed_nonapproval')
  if bad:denials.update(bad);continue
  eligible.append((sid,record))
 population[source]=dict(records=len(eligible),content_tokens=sum(r['tokens'] for _,r in eligible))
 ranked=sorted(eligible,key=lambda x:(x[1]['tokens'],x[0]));n=len(ranked)
 # Two complete fresh records per quartile, exclude every previous sampled record from selection, not population.
 for q in range(4):
  bucket=[x for x in ranked[n*q//4:n*(q+1)//4] if x[0] not in {r['sid'] for r in rows}]
  for sid,r in sorted(bucket,key=lambda x:digest(['english-corpus-admission-review-v2',x[1]['id']]))[:2]:selected.append(dict(sid=sid,source=source,length_quartile=q,content_sha256=digest(r['texts']['content']),record=r))
(out/'samples.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in selected))
plan=dict(creator='Navneet Prabhakar',kind='refined-finite-language-review-v2',population=population,samples=24,rule=RULE,source_defect_fraction_reject_above=.25,critical_privacy_or_unsafe_defects_allowed=0,prior_nonapprovals=sorted(blocked),known_failed_broad_population_preserved=True,human_attestation=False,training_approved=False,inputs={p:sha(p) for p in ['src/slm/data/english_eligibility.py',__file__,str(old/'decision.json'),str(old/'judgments.jsonl'),'data/global-exact-families-v2/families.sqlite']},sample_sha256=sha(out/'samples.jsonl'))
(out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps(plan,indent=2))
