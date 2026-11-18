import collections,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
suite=json.loads((P/'suite.json').read_text());rows=[json.loads(l) for l in (P/'raw-results.jsonl').read_text().splitlines()]
assert [r['case_id'] for r in rows]==[c['id'] for c in suite],'Incomplete/out-of-order suite'
turns=[t for r in rows for t in r['turns']];expected=sum(len(c['turns']) for c in suite);assert len(turns)==expected
positive=[t for t in turns if t['expected_call']];negative=[t for t in turns if not t['expected_call']]
actions=[e for t in turns for e in t['events'] if e['kind']=='model_action'];calls=[e for t in turns for e in t['events'] if e['kind']=='tool_result']
report={'scenarios':len(rows),'intended_turns':expected,'positive_call_turns':len(positive),'no_call_turns':len(negative),'status_counts':dict(collections.Counter(t['status'] for t in turns)),'generated_actions':len(actions),'parsed_call_actions':sum(e['parsed']['kind']=='call' for e in actions),'broker_attempts':len(calls),'dispatched_calls':sum(not e['result'].get('blocked',False) for e in calls),'successful_tool_results':sum(e['result']['ok'] for e in calls),'positive_exact_call_sequence':sum(t.get('exact_call_match',False) for t in positive),'positive_structural_passes':sum(t.get('structural_pass',False) for t in positive),'no_call_structural_passes':sum(t.get('structural_pass',False) for t in negative),'fully_structural_workflows':sum(all(t.get('structural_pass',False) for t in r['turns']) for r in rows if r['kind']=='workflow'),'workflow_scenarios':sum(r['kind']=='workflow' for r in rows),'total_generation_seconds':sum(e['seconds'] for e in actions),'per_tool':{},'semantic_review':'pending; structural passes are not grounded-answer acceptance','training':False,'release_eligible':False,'raw_sha256':hashlib.sha256((P/'raw-results.jsonl').read_bytes()).hexdigest()}
for tool in json.loads((P/'tools.json').read_text())['tools']:
 ts=[t for r in rows if r['kind']=='crud' and r['case_id'].startswith(tool+'_') for t in r['turns']]
 report['per_tool'][tool]={'crud_cases':len(ts),'exact_call_sequences':sum(t.get('exact_call_match',False) for t in ts),'structural_passes':sum(t.get('structural_pass',False) for t in ts)}
(P/'summary.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
