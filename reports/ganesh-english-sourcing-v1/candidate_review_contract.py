"""Content-bound review consistency, not automated semantic quality approval."""
import hashlib,json

def digest(value):
 return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def validate_review(row,review):
 turns=row['turns']
 if not turns or any(len(t)!=2 or any(not isinstance(s,str) or not s.strip() for s in t) for t in turns):
  raise ValueError('Conversation must contain nonempty user/assistant pairs')
 messages=[dict(role=role,content=text) for pair in turns for role,text in zip(('user','assistant'),pair)]
 if review['group']!=row['group'] or review['messages_sha256']!=digest(messages):
  raise ValueError('Review does not bind the exact scenario and content')
 if review['decision']!='shortlist' or review['assistant_turns_reviewed']!=len(turns):
  raise ValueError('Conversation not fully shortlisted')
 if review['independent_review'] is not False or review['training_admitted'] is not False:
  raise ValueError('Author review cannot claim independent review or admission')
 if 'reviewed_turn_numbers' in review and review['reviewed_turn_numbers']!=list(range(1,len(turns)+1)):
  raise ValueError('Review turn coverage incomplete')
 for check in review.get('checks',[]):
  index=check['turn']
  if not isinstance(index,int) or not 1<=index<=len(turns) or turns[index-1][1]!=check['expected_assistant_exact']:
   raise ValueError('Reviewed probe does not match the target')
 if 'recall_probe' in review:
  p=review['recall_probe'];support=p['last_supporting_turn'];probe=p['probe_turn']
  if not (isinstance(support,int) and isinstance(probe,int) and 1<=support<probe<=len(turns)):
   raise ValueError('Invalid recall evidence positions')
  if p['intervening_complete_turns']!=probe-support-1 or turns[probe-1][1]!=p['expected_assistant_exact']:
   raise ValueError('Recall evidence does not match content or delay')
 return messages
