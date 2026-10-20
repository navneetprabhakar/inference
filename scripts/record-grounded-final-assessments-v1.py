"""Record completed direct semantic judgments from an explicit manually reviewed decision map."""
# Creator: Navneet Prabhakar
import collections,importlib.util,json
from pathlib import Path
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/grounded-conversation-run-v1');CORE=Path('data/grounded-core-comparison-v1')
def main():
 decision_path=ROOT/'manual-final-decisions-v1.json';manual=json.loads(decision_path.read_text());plan=json.loads(Path('configs/grounded-conversation-run-v1.json').read_text());reports={}
 if manual.get('human_attestation') is not False or manual.get('reviewed_actual_replies')!=1200:raise ValueError('Explicit complete direct reading of four new captures required')
 spec=importlib.util.spec_from_file_location('initial_grounded_assessment','scripts/record-grounded-initial-assessment-v1.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 refs=[json.loads(l) for l in Path(plan['heldout_references']).open()]
 for name,path,protocol in [('grounded-100',ROOT/'grounded-100',Path(plan['generation_protocols']['grounded-100'])),('regression-100',ROOT/'regression-100',Path(plan['generation_protocols']['regression-100'])),('core-source',CORE/'source',Path('data/core-english-development-v1/protocol-v2.json')),('core-trained',CORE/'trained',Path('data/core-english-development-v1/protocol-v2.json'))]:
  target=ROOT/(name+'-direct.json')
  if target.exists():raise FileExistsError('Immutable direct semantic assessment')
  m=manual['protocols'][name];rows=[json.loads(l) for l in (path/'turns.jsonl').open()];done=json.loads((path/'completion.json').read_text());cases=json.loads(protocol.read_text())['conversations'];session=json.loads((path/'session.json').read_text());passed=m['correct_turns'];judgments=[];slices=collections.defaultdict(lambda:[0,0]);em=[];f1=[]
  if not m['all300_actual_replies_read'] or len(rows)!=300 or not done['complete'] or sha(path/'turns.jsonl')!=m['capture_sha256'] or done['turns_sha256']!=m['capture_sha256']:raise ValueError('Completed directly read exact capture binding required')
  if any(k not in {f'{c["id"]}.{t}' for c in cases for t in (1,2,3)} for k in passed):raise ValueError('Unknown manually graded turn')
  for i,c in enumerate(cases):
   decisions=[]
   for t in (1,2,3):
    row=rows[i*3+t-1];key=f'{c["id"]}.{t}'
    if (row['conversation'],row['turn'],row['user'],row['success_criterion'])!=(c['id'],t,c['turns'][t-1]['user'],c['turns'][t-1]['success_criterion']):raise ValueError('Graded request/protocol differs')
    correct=key in passed
    if correct and (not passed[key] or not row['response']['text'].strip()):raise ValueError('Explicit positive reason and actual nonempty reply required')
    decision=dict(turn=t,correct=correct,partially_correct=key in m.get('partial_turns',{}),reason=passed[key] if correct else m['default_failure_reason'],actual_turn_row_sha256=digest(row))
    if key in m.get('partial_turns',{}):decision['reason']=m['partial_turns'][key]
    if key in m.get('specific_failure_reasons',{}):decision['reason']=m['specific_failure_reasons'][key]
    if name=='grounded-100':
     e,f=module.auxiliary(row['response']['text'],[a['text'] for a in refs[i]['original_questions'][t-1]['answers']]);decision['auxiliary_normalized_exact_match']=e;decision['auxiliary_token_f1']=f;em.append(e);f1.append(f)
    decisions.append(decision);slices[c['category']][0]+=int(correct);slices[c['category']][1]+=1
   judgments.append(dict(conversation=c['id'],category=c['category'],actual_three_turn_replies_fully_read=True,human_attestation=False,review_mode='assistant_direct_review',session_correct=all(v['correct'] for v in decisions),turns=decisions))
  journal=ROOT/(name+'-direct-judgments.jsonl')
  with journal.open('x') as f:
   for r in judgments:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
  result=dict(creator='Navneet Prabhakar',complete=True,correct_sessions=sum(r['session_correct'] for r in judgments),total_sessions=100,correct_turns=len(passed),total_turns=300,correctness_fraction=len(passed)/300,partially_correct_turns=len(m.get('partial_turns',{})),by_slice={k:dict(correct_turns=v[0],total_turns=v[1]) for k,v in slices.items()},all_replies_directly_read=True,human_attestation=False,model_manifest_sha256=session['student']['model_manifest_sha256'],capture_sha256=sha(path/'turns.jsonl'),journal_sha256=sha(journal),manual_decisions_sha256=sha(decision_path),judgments=judgments,scope='Direct expert semantic assessment, unblinded/human_attestationfalse. Later turns judged against actual history, not automatically failed because earlier turns failed. No teacher repair/substitution, random population or causal claim. All cases/failures retained. GroundedQA is intermediate; authored coreEnglish and repeated regression are development, not untouched final acceptance.')
  if em:result.update(auxiliary_normalized_exact_match=sum(em)/300,auxiliary_token_f1=sum(f1)/300)
  target.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n');reports[name]={k:v for k,v in result.items() if k not in ('judgments','scope')}
 initial=json.loads((ROOT/'initial-grounded-100-direct.json').read_text());comparison=dict(creator='Navneet Prabhakar',complete=True,actual_replies_directly_read=1500,teacher_calls=0,initial_grounded=initial,post_training=reports,working_core_development_target=.75,core_development_target_reached=reports['core-trained']['correctness_fraction']>=.75,fresh_final_confirmation=False,full_project_complete=False,model_promoted=False)
 (ROOT/'direct-comparison.json').write_text(json.dumps(comparison,indent=2,sort_keys=True)+'\n');print(json.dumps({k:dict(correct_turns=v['correct_turns'],correct_sessions=v['correct_sessions']) for k,v in reports.items()},indent=2))
if __name__=='__main__':main()
