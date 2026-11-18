"""Checks raw CLI candidates without admitting or modifying corpus data."""
import argparse,collections,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('batch');p.add_argument('--revision',action='store_true');args=p.parse_args()
R=Path(__file__).resolve().parent;O=R.parents[1]/'runs/ganesh-english-sourcing-v1/terra-cli'
name=args.batch+('.revised' if args.revision else '.raw');data=json.loads((O/f'{name}.json').read_text());rows=data['conversations'];plan=json.loads((R/f'authoring-plan-{args.batch}.json').read_text())['scenario_groups_assigned_before_authoring'];expected={g:f for f,gs in plan.items() for g in gs}
assert len(rows)==len(expected) and len({r['group'] for r in rows})==len(rows)
lengths=collections.Counter();issues=[]
for r in rows:
 assert r['group'] in expected and r['family']==expected[r['group']]
 turns=r['turns'];lengths[len(turns)]+=1
 if not 4<=len(turns)<=8:issues.append([r['group'],'turn count outside4–8'])
 if sum(len(t['user'].split())+len(t['assistant'].split()) for t in turns)>380:issues.append([r['group'],'word budget exceeded'])
 if any(not t['user'].strip() or not t['assistant'].strip() for t in turns):issues.append([r['group'],'empty message'])
 q=r['recall_probe']
 if r['family']=='memory':
  if not q or not 1<=q['support_turn']<q['probe_turn']<=len(turns) or q['probe_turn']-q['support_turn']<3:issues.append([r['group'],'invalid delay'])
 if not r['author_review_notes'].strip():issues.append([r['group'],'missing self review'])
if len(lengths)<3 or max(lengths.values())>len(rows)//2:issues.append(['batch','insufficient turn-length variety'])
events=O/(args.batch+('.revision' if args.revision else '')+'.events.jsonl');eventrows=[json.loads(l) for l in events.read_text().splitlines()];types=collections.Counter(e.get('item',{}).get('type') for e in eventrows if 'item' in e)
if any(t not in ('agent_message','reasoning') for t in types):issues.append(['batch','unexpected tool item: '+str(dict(types))])
report={'batch':args.batch,'revision':args.revision,'requested_model':'gpt-6.1-terra','raw_sha256':hashlib.sha256((O/f'{name}.json').read_bytes()).hexdigest(),'conversation_count':len(rows),'lengths':dict(lengths),'issues':issues,'cli_item_types':dict(types),'turn_completed':any(e['type']=='turn.completed' for e in eventrows),'usage':[e.get('usage') for e in eventrows if e['type']=='turn.completed'],'training_admitted':False,'semantic_review':'not established by this script'}
(R/f'terra-{args.batch}{"-revised" if args.revision else ""}-structural.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
