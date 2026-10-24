"""Summarize direct manual review of the 30 supplemental basic-fact responses."""
import json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent;V=R/'private'
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
freeze=read(R/'knowledge-freeze.json');assert sha(V/'knowledge-bank.json')==freeze['bank_sha256'] and sha(R/'knowledge_check.py')==freeze['script_sha256']
passed={('retained','knowledge-4',2)};judgments=[];metrics={}
for model in ['retained','rejected']:
 rows=read(V/(model+'-knowledge-responses.json'));assert len(rows)==15
 assert sha(V/(model+'-knowledge-responses.json'))==read(R/'knowledge-result.json')['models'][model]['raw_responses_sha256']
 for row in rows:
  correct=(model,row['id'],row['turn']) in passed
  judgments.append(dict(model=model,id=row['id'],turn=row['turn'],factual_correct=correct,reason='The single letter names the correct oxygen symbol; lowercase accepted for factual identity, capitalization defect retained.' if correct else 'Incorrect or absent answer to the elementary fact question; not a valid paraphrase.'))
 metrics[model]=dict(correct=sum(j['factual_correct'] for j in judgments if j['model']==model),turns=15,fully_correct_conversations=0,conversations=5,eos=sum(r['eos'] for r in rows),empty_responses=sum(not r['response'].strip() for r in rows))
save(V/'knowledge-manual-judgments.json',judgments)
save(R/'knowledge-review.json',dict(status='BASIC_FACT_CHECK_FAIL_BOTH',models=metrics,primary_directly_reviewed_answers=30,judge='Primary manual semantic review; not blind or teacher judged.',manual_judgments_sha256=sha(V/'knowledge-manual-judgments.json'),case_note='One lowercase single-letter chemical-symbol answer accepted for factual identity but capitalization remains defective. A single correct response does not establish robust knowledge.',limitations='15 elementary questions, not a representative knowledge benchmark. Added after the primary supplied-fact review, frozen before its own inference, kept separate from the primary 60-turn totals. Potential overlap with older teacher-generated data is not certified.',training_updates=0,promotion=False))
print(json.dumps(read(R/'knowledge-review.json'),indent=2))
