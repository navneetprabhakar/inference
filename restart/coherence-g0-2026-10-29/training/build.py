"""Deterministic candidate authoring. Does not admit data, train, or run a model."""
import json, hashlib, random
from collections import Counter
from pathlib import Path
from sentencepiece import SentencePieceProcessor
from frames import FRAMES
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
PRIV=ROOT/'private'
sp=SentencePieceProcessor(model_file=str(REPO/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
FAMILIES=['grounding','comprehension','clarification','correction','instructions','explanation','name_copy','time_copy']
STRUCTURES=['direct_followup','correction_repair','interruption_return','multi_constraint']
# Same serialization as phase-a-2026-10-28/build.py, copied rather than importing its side effects.
def serial(messages):
 ids=[sp.bos_id()]; mask=[0]
 for m in messages:
  user=m['role']=='user'
  a=sp.encode('User: '+m['content']+'\nAssistant:') if user else sp.encode(m['content'])+[sp.eos_id()]
  ids+=a; mask += [0 if user else 1]*len(a)
 return ids,mask

def save(p,x): p.write_text((json.dumps(x,ensure_ascii=False,separators=(',',':')) if p.name.startswith('review-all-') or p.name.startswith('review-second-') else json.dumps(x,ensure_ascii=False,indent=2))+'\n')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def turns(pairs):return [dict(role=role,content=content) for u,a in pairs for role,content in [('user',u),('assistant',a)]]
def checks(r):
 m=r['messages']; ids,mask=serial(m)
 r['ids']=ids;r['mask']=mask
 # At the last reply, reserve32 positions for every generated response, including this one.
 # User turn role serialization is independent of generated text, as in native serial().
 worst=1+sum(len(sp.encode('User: '+x['content']+'\nAssistant:')) for x in m if x['role']=='user')+32*(len(m)//2)
 replies=[len(sp.encode(x['content']))+1 for x in m if x['role']=='assistant']
 assert max(replies)<=32,(r['id'],'reply',replies)
 assert worst<=256,(r['id'],'context',worst)
 assert len(ids)<=256,(r['id'],'teacher-context',len(ids))
 r['validation']={'native_reply_lengths_including_eos':replies,'worst_generated_history_plus_last_reply':worst,'teacher_forced_positions':len(ids),'assistant_targets':sum(mask)}
 r['review_status']='PENDING_NONAUTHOR_FULL_SEMANTIC_REVIEW'
 r['turn_contracts']=[{'turn':i+1,'reference':a,'exact_match_required':exact,'requirements':['grammatical intelligible English','relevant requested act','supplied facts only','latest relevant state','no material unsupported claim'],'reference_is_not_exclusive':not exact} for i,((u,a),exact) in enumerate(zip(r.pop('_pairs'),r.pop('_exact')))]
 return r

def natural():
 out=[]
 for f in FAMILIES[:6]:
  for frame in FRAMES:
   for st in STRUCTURES:
    for aidx in range(5):
     p={'person':['Nora','Dara','Milo','Iris','Owen'][aidx], 'count':[3,5,7,9,11][aidx], 'time':['08:15','09:40','12:05','15:30','17:55'][aidx]}
     key,domain,prem,fq,fa,cq,ca,eq,ea,change,newfa,mq,resolve,resolved=[s.format(**p) for s in frame]
     # Refilling a single jar cannot have an unknown original count.
     if key=='refill':mq='When was the jar brought?';resolve='The jar was brought at '+p['time']+'.';resolved=p['time']
     # The key frame explicitly concerns a single spare key; do not turn that into an unknown count.
     if key=='keys':mq='When was the spare key left there?';resolve='It was left there at '+p['time']+'.';resolved=p['time']
     q,ans={'grounding':(fq,fa),'comprehension':(cq,ca),'clarification':(mq,'That information was not provided.'),'correction':('Under the latest arrangement, '+fq,newfa),'instructions':('Return only the requested value, without explanation. '+fq,fa),'explanation':(eq,ea)}[f]
     intro=prem+(' Correction: '+change if f=='correction' else '')
     pairs=[(intro+' '+q,ans)];exact=[False]
     if st=='direct_followup':
      if f=='clarification':pairs.append((resolve+' '+mq,resolved))
      elif f=='correction':pairs.append(('Before that correction, '+fq,fa))
      elif f=='comprehension':pairs.append((fq,fa))
      else:pairs.append((cq,ca))
      exact.append(False)
     elif st=='correction_repair':
      if f=='clarification':
       pairs.extend([(resolve+' '+mq,resolved),('Use the information I just supplied. '+mq,resolved)])
      elif f=='correction':
       pairs.extend([('For clarity, give the original answer. '+fq,fa),('Now give the updated answer. '+fq,newfa)])
      else:
       pairs.extend([(change+' Under the latest arrangement, '+fq,newfa),('Use the latest update, not the original arrangement. '+fq,newfa)])
      exact.extend([False,False])
     elif st=='interruption_return':
      label=['amber','violet','silver','green','orange'][aidx]
      pairs.extend([('Pause that topic. For a separate note, remember the label '+label+'.','The label is '+label+'.'),('What label did I just give?',label),('Back to the earlier topic. '+q,ans)])
      exact.extend([False,False,False])
     else:
      pairs[0]=(intro+' Keep the answer brief and do not add suggestions. '+q,ans)
      pairs.append((mq+" If it has not been supplied, reply exactly: Not provided",'Not provided'))
      exact.append(True)
     out.append(checks({'id':f+'-'+key+'-'+st+'-'+str(aidx),'family':f,'domain':domain,'scenario_family':key,'abstract_structure':st,'semantic_template_id':f+':'+key,'structure_variant':st,'slot_assignment':p,'slot_assignment_index':aidx,'answerability_negative_case':f=='clarification' or st=='multi_constraint','state_change_case':f=='correction' or st=='correction_repair','continuity_case':st=='interruption_return','_pairs':pairs,'_exact':exact,'messages':turns(pairs)}))
 return out

FIRST=['Al','Bo','Cy','Dee','Eve','Fay','Gus','Hal','Ira','Joy','Kai','Lea','Max','Nia','Omar','Pia','Quin','Rae','Sofia','Theodore','Amina','Benedict','Celia','Dominic','Elena','Farid','Greta','Hiro','Indira','Jules','Kiran','Lena','Mateo','Nolan','Opal','Priya','Rohan','Sana','Tariq','Uma']
LAST=['Li','Wu','Xu','Yu','Ng','Ho','Fox','Reed','Shaw','Bell','Cole','Dunn','Ford','Gray','Hill','King','Lane','Mills','Bennett','Christensen']
def copying():
 out=[]
 #40*20=800 unique names; base matching is20 diagonals repeated across first-name halves.
 #Novel-combination means outside a frozen component-introduction anchor set, NOT held out of training.
 nameanchors={(i,(i%20)) for i in range(40)}
 for f in FAMILIES[6:]:
  for i in range(800):
   st=STRUCTURES[(i//200)%4]
   if f=='name_copy':
    x,y=divmod(i,20); value=FIRST[x]+' '+LAST[y];alternate=FIRST[(x+13)%40]+' '+LAST[(y+7)%20]
    recombination=(x,y) not in nameanchors; segmentation=(x>=18 or y>=18)
    intro='The school craft club registration lists the name '+value+'.'
    q='Copy the registered name exactly, with no other words.'
    update='The registered name is now '+alternate+'.'
    pool={'first':FIRST[x],'last':LAST[y]}
   else:
    h,m=divmod(i,40);minute=(m*7)%60
    #even row numeric clock; odd row natural time components with varied spacing/length.
    value=f'{h:02d}:{minute:02d}' if i%2==0 else f'{(h%12) or 12}:{minute:02d} '+('am' if h<12 else 'pm')
    alternate=f'{(h+3)%24:02d}:{(minute+11)%60:02d}'
    recombination=m!=h%40;segmentation=i%2==1
    intro='The neighborhood shop pickup note gives the time '+value+'.'
    q='Copy the time exactly as written, with no other words.'
    update='The pickup time is now '+alternate+'.'
    pool={'hour_component':str(h),'minute_component':f'{minute:02d}','style':'clock' if i%2==0 else 'marked'}
   pairs=[(intro+' '+q,value)]
   if st=='direct_followup':pairs.append(('Please copy that same value once more, exactly.',value))
   elif st=='correction_repair':pairs.extend([(update+' '+q,alternate),('Copy only the latest value again.',alternate)])
   elif st=='interruption_return':pairs.extend([('For a separate household note, remember the word clean.','clean'),('What word was in that separate note?','clean'),('Return to the first note. '+q,value)])
   else:pairs.append(('Repeat the original value exactly: preserve spaces and punctuation; add no prefix.',value))
   out.append(checks({'id':f+'-'+str(i).zfill(4),'family':f,'domain':'school_clubs' if f=='name_copy' else 'retail','scenario_family':'registration_name' if f=='name_copy' else 'pickup_time','abstract_structure':st,'semantic_template_id':f,'structure_variant':st,'copy_value':value,'copy_updated_value':alternate if st=='correction_repair' else None,'copy_component_pool_assignment':pool,'recombination_from_frozen_component_anchors':recombination,'varied_length_or_segmentation':segmentation,'_pairs':pairs,'_exact':([True,False,False,True] if st=='interruption_return' else [True]*len(pairs)),'messages':turns(pairs)}))
 return out

def review_record(r):
 return {'id':r['id'],'family':r['family'],'structure':r['abstract_structure'],'pairs':[[m['content'],r['messages'][2*i+1]['content'],r['turn_contracts'][i]['exact_match_required']] for i,m in enumerate(r['messages'][::2])]}

def main():
 PRIV.mkdir(exist_ok=True)
 assert not (ROOT/'ADMITTED.json').exists(),'Admission requires versioned rebuild, not silent overwrite'
 rows=natural()+copying()
 assert len(rows)==6400 and len({r['id'] for r in rows})==6400
 save(PRIV/'candidates.json',rows)
 by={f:[r['id'] for r in rows if r['family']==f] for f in FAMILIES}
 #Fixed repeat subset across seeds, stratified by task and four structures.
 repeat={f:[r['id'] for st in STRUCTURES for r in [x for x in rows if x['family']==f and x['abstract_structure']==st][::4]] for f in FAMILIES}
 assert all(len(v)==200 for v in repeat.values())
 save(PRIV/'repeat-subset.json',repeat)
 for seed in [291102,291103]:
  decks={}
  for f in FAMILIES:
   rr=random.Random(str(seed)+':'+f);first=by[f].copy();last=repeat[f].copy();rr.shuffle(first);rr.shuffle(last);decks[f]=first+last
  schedule=[{'update':i+1,'conversation_ids':[decks[f][i] for f in FAMILIES]} for i in range(1000)]
  save(PRIV/f'schedule-{seed}.json',schedule)
  for f in FAMILIES:assert set(decks[f][:800])==set(by[f]) and set(decks[f][800:])==set(repeat[f])
 #Every label, packed into 16 bounded full-review shards; second review is deterministic20%.
 for j in range(16):save(PRIV/f'review-all-{j:02d}.json',[review_record(r) for r in rows[j*400:(j+1)*400]])
 second=[r for f in FAMILIES for st in STRUCTURES for r in [x for x in rows if x['family']==f and x['abstract_structure']==st][::5]]
 assert len(second)==1280
 save(PRIV/'second-review-ids.json',[r['id'] for r in second])
 second_ids={r['id'] for r in second};second_ordered=[r for r in rows if r['id'] in second_ids]
 for j in range(4):save(PRIV/f'review-second-{j:02d}.json',[review_record(r) for r in second_ordered[j*320:(j+1)*320]])
 #Review examples cover every function/frame/structure, assignment0 (960natural+8copy).
 representative=[r['id'] for r in rows if (r.get('slot_assignment_index')==0 or (r['family'].endswith('_copy') and int(r['id'].split('-')[-1])%200==0))]
 save(ROOT/'review-index.json',{'representative_ids':representative,'all_review_shards':16,'all_review_rows_per_shard':400,'second_review_count':len(second),'review_requirement':'Review all actual labels, including assignments not represented by this index. Index is navigation, not semantic admission.'})
 totals={'records':len(rows),'turns':sum(len(r['messages'])//2 for r in rows),'assistant_targets_one_pass':sum(r['validation']['assistant_targets'] for r in rows),'native_teacher_positions_one_pass':sum(len(r['ids']) for r in rows),'worst_generated_context':max(r['validation']['worst_generated_history_plus_last_reply'] for r in rows),'max_reply_tokens':max(max(r['validation']['native_reply_lengths_including_eos']) for r in rows),'family_counts':dict(Counter(r['family'] for r in rows)),'family_structure_counts':dict(Counter(r['family']+':'+r['abstract_structure'] for r in rows))}
 for f in FAMILIES[6:]:
  group=[r for r in rows if r['family']==f]
  totals[f]={'recombination':sum(r['recombination_from_frozen_component_anchors'] for r in group),'varied_segmentation':sum(r['varied_length_or_segmentation'] for r in group),'unique_values':len({r['copy_value'] for r in group}),'native_value_token_lengths':dict(Counter(len(sp.encode(r['copy_value'])) for r in group))}
 save(ROOT/'validation.json',totals)
 files=[p for p in PRIV.iterdir() if p.suffix=='.json']+[ROOT/'build.py',ROOT/'frames.py',ROOT/'validation.json',ROOT/'review-index.json']
 save(ROOT/'manifest.json',{'status':'CANDIDATES_PENDING_NONAUTHOR_REVIEW','files':{str(p.relative_to(ROOT)):digest(p) for p in files},'native_tokenizer_sha256':digest(REPO/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'),'serial_source':'restart/phase-a-2026-10-28/build.py','admitted':False})
 print(json.dumps(totals,indent=2))
if __name__=='__main__':main()
