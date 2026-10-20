"""Preserve direct full-text review decisions; no synthetic semantic grading."""
# Creator: Navneet Prabhakar
import collections,json
from pathlib import Path
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/grounded-conversations-v1')
BAD={0:'First naming answer reverses chronology: the paragraph says Neptune was proposed first, then Le Verrier; approval question also assumes actual approval despite stated false claim.',7:'Country question labels Rome, a city; highest artistic expression also overstates the supplied major-form claim.',8:'Date of calling the council is conflated with its first session opening; original passage does not support that exact calling date.',11:'The target purely resistive feedpoint omits impedance, leaving an incomplete technical answer; malformed question wording also reduces reliability.',12:'Questions reverse the before-20th-century framing; supplied20th answer contradicts the paragraph and mass-at-rest framing is reassigned to the earlier definition.',16:'First question asks all whites in1970 but62.4% specifically describes non-Hispanic whites; category qualifier is essential.',29:'Halogen70% is power used, not saved; both CFL lifetime labels misattribute the LED lifetime and duplicate the question.',30:'Where question is paired with a decade rather than location; this is not a correct supplied question/answer target.',38:'All bird species question is labeled with resident-only count, omitting the separately migrating200; ambiguous total cannot be certified.',43:'17–18% is mean European ancestry, not the fraction of African Americans having European ancestry; the question changes the quantity.',48:'Final thing shown was test transmissions after the cartoon according to the supplied paragraph; cartoon answer conflicts with exact wording.',63:'Question generalizes an attributed, conditional US-Hispanic social classification to what all Latinos consider, dropping the class/status condition.'}
def main():
 if (ROOT/'direct-judgments.jsonl').exists():raise FileExistsError('Immutable direct review')
 sample=[json.loads(l) for l in (ROOT/'sample.jsonl').open()]
 if len(sample)!=64 or len({s['record']['split_group'] for s in sample})!=64:raise ValueError('Distinct complete64 article-component sample required')
 journal=[]
 for s in sample:
  i=s['index'];r=s['record']
  if digest(r)!=s['record_sha256']:raise ValueError('Sample changed')
  journal.append(dict(index=i,paragraph_id=r['id'],split_group=r['split_group'],article=r['article'],record_sha256=digest(r),sample_sha256=sha(ROOT/'sample.jsonl'),full_text_read=True,human_attestation=False,review_mode='delegated_expert',judgment='exclude' if i in BAD else 'consider',reason=BAD.get(i,'Complete passage and all three original human questions/answer spans read. Answers address their questions with supplied passage evidence; no material observed target error. Historical/source assertions are supplied context, not independently verified current facts. Minor source wording defects retained without rewriting. Consideration only.'),training_approved=False))
 with (ROOT/'direct-judgments.jsonl').open('x') as f:
  for r in journal:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 report=dict(creator='Navneet Prabhakar',complete=True,fully_read=64,actual_question_answer_pairs_read=192,distinct_article_components=64,counts=dict(collections.Counter(r['judgment'] for r in journal)),nonapproval_fraction=len(BAD)/64,maximum_nonapproval_fraction=.25,passed=len(BAD)/64<=.25,all_observed_negative_article_components_withheld=True,human_attestation=False,training_approved=False,sample_sha256=sha(ROOT/'sample.jsonl'),journal_sha256=sha(ROOT/'direct-judgments.jsonl'),scope='Purposive fixed sample, not a population defect estimate. Generic wrappers are fixed and original full passages/all192QA targets directly read. Whole negative article components withheld, even unsampled paragraphs. Most other rows unread; no SFW/individual source factuality certification.')
 (ROOT/'review-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
