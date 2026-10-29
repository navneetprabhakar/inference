import json,re,collections
from pathlib import Path
p=Path('restart/paired-fit-preparation-2026-10-29');results={};bad=[]; defects=[]
for n in ['fit-records','development']:
 rows=json.loads((p/'private'/f'{n}.json').read_text()); conflicts=collections.defaultdict(set);counts=collections.Counter(); collisions=collections.Counter()
 for r in rows:
  s=r['scenario'];msgs=r['messages'];f=s['family'];u=msgs[0]['content'];ans=[m['content'] for m in msgs if m['role']=='assistant'];item=s['item']
  # Extract actual rendered target facts rather than call the shared scenario oracle.
  if f=='clarification':
   expected=['What time is the meeting?' if 'time'==s['slot'] else 'Where is the meeting?', msgs[2]['content'].split(' Now write the reminder.')[0]]
  else:
   if f in ['name','missing']:
    pats=[rf'{item}:[^.]*?owner ([A-Z][a-z]+ [A-Z][a-z]+|not supplied)',rf'The {item} is [^.]*?with owner ([A-Z][a-z]+ [A-Z][a-z]+|not supplied)',rf'The {item} belongs to ([A-Z][a-z]+ [A-Z][a-z]+)',rf'The owner of the {item} is (not supplied)']
   elif f=='time':pats=[r'Meeting: (\d\d:\d\d)',r'The meeting is at (\d\d:\d\d)']
   elif f=='location':pats=[rf'{item}:[^.]*?on the ([a-z]+)',rf'The {item} is [^.]*?on the ([a-z]+)']
   else:pats=[rf'{item}: ([a-z]+)',rf'The {item} is ([a-z]+)']
   hits=[m.group(1) for pat in pats if (m:=re.search(pat,u))];val=hits[0] if hits else None
   if val=='not supplied':val='Unknown'
   if f=='format' and 'exactly one sentence' in u:val=f'The {item} is {val}.'
   expected=[val]
   if f=='state':
    m=re.search(rf'Correction: the {item} is ([a-z]+), not ([a-z]+)',msgs[2]['content']);assert m and m.group(2)==val
    expected.extend([m.group(1),m.group(1)])
  if expected!=ans:bad.append((n,r['id'],expected,ans))
  key=tuple(m['content'] for m in msgs if m['role']=='user');conflicts[key].add(tuple(ans));counts[f]+=1
  if r['scope']=='single' and any(q in u for q in ['two belongings','two objects','both objects']):defects.append({'view':n,'id':r['id'],'query':u})
  if f in ['distractor','state']:
   collisions[f+'-initial-equal']+=s['color']==s['other_color'];collisions[f+'-final-equal']+=s['new_color']==s['new_other_color']
 results[n]={'family_counts':dict(counts),'conflicting_duplicate_prompts':sum(len(v)>1 for v in conflicts.values()),'same_value_cases':dict(collisions)}
print(json.dumps({'extracted_reference_errors':bad,'stats':results,'single_scope_two_object_defect_count':len(defects),'defect_examples':defects[:8]},indent=2))
Path('restart/paired-fit-preparation-2026-10-29/successor-semantic-evidence.json').write_text(json.dumps({'extracted_reference_errors':bad,'stats':results,'single_scope_two_object_defects':defects},indent=2)+'\n')
