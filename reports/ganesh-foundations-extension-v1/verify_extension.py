"""Verify separate extension candidates; never admits training or edits protected data."""
import argparse, collections, hashlib, importlib.util, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; P=Path(__file__).resolve().parent
V=ROOT/'reports/ganesh-english-sourcing-v1/scale-1000'
spec=importlib.util.spec_from_file_location('selection_verifier',V/'verify_selection.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
spec=importlib.util.spec_from_file_location('overlap',V/'check_selection_overlap.py');ov=importlib.util.module_from_spec(spec);spec.loader.exec_module(ov)
def read(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
def verify_root_review(row):
 ref=row['root_review_receipt'];path=ROOT/ref['path'];assert v.sha(path)==ref['sha256']
 entries=json.loads(path.read_text())['entries'];matches=[e for e in entries if e['group']==row['group']];assert len(matches)==1
 e=matches[0];assert e['messages_sha256']==v.digest(row['messages']) and e['decision']=='pass'
 assert e['reviewed_turn_numbers']==list(range(1,len(row['messages'])//2+1)) and e['rationale'].strip()
def verify_math(row):
 spec=importlib.util.spec_from_file_location('math_audit',P/'maths/arithmetic_audit.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 ref=row['arithmetic_audit_receipt'];path=ROOT/ref['path'];assert v.sha(path)==ref['sha256']
 entries=json.loads(path.read_text())['entries'];hits=[e for e in entries if e['group']==row['group']];assert len(hits)==1
 e=hits[0];assert e['messages_sha256']==v.digest(row['messages']);ops=module.A[row['group'][-2:]]
 assert len(ops)==len(e['turns'])==len(row['messages'])//2
 for i,(turn,checks) in enumerate(zip(e['turns'],ops)):
  assert turn['turn']==i+1 and turn['quoted_assistant_reply']==row['messages'][2*i+1]['content']
  assert turn['checks']==[module.check(*op) for op in checks] and turn['explanation_review'].strip()
def verify_supplemental(row):
 spec=importlib.util.spec_from_file_location('supplemental',P/'supplemental_arithmetic.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 ref=row['supplemental_arithmetic_receipt'];path=ROOT/ref['path'];assert v.sha(path)==ref['sha256']
 entries=json.loads(path.read_text())['entries'];hits=[e for e in entries if e['group']==row['group']];assert len(hits)==1
 assert hits[0]==module.entry(row,v.digest)
def verify(rows):
 assert v.sha(P/'initial-contract.json')=='3e8b8c3e16fe4fb115a1a63f8b4a13cc2557e4170b72f1806f3db37b6eeadd33', 'Initial scope/baseline changed'
 contract=json.loads((P/'initial-contract.json').read_text())
 for path,expected in contract['protected_hashes'].items():assert v.sha(ROOT/path)==expected, 'Protected payload changed'
 assert rows and len({r['group'] for r in rows})==len(rows)
 for row in rows:
  assert all(set(m)=={'role','content'} and isinstance(m['content'],str) for m in row['messages'])
  v.verify_new(row);v.verify_full_content(row);v.verify_memory(row,ROOT);verify_root_review(row)
  assert row['curriculum_track'] in ('maths','decisions','orchestration')
  if row['curriculum_track']=='maths':verify_math(row)
  else:verify_supplemental(row)
  assert row.get('training_admitted') is False
 stats=v.native(rows)
 comparators=[];bound={}
 for name in [*ov.EXPOSED,'runs/ganesh-english-sourcing-v1/scale-1000/reviewed-1000-v1.jsonl']:
  path=ROOT/name;bound[name]=v.sha(path);comparators.extend((name,r.get('group',r.get('id')),ov.fingerprint(r)) for r in read(path) if 'messages' in r)
 count=len(comparators);exact=[];near=[]
 for row in rows:
  text,sh=ov.fingerprint(row)
  for name,group,(other,osh) in comparators:
   if text==other:exact.append([row['group'],group,name])
   if min(len(sh),len(osh))/max(1,max(len(sh),len(osh)))<.35:continue
   score=len(sh&osh)/max(1,len(sh|osh))
   if score>=.35:near.append({'group':row['group'],'other':group,'path':name,'fivegram_jaccard':score})
  comparators.append(('extension',row['group'],(text,sh)))
 assert not exact, 'Exact conversation duplicate'
 assert not near, 'Near-overlap requires separate review before selection'
 stats.update(exposed_comparators=count,comparator_hashes=bound,exact_duplicates=exact,near_flags=near,training_admitted=False,model_evaluated=False,positive_tool_training=False,protected_payloads_unchanged=True)
 return stats
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('selection');ap.add_argument('--receipt',required=True);a=ap.parse_args();path=Path(a.selection);stats=verify(read(path));stats['payload_sha256']=v.sha(path);Path(a.receipt).write_text(json.dumps(stats,indent=2)+'\n');print(json.dumps(stats,indent=2))
