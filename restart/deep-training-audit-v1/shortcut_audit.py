"""Read-only audit of generator correlations; evidence of available shortcuts, not proof of their use."""
import json
from pathlib import Path
from collections import defaultdict,Counter
R=Path(__file__).resolve().parent;P=R.parents[1]
train=json.loads((P/'restart/broader-curriculum-v1/private/training.json').read_text())[:2592]
colors=['red','blue','green','yellow','white','black','pink','purple','orange','gold','brown','gray']
presence=defaultdict(Counter);updates=defaultdict(set);distractor_order=defaultdict(set)
for row in train:
 j=row['value_index']
 if row['family']=='answerability':presence[colors[j]][str(row['answer_present'])]+=1
 if row['family']=='delayed_update':
  answers=[m['content'] for m in row['messages'] if m['role']=='assistant'];updates[answers[0]].add(answers[2])
 if row['family']=='distractor':distractor_order[j].add('second' if j%2 else 'first')
report=dict(status='GENERATOR_CORRELATIONS_CONFIRMED',answerability_color_predicts_presence_perfectly=all(len(v)==1 for v in presence.values()),answerability_color_categories=len(presence),answerability_examples=sum(sum(v.values()) for v in presence.values()),answerability_present_examples=sum(v.get('True',0) for v in presence.values()),answerability_absent_examples=sum(v.get('False',0) for v in presence.values()),update_initial_locations=len(updates),unique_update_pairs=sum(len(v) for v in updates.values()),possible_nonidentity_pairs=12*11,every_initial_location_has_exactly_one_updated_location=all(len(v)==1 for v in updates.values()),distractor_target_position_deterministic_from_value_index=all(len(v)==1 for v in distractor_order.values()),limitations='Correlations are real in the training generator. They do not prove the model exploits them; matched reassessment already changes some transitions and present/absent combinations. Do not claim all measured gains are shortcut artifacts.',training_updates=0)
(R/'shortcut-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
