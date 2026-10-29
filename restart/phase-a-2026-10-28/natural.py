"""Primary-authored acceptance anchors and prospective natural-language candidate bank."""
import json,copy
from pathlib import Path
from build import ROOT,PRIVATE,save,serial
FAMS=['grounded_extraction','reading_comprehension','clarification','correction','instructions','simple_explanation']
# Public rubric anchors: states, expected acts and constraints are explicit.
BASE=[
 dict(family=FAMS[0],users=['The repair shelf has a copper lamp on the left and a blue radio on the right. Where is the radio?','Who owns the radio? The note does not name any owner.'],answers=['On the right.','The owner is not supplied.'],states=[{'radio_location':'right','lamp_location':'left'},{'radio_location':'right','radio_owner':None}],acts=['extract location','state missing information'],required=[['radio on right'],['owner unknown']],forbidden=[['invent a different location'],['invent an owner']],border=['On the right, where it is easy to reach.','The owner is not supplied.'],bad=['On the left.','Maya owns it.']),
 dict(family=FAMS[1],users=['A caretaker put a folder by an open window. Rain began coming through, so she moved it into a cabinet. Why did she move the folder?','Where is the folder now?'],answers=['She moved it because rain was coming through the window.','In the cabinet.'],states=[{'folder_location':'cabinet','move_reason':'rain through window'},{'folder_location':'cabinet'}],acts=['explain supplied cause','track location'],required=[['rain as cause'],['cabinet']],forbidden=[['invent damage or another motive'],['return old location']],border=['She wanted to keep it safe.','In the cabinet.'],bad=['The cabinet was getting wet.','By the window.']),
 dict(family=FAMS[2],users=['Write a reminder for my pottery meeting. I have not provided its time.','It is at 18:25. Now write the reminder.'],answers=['What time is the pottery meeting?','Your pottery meeting is at 18:25.'],states=[{'meeting':'pottery','time':None},{'meeting':'pottery','time':'18:25'}],acts=['ask relevant missing detail','write supported reminder'],required=[['ask time'],['pottery meeting','18:25']],forbidden=[['invent a time','ask an unrelated question'],['change time','add date']],border=['What time is it?','18:25'],bad=['Your pottery meeting is at 09:00.','Your pottery meeting is at 18:52.']),
 dict(family=FAMS[3],users=['Put the green basket on the desk. Restate that instruction.','Change only the destination to the bench. Restate the updated instruction.'],answers=['Put the green basket on the desk.','Put the green basket on the bench.'],states=[{'item':'green basket','destination':'desk'},{'item':'green basket','destination':'bench'}],acts=['restate instruction','apply correction'],required=[['green basket','desk','instruction'],['green basket','bench','instruction']],forbidden=[['change object'],['retain desk','change object']],border=['The green basket goes on the desk.','The bench.'],bad=['Put the green basket on the desk.','Put the green basket on the desk.']),
 dict(family=FAMS[4],users=['A toy is on the floor. A shelf is available. Give one step to clear the floor without throwing the toy away.','The shelf is unavailable now, but a box is available. Revise the step.'],answers=['Put the toy on the shelf.','Put the toy in the box.'],states=[{'item':'toy','available':'shelf','must_keep':True},{'item':'toy','available':'box','must_keep':True}],acts=['give constrained action','revise action'],required=[['toy retained','floor clear','shelf'],['toy retained','floor clear','box']],forbidden=[['discard toy','multiple steps'],['use unavailable shelf']],border=['Store it safely.','Use the box.'],bad=['Throw the toy away.','Put the toy on the shelf.']),
 dict(family=FAMS[5],users=['This note says a felt panel absorbs some sound, so less sound returns from the wall. Why does the echo become quieter?','Does the note say the panel creates extra sound?'],answers=['It absorbs some sound, so less sound returns from the wall.','No. The note says it absorbs some sound.'],states=[{'mechanism':'absorbs some sound','effect':'less reflected sound'},{'creates_extra_sound':False}],acts=['explain stated mechanism','answer grounded yes/no'],required=[['absorption','less returning sound'],['no','absorption']],forbidden=[['claim all sound disappears','invent mechanism'],['claim extra sound is created']],border=['The panel makes the room quieter.','No.'],bad=['The panel creates sound that cancels everything.','Yes, it makes more sound.'])]

def anchors():
 out=[]
 for base in BASE:
  for variant,grade,key in [('a','acceptable','answers'),('b','acceptable','answers'),('c','borderline','border'),('d','failure','bad')]:
   b=copy.deepcopy(base);users=b['users'].copy();answers=b[key].copy();states=b['states'].copy();acts=b['acts'].copy();required=b['required'].copy();forbidden=b['forbidden'].copy()
   if variant=='b':
    users+=['New topic: the notice says the reading room closes at 17:40. When does it close?','Return to the earlier task. Do we have any information about tomorrow’s weather?']
    answers+=['At 17:40.','No weather information was supplied.'];states += [{'reading_room_close':'17:40'},{'weather':None}];acts+=['switch topic','acknowledge absent information'];required += [['17:40'],['weather unknown']];forbidden += [['reuse previous task answer'],['invent forecast']]
   out.append(dict(id=f"anchor-{b['family']}-{variant}",family=b['family'],grade=grade,turns=[dict(user=u,assistant=a,state_after=st,expected_act=act,required=req,forbidden=forb,format='Natural concise answer; exact full time when given; no unsupported additions.') for u,a,st,act,req,forb in zip(users,answers,states,acts,required,forbidden)],review_note='Borderline examples require separate content/act grading. They are not accepted automatically. A correct time alone can be adequate as a minimal reminder when the meeting is unambiguous, but does not repair a failed clarification.'))
 save(ROOT/'acceptance-examples.json',out)
 lines=['# Acceptance examples —24 review anchors','', '12 acceptable,6 borderline,6 failures. Primary-authored, not independent human calibration. Never train on these anchors.','']
 for r in out:
  lines+=['## '+r['id']+' — '+r['grade'],'']
  for i,t in enumerate(r['turns']):
   lines += [f"**Turn {i+1}. User:** {t['user']}",f"**Assistant:** {t['assistant']}",f"Required act: {t['expected_act']}. Required content: {', '.join(t['required'])}. Prohibited: {', '.join(t['forbidden'])}.",f"State: `{json.dumps(t['state_after'])}`",'']
  lines+=[r['review_note'],'']
 (ROOT/'ACCEPTANCE_EXAMPLES.md').write_text('\n'.join(lines))
 return out

DOMAINS=['community library','garden club','theatre workshop','school art room','bicycle repair stall','music rehearsal room','neighbourhood pantry','craft group','museum office','volunteer kitchen','board-game club','book exchange','photography group','sewing room','community hall','sports equipment room','pottery studio','school reception','language club','dance studio','drawing class','shared workshop','reading circle','chess club','local archive','swimming club office','community greenhouse','small exhibition room','choir rehearsal','repair cafe','film club','youth centre','school library','neighbourhood meeting','ceramics class','shared home office','paper craft class','rowing club office','community storeroom','walking club']
OBJECTS=['folder','box','bag','basket','notebook','coat','parcel','painting']
LOCATIONS=['cabinet','table','shelf','bench','drawer','cupboard','desk','basket']
MATERIALS=['felt','foam','cloth','paper']

def final_candidates():
 rows=[]
 for f in FAMS:
  for j,domain in enumerate(DOMAINS):
   item=OBJECTS[j%8];old=LOCATIONS[j%8];new=LOCATIONS[(j+3)%8];other=LOCATIONS[(j+5)%8];color=['red','blue','green','yellow'][j%4];time=f'{9+j%10:02d}:{(j*11)%60:02d}';later=f'{10+j%10:02d}:{(j*11+7)%60:02d}';users=[];answers=[];contracts=[]
   if f=='grounded_extraction':
    users=[f"At the {domain}, the note says the {color} {item} is in the {old}. It gives no owner name. Where should I look for it?",'Does that note identify its owner?']
    answers=[f'In the {old}.','No owner is named.'];contracts=[dict(act='extract location',required=[old],prohibited=['unsupported location']),dict(act='unknown',required=['owner not supplied'],prohibited=['invent owner'])]
    extra=[(f"An update says it has moved to the {new}. Where should I look now?",f'In the {new}.',dict(act='update location',required=[new],prohibited=[old])),('Does the note say how much it costs?','No price is supplied.',dict(act='unknown',required=['price unknown'],prohibited=['invent price']))]
   elif f=='reading_comprehension':
    # All facts needed for the causal answer are explicitly given.
    users=[f"At the {domain}, a volunteer left a {item} on the {old}. The note says rain reached that spot, so the volunteer moved the {item} to the {new}. Why was it moved?",f'Where is the {item} at the end of that note?']
    answers=['It was moved because rain reached its original spot.',f'On the {new}.'];contracts=[dict(act='cause',required=['rain reached original spot'],prohibited=['invent cause']),dict(act='latest location',required=[new],prohibited=[old])]
    extra=[('Does the note say who owns it?','No owner is named.',dict(act='unknown',required=['owner unknown'],prohibited=['invent name'])),(f"The volunteer now moves it onto the {other}. Where is it?",f'On the {other}.',dict(act='update location',required=[other],prohibited=[new]))]
   elif f=='clarification':
    users=[f"I need a reminder for the {domain} meeting, but I have not provided the time. Ask me for the missing detail.",f'The meeting is at {time}. Please write the reminder now.']
    answers=['What time is the meeting?',f'The meeting is at {time}.'];contracts=[dict(act='ask time',required=['time question'],prohibited=['invent time']),dict(act='reminder',required=[time],prohibited=['invent date'])]
    extra=[(f"The time has changed to {later}. Update the reminder.",f'The meeting is at {later}.',dict(act='update time',required=[later],prohibited=[time])),('Do we know the meeting room?','No meeting room was supplied.',dict(act='unknown',required=['room unknown'],prohibited=['invent room']))]
   elif f=='correction':
    users=[f"For the {domain}, put the {color} {item} on the {old}. Restate the instruction.",f"Change only the destination to the {new}. Restate the revised instruction."]
    answers=[f'Put the {color} {item} on the {old}.',f'Put the {color} {item} on the {new}.'];contracts=[dict(act='instruction',required=[color,item,old],prohibited=['change item']),dict(act='correct instruction',required=[color,item,new],prohibited=[old])]
    extra=[(f"Now change only the destination to the {other}.",f'Put the {color} {item} on the {other}.',dict(act='correct instruction',required=[color,item,other],prohibited=[new])),(f"New topic: the door sign says closing time is {time}. What is the closing time?",f'{time}.',dict(act='topic switch',required=[time],prohibited=['repeat instruction']))]
   elif f=='instructions':
    users=[f"At the {domain}, a {item} is on the floor. The {old} is free. Give one step to clear the floor while keeping the {item}.",f"That spot is unavailable now. The {new} is free. Revise the step."]
    answers=[f'Put the {item} on the {old}.',f'Put the {item} on the {new}.'];contracts=[dict(act='one action',required=[item,old,'keep item'],prohibited=['discard item']),dict(act='revise action',required=[item,new,'keep item'],prohibited=[old])]
    extra=[(f"The {new} is unavailable too, but the {other} is free. What step works now?",f'Put the {item} on the {other}.',dict(act='revise action',required=[item,other],prohibited=[new,old])),('Does the note give the owner’s name?','No owner name is supplied.',dict(act='unknown',required=['owner unknown'],prohibited=['invent name']))]
   else:
    material=MATERIALS[j%4]
    users=[f"At the {domain}, a note says a {material} cover absorbs some sound, leaving less sound to return from the wall. Explain why the echo gets quieter using that note.",'Does the note say the cover creates extra sound?']
    answers=[f'The {material} absorbs some sound, so less sound returns from the wall.','No. It says the cover absorbs some sound.'];contracts=[dict(act='explain mechanism',required=['absorption','less reflected sound'],prohibited=['invent mechanism','all sound removed']),dict(act='grounded yes/no',required=['no','absorbs sound'],prohibited=['creates sound'])]
    extra=[('Does absorbing some sound mean the note guarantees total silence?','No. It says some sound is absorbed, not that all sound disappears.',dict(act='qualify claim',required=['not total silence'],prohibited=['total silence'])),(f"New topic: the next meeting starts at {time}. What time is that meeting?",f'{time}.',dict(act='topic switch',required=[time],prohibited=['continue sound explanation']))]
   for u,a,contract in extra[:j%3]:users.append(u);answers.append(a);contracts.append(contract)
   messages=[m for u,a in zip(users,answers) for m in [dict(role='user',content=u),dict(role='assistant',content=a)]];ids,mask=serial(messages)
   rows.append(dict(id=f'prospective-final-{f}-{j:02d}',family=f,scenario_cluster=f'final-{f}-{j:02d}',language_frame=f'final-{f}',domain=domain,messages=messages,contracts=contracts,ids=ids,mask=mask,review=dict(author='primary agent',semantic_label_review='Constructed from explicit facts; all six logical flows and40 substitutions per flow checked by deterministic invariants.',independent_review=False,status='CANDIDATE_NOT_RELEASED')))
 save(PRIVATE/'prospective-final-candidates.json',rows)
 return rows
if __name__=='__main__':
 assert not (ROOT/'freeze.json').exists();anchors();final_candidates();print('Prepared24 anchors and240 prospective final candidates; independent review pending.')
