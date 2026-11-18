"""Read-only corpus audit plus compact evidence; never accesses frozen release text/cloud."""
import collections,hashlib,importlib.util,json,statistics,unicodedata
from pathlib import Path
R=Path(__file__).resolve().parent;ROOT=R.parents[1];OUT=ROOT/'runs/ganesh-english-sourcing-v1'
def norm(s):return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())
raw=(OUT/'reviewed-candidates.jsonl').read_bytes().splitlines();rows=[json.loads(x) for x in raw]
baseline=json.loads((R/'continuation-baseline.json').read_text())
assert [hashlib.sha256(x).hexdigest() for x in raw[:baseline['sessions']]]==baseline['row_hashes'], 'Existing candidate rows changed'
reviews=[];lengths=[]
for batch in ('b03','b04','b05','b06','b07'):
 reviews.extend(json.loads((R/f'authored-review-{batch}.json').read_text()))
 spec=importlib.util.spec_from_file_location(batch,R/f'authored_source_{batch}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 lengths.extend(len(x['turns']) for x in m.ROWS)
answers=[m['content'] for row in rows for m in row['messages'] if m['role']=='assistant']
c=collections.Counter(norm(x) for x in answers)
probes=[r['recall_probe'] for r in reviews if 'recall_probe' in r]
assert len(reviews)==80 and len(probes)==40
family=json.loads((R/'overlap-check.json').read_text())['family_target_positions']
checks={'status':'local_consistency_pass_not_semantic_independence','previous_54_rows_byte_identical':True,'new_scenarios':len(reviews),'new_assistant_turns_reviewed':sum(x['assistant_turns_reviewed'] for x in reviews),'new_scenario_turn_counts':dict(collections.Counter(lengths)),'annotated_memory_probes':len(probes),'intervening_turn_histogram':dict(collections.Counter(p['intervening_complete_turns'] for p in probes)),'assistant_turns_all_candidates':len(answers),'unique_normalized_assistant_texts':len(c),'repeated_text_excess':sum(n-1 for n in c.values()),'repeated_assistant_texts':[(text,n) for text,n in c.most_common() if n>1],'family_target_positions':family,'correction_memory_target_fraction':(family['correction']+family['memory'])/sum(family.values()),'candidate_payload_sha256':hashlib.sha256((OUT/'reviewed-candidates.jsonl').read_bytes()).hexdigest(),'independent_review':False,'training_admitted':False,'cloud_operations':False,'limitations':['Author review and exact-answer checks cannot establish independent semantic quality','Memory delay is annotated turns, not measured Ganesh performance or a 3K/4K claim','Six-turn state-tracking patterns and vocabulary detours are overrepresented in this continuation; do not expand by name/object substitution','Answers are deliberately brief; this packet alone cannot teach broad fluent English conversation','Lexical checks cover only 172 exposed historical rows, not full semantic/source decontamination','No new held-out development set or positive tool curriculum is admitted']}
(R/'continuation-audit.json').write_text(json.dumps(checks,indent=2,ensure_ascii=False)+'\n');print(json.dumps(checks,indent=2,ensure_ascii=False))
