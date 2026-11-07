"""Synthetic regression cases; no source history read."""
from grouping_draft import propose,fingerprint

def row(identifier,task,status,user,reply):
 h=[dict(role='user',text='Hi!'),dict(role='assistant',text='Hello!'),dict(role='user',text=user),dict(role='assistant',text=reply)]
 return dict(doc_id=identifier,task_key=task,status=status,history=h,history_sha256=fingerprint(h),semantic_review_sha256='reviewed-fixture')
a=row('a','reschedule-existing-appointment','old_train','Move the dentist appointment to Tuesday.','The requested new day is Tuesday.')
b=row('b','explain-how-to-schedule','old_train','What steps help arrange a first visit?','Call the reception desk and ask for availability.')
g=propose([a,b],salt='fixture');assert len(g)==2 and all(x['proposed_split']=='train' for x in g)
c=dict(b,doc_id='c',task_key=a['task_key'],status='unknown');assert len(propose([a,c],salt='fixture'))==1 and propose([a,c],salt='fixture')[0]['proposed_split']=='quarantine'
for status in ['historical_holdout','excluded']:
 c=dict(a,doc_id='c',status=status);assert propose([a,c],salt='fixture')[0]['proposed_split']=='quarantine'
assert a['history'][0]['text']=='Hi!' # No greeting deletion in full training history.
print('5 grouping protection/greeting fixtures PASS; no corpus reads')
