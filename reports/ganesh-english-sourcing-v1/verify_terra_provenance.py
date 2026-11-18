"""Verify all CLI-authored candidate text against retained raw artifacts, plus request receipts."""
import collections,hashlib,json
from pathlib import Path
ROOT=Path.cwd();R=ROOT/'reports/ganesh-english-sourcing-v1';O=ROOT/'runs/ganesh-english-sourcing-v1/terra-cli'
rows=[json.loads(l) for l in (O.parent/'reviewed-candidates.jsonl').read_text().splitlines()];cli=[r for r in rows if 'generation' in r];models=collections.Counter();artifacts={}
for row in cli:
 g=row['generation'];p=ROOT/g['raw_artifact'];data=p.read_bytes()
 assert hashlib.sha256(data).hexdigest()==g['raw_sha256']
 assert g['requested_model']=='gpt-6.1-terra' and g['interface']=='codex exec'
 raw=next(c for c in json.loads(data)['conversations'] if c['group']==row['group'])
 expected=[dict(role=role,content=turn[role]) for turn in raw['turns'] for role in ('user','assistant')]
 assert row['messages']==expected,'Parent changed CLI-authored text'
 models[g['requested_model']]+=1;artifacts[str(p.relative_to(ROOT))]=g['raw_sha256']
usage=collections.Counter();completed=0;itemtypes=collections.Counter()
for p in O.glob('*.events.jsonl'):
 events=[json.loads(l) for l in p.read_text().splitlines()]
 assert any(e['type']=='turn.completed' for e in events),f'Incomplete CLI job: {p.name}'
 completed+=1
 for e in events:
  if 'item' in e:itemtypes[e['item']['type']]+=1
  if e['type']=='turn.completed':usage.update(e.get('usage',{}))
assert all(t in ('agent_message','reasoning') for t in itemtypes), 'Unexpected generator tool execution'
baseline=json.loads((R/'continuation-03-baseline.json').read_text())
lines=(O.parent/'reviewed-candidates.jsonl').read_bytes().splitlines()
assert [hashlib.sha256(l).hexdigest() for l in lines[:214]]==baseline['row_hashes']
report={'status':'pass','cli_candidates':len(cli),'model_requests':dict(models),'cli_version':'0.167.1','model_claim_scope':'Exact explicit CLI request and local catalog match; response events do not independently expose backend routing','raw_text_roundtrip_exact':True,'prior_214_rows_byte_identical':True,'completed_cli_calls':completed,'generator_item_types':dict(itemtypes),'aggregate_cli_usage':dict(usage),'selected_artifacts':artifacts,'training_admitted':False,'independent_release_review':False,'gcp_operations':False}
(R/'terra-provenance-receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='selected_artifacts'},indent=2))
