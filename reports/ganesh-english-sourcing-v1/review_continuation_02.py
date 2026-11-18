"""Persist full author second-pass notes. Exact checks bind evidence, not an independent quality verdict."""
import hashlib,importlib.util,json
from pathlib import Path
R=Path(__file__).resolve().parent
notes=json.loads((R/'review_notes_02.json').read_text())
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
for batch,judgments in notes.items():
 spec=importlib.util.spec_from_file_location(batch,R/f'authored_source_{batch}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 assert {x['group'] for x in m.ROWS}==set(judgments)
 out=[]
 for row in m.ROWS:
  turns=row['turns'];note=judgments[row['group']]
  messages=[dict(role=role,content=text) for pair in turns for role,text in zip(('user','assistant'),pair)]
  r=dict(group=row['group'],messages_sha256=digest(messages),decision='shortlist',reviewer='Codex author second semantic pass',independent_review=False,training_admitted=False,assistant_turns_reviewed=len(turns),reviewed_turn_numbers=list(range(1,len(turns)+1)),rationale=note[0],checks=[{'turn':len(turns),'expected_assistant_exact':turns[-1][1]}])
  if len(note)>1:
   support,probe=note[1:3];assert 1<=support<probe<=len(turns)
   r['recall_probe']=dict(last_supporting_turn=support,probe_turn=probe,intervening_complete_turns=probe-support-1,expected_assistant_exact=turns[probe-1][1],probe_focus=note[3],annotation_scope='Author-assessed supporting exchange for named focus only; other cues and repeated constraints can lower difficulty. Not model evaluation.')
  out.append(r)
 (R/f'authored-review-{batch}.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
 print(batch,len(out),'reviewed conversations',sum(x['assistant_turns_reviewed'] for x in out),'assistant turns')
