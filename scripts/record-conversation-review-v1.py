"""Record direct judgments after reading all64 complete frozen dialogues."""
# Creator: Navneet Prabhakar
import collections,json
from pathlib import Path
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/conversation-review-v1')
REASONS={
0:('defer','Specific exercise frequency/strength and diet advice falls outside the first low-risk conversation slice; no individual suitability established.'),
2:('exclude','The counselor invents that the camp has friendly animals and offers concrete facilities without supplied context; later repair does not remove earlier targets.'),
4:('exclude','Repeated irrelevant wizard redirection and changing explanations obstruct a simple capability question; entire dialogue withheld.'),
6:('defer','Climate effects are overgeneralized as more frequent hurricanes without scope or verification; factual science slice deferred.'),
9:('exclude','Summary uses She despite explicit system prohibition on second and third person pronouns.'),
12:('exclude','Presents cap and gown as usual senior-photo attire without locality/context; unsupported universal framing.'),
15:('exclude','Summary omits the central intent of aligning the research argument with scripture while retaining only generic geology topics.'),
16:('exclude','Asserts keyboard navigation support and Up/Down behavior for an unidentified chatbot; unsupported product capability targets.'),
17:('exclude','Rewrite changes ideas that could help future research into discussions that already have been insightful; strengthens uncertain claim.'),
18:('defer','Claims current-year fashion popularity without dated evidence; outside stable first research scope.'),
24:('exclude','Invents a substantive solid-chain versus interlocking-chain-link distinction and current belt trends without grounding.'),
25:('exclude','A trailing quotation mark follows the required exact ending phrase; first-slice literal constraint fidelity is not met.'),
26:('exclude','Rewrites add self-discovery and relaxation to taking time to oneself and introduce extra destination claims; meaning preservation is not exact.'),
32:('exclude','First algebra answer gives false identity 1+x^2=(1+x)(1-x)+2x; later correct math turns do not repair the whole target dialogue.'),
33:('exclude','Adds STEM lab materials where the supplied email refers more generally to curriculum materials and hands-on activities.'),
36:('defer','Universal clothing/showering frequency guidance is not supported by personal context; health/hygiene advice excluded from initial scope.'),
39:('defer','Source asserts specific medical study findings without verifiable references; first-slice research does not admit those factual claims.'),
40:('exclude','Requested rhyming couplet is emitted as one undivided quoted line, failing the requested two-line poetic form.'),
44:('defer','Aircraft retirement date and historical superlative require niche verification before training admission.'),
46:('exclude','Repeated yes/no nonanswers and contradictory willingness claims fail actual user requests despite one-word system constraint.'),
50:('exclude','Adds speculative Spanish etymological explanation for consumor without evidence; full conversation retained as exclusion.'),
52:('defer','Species-specific pet safety, low-light and fixed watering advice need independent verification; outside initial slice.'),
59:('exclude','Changes starting to settle into the new role to already settled; alters the supplied completion state.'),
61:('exclude','Invents a current weather forecast without location, data or user-supplied forecast context.'),
63:('exclude','Summary uses He despite explicit prohibition on second and third person pronouns.')}
def main():
 target=ROOT/'direct-judgments.jsonl'
 if target.exists():raise FileExistsError(target)
 sample=[json.loads(x) for x in (ROOT/'sample.jsonl').open()];out=[]
 for s in sample:
  i=s['index'];judgment,reason=REASONS.get(i,('consider','Complete dialogue read: supplied-context transformation, low-risk creative text, checked elementary reasoning or general everyday assistance is relevant; no material observed target error in this reading. Not individual factual/privacy/SFW certification.'))
  out.append(dict(index=i,row_index=s['record']['row_index'],source=s['record']['source'],record_sha256=digest(s['record']),sample_sha256=sha(ROOT/'sample.jsonl'),full_text_read=True,review_mode='delegated_expert',human_attestation=False,judgment=judgment,reason=reason,training_approved=False))
 with target.open('x') as f:
  for r in out:f.write(json.dumps(r,sort_keys=True)+'\n')
 counts=dict(collections.Counter(r['judgment'] for r in out));bad=sum(r['judgment']!='consider' for r in out)
 report=dict(creator='Navneet Prabhakar',complete=True,fully_read=64,counts=counts,nonapproval_fraction=bad/64,maximum_nonapproval_fraction=.25,passed=bad/64<=.25,training_approved=False,human_attestation=False,sample_sha256=sha(ROOT/'sample.jsonl'),journal_sha256=sha(target),scope='Purposive constituent-stratified screen review; not a population quality estimate. Failure retained; no broad source admission.')
 (ROOT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
