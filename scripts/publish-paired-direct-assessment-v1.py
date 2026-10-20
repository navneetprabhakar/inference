"""Bind explicit direct judgments to every actual paired conversation; aggregate only."""
# Creator: Navneet Prabhakar
import json,re
from pathlib import Path
from collections import Counter
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/balanced-versus-foundation-assessment-v1')

def main():
 integrity=json.loads(Path('reports/balanced-versus-foundation-integrity-v1.json').read_text())
 if not integrity['complete']:raise ValueError('Actual600pair integrity first')
 protocol=json.loads(Path('configs/current-model-100-conversations-v1.json').read_text());summary={}
 for name in ('foundation','corrected'):
  rows=[json.loads(x) for x in (ROOT/name/'turns.jsonl').read_text().splitlines()]
  if sha(ROOT/name/'turns.jsonl')!=integrity['models'][name]['turns_sha256']:raise ValueError('Actual raw replies changed')
  judgments=[json.loads(x) for x in (ROOT/('direct-review-'+name+'.jsonl')).read_text().splitlines()]
  if [x['conversation'] for x in judgments]!=list(range(1,101)):raise ValueError('One explicit review per complete conversation')
  for i,j in enumerate(judgments):
   if len(j['turn_success'])!=3 or any(type(x) is not bool for x in j['turn_success']):raise ValueError('Three explicit task judgments')
   if set(j['dimensions'])!=set(protocol['rubric']['dimensions']) or any(type(x) is not int or not 0<=x<=4 for x in j['dimensions'].values()):raise ValueError('Original rubric required')
   if not j['reason'] or not j['coherence_reason']:raise ValueError('Direct evidence reasons required')
   actual=rows[i*3:i*3+3];j.update(category=actual[0]['category'],recorded_turns_sha256=digest(actual),score_out_of_100=sum(j['dimensions'].values())*5,successful_turns=sum(j['turn_success']),conversation_succeeded=all(j['turn_success']))
  categories={}
  for category in sorted({x['category'] for x in judgments}):
   group=[x for x in judgments if x['category']==category]
   categories[category]=dict(conversations=len(group),successful_conversations=sum(x['conversation_succeeded'] for x in group),successful_turns=sum(x['successful_turns'] for x in group),mean_score_out_of_100=sum(x['score_out_of_100'] for x in group)/len(group))
  looping=0
  for row in rows:
   words=re.findall(r'\w+',row['response']['text'].lower());ng=Counter(tuple(words[i:i+8]) for i in range(len(words)-7))
   looping+=bool(ng and max(ng.values())>=3)
  metrics=dict(conversations=100,turns=300,successful_conversations=sum(x['conversation_succeeded'] for x in judgments),successful_turns=sum(x['successful_turns'] for x in judgments),mean_score_out_of_100=sum(x['score_out_of_100'] for x in judgments)/100,dimension_means={d:sum(x['dimensions'][d] for x in judgments)/100 for d in protocol['rubric']['dimensions']},categories=categories,**{k:v for k,v in integrity['models'][name].items() if k not in ('turns','conversations')},replies_with_same_word_8gram_at_least_3_times=looping)
  report=dict(creator='Navneet Prabhakar',model=name,complete=True,**metrics,judgments=judgments,rubric=protocol['rubric'],review_mode='direct_expert',human_attestation=False,review_coverage='All600paired replies reviewed across both reports; exact duplicates mapped only after text equality, other repeats rendered losslessly with original character runs/counts. No output truncation in the review view or published raw transcripts.',integrity_report_sha256=sha('reports/balanced-versus-foundation-integrity-v1.json'),direct_judgment_file_sha256=sha(ROOT/('direct-review-'+name+'.jsonl')),production_accepted=False,training_approved=False)
  target=Path('reports/paired-'+name+'-direct-assessment-v1.json');target.write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+'\n');assert target.stat().st_size<100*1024;summary[name]=metrics
 result=dict(creator='Navneet Prabhakar',complete=True,models=summary,task_success_change_corrected_minus_foundation=summary['corrected']['successful_turns']-summary['foundation']['successful_turns'],rubric_change_corrected_minus_foundation=summary['corrected']['mean_score_out_of_100']-summary['foundation']['mean_score_out_of_100'],scope='Paired deterministic visible development comparison; fixed later user prompts, separate actual assistant history. Direct unblinded judgments, not population accuracy or isolated causal attribution. Repetition statistic is descriptive, not semantic scoring.',model_updates=0,teacher_calls=0,cloud_commands=0)
 Path('reports/balanced-versus-foundation-comparison-v1.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
