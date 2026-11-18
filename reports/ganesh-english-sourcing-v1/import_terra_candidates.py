"""Preserve exact CLI-authored text after separate parent review; candidate only."""
import hashlib,json,pprint
from pathlib import Path
R=Path(__file__).resolve().parent;O=R.parents[1]/'runs/ganesh-english-sourcing-v1/terra-cli'
notes=json.loads((R/'terra-parent-review.json').read_text())
selected={'b13':'revised','b14':'revised','b15':'raw','b16':'raw','b17':'revised','b18':'revised','b19':'revised','b20':'revised'}
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
for batch,version in selected.items():
 rawpath=O/f'{batch}.{version}.json';rawsha=hashlib.sha256(rawpath.read_bytes()).hexdigest();convs=json.loads(rawpath.read_text())['conversations']
 structure=json.loads((R/f'terra-{batch}{"-revised" if version=="revised" else ""}-structural.json').read_text())
 if structure['issues'] or not structure['turn_completed'] or structure['raw_sha256']!=rawsha:raise ValueError('Raw CLI checks failed')
 assert set(notes[batch])=={c['group'] for c in convs}
 rows=[];reviews=[]
 for c in convs:
  turns=[(t['user'],t['assistant']) for t in c['turns']]
  gen={'interface':'codex exec','requested_model':'gpt-6.1-terra','cli_version':'0.167.1','raw_artifact':str(rawpath.relative_to(R.parents[1])),'raw_sha256':rawsha,'generator_self_review':'not independent','parent_review':'separate session; not independent release assessment'}
  rows.append(dict(family=c['family'],group=c['group'],turns=turns,source='Codex CLI gpt-6.1-terra',generation=gen))
  messages=[dict(role=role,content=text) for pair in turns for role,text in zip(('user','assistant'),pair)]
  review=dict(group=c['group'],messages_sha256=digest(messages),decision='shortlist',reviewer='Codex parent session full semantic review of CLI output; exact reviewer backend variant not verified',independent_review=False,training_admitted=False,assistant_turns_reviewed=len(turns),reviewed_turn_numbers=list(range(1,len(turns)+1)),rationale=notes[batch][c['group']],generator_self_review_notes=c['author_review_notes'],checks=[dict(turn=len(turns),expected_assistant_exact=turns[-1][1])])
  q=c['recall_probe']
  if c['group']=='writing_partner_twist_hidden':
   review['excluded_recall_annotation_reason']='Ending never supplied and final target does not explicitly state constraint; valid editing lesson, insufficient delayed-memory evidence.'
  elif q:
   s,p=q['support_turn'],q['probe_turn'];assert 1<=s<p<=len(turns) and p-s>=3
   review['recall_probe']=dict(last_supporting_turn=s,probe_turn=p,intervening_complete_turns=p-s-1,expected_assistant_exact=turns[p-1][1],probe_focus=q['focus'],annotation_scope='Parent-reviewed constraint/fact focus; contextual cues may reduce difficulty, not measured model performance.')
  reviews.append(review)
 (R/f'authored_source_{batch}.py').write_text('"""Exact Codex CLI gpt-6.1-terra output; no parent-authored text changes."""\nROWS = '+pprint.pformat(rows,width=110,sort_dicts=False)+'\n')
 (R/f'authored-review-{batch}.json').write_text(json.dumps(reviews,indent=2,ensure_ascii=False)+'\n')
 print(batch,len(rows),'candidate conversations',sum(len(r['turns']) for r in rows),'replies')
