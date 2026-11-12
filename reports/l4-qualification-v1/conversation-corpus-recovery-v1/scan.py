import json,sys,collections,re,hashlib
from pathlib import Path
sys.path.insert(0,str(Path('.').resolve()))
from cloud_training.conversation_overlap import normalize,user_sequence,rejection_reason,COURTESIES
root=Path('runs/ownbase-v2-sft');devprompts=set();devsequences=set()
for r in map(json.loads,(root/'general-admitted-v1/validation.jsonl').read_text().splitlines()):
 seq=user_sequence(r['messages']);devsequences.add(seq);devprompts.update(seq)
kept={json.loads(l)['id'] for l in (root/'general-admitted-v1/train.jsonl').open()};stats=collections.Counter();hits=collections.Counter();candidates=[]
include=re.compile(r'\b(organiz\w*|tidy\w*|clutter|writ\w*|creative|craft\w*|productiv\w*|learn\w*|study|hobb\w*|read\w*|drawing|paint\w*|presentation\w*|meeting\w*|notes|planning|plan|motivat\w*|focus|procrast\w*)\b',re.I)
exclude=re.compile(r'\b(sleep\w*|stress\w*|anxiety|depress\w*|weight|diet\w*|health\w*|exercise\w*|medicin\w*|illness\w*|budget\w*|invest\w*|stocks|loan\w*|insurance|law|legal|pets?|dogs?|cats?|food|recipes?|meals?|travel\w*|festival\w*|social media|software|apps?)\b',re.I)
for line in (root/'general/train.jsonl').open():
 r=json.loads(line)
 if r.get('source',{}).get('component')!='everyday-conversations':continue
 stats['original_everyday']+=1
 if r['id'] in kept:stats['retained_everyday']+=1;continue
 seq=user_sequence(r['messages']);overlap=set(seq)&devprompts;hits.update(overlap)
 if overlap and overlap<=COURTESIES:stats['removed_only_for_courtesy_overlap']+=1
 reason=rejection_reason(r['messages'],devprompts,devsequences)
 if reason:stats[reason]+=1;continue
 usertext=' '.join(seq)
 if not include.search(usertext) or exclude.search(usertext):stats['outside_practical_advice_screen']+=1;continue
 r['provenance']={'kind':'recovered_public_conversation_candidate','original_id':r['id'],'old_overlap':sorted(overlap),'training_admitted':False,'semantic_review':'pending'};candidates.append(r)
stats['screened_candidates_not_admitted']=len(candidates)
out=Path('runs/conversation-corpus-recovery-v1');out.mkdir(exist_ok=True);(out/'candidates.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in candidates))
report={'training_admitted':False,'stats':dict(stats),'most_common_old_overlaps':hits.most_common(10),'policy':'Only four explicit greetings exempted; exact full user sequence and all substantive prompt overlap still rejected. Original admitted corpus untouched. Practical-advice candidate subset requires semantic review.','candidate_sha256':hashlib.sha256((out/'candidates.jsonl').read_bytes()).hexdigest()}
Path('reports/l4-qualification-v1/conversation-corpus-recovery-v1/scan.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
