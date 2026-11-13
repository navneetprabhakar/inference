"""Independent reducer checks using the reviewed teacher implementation."""
import copy, hashlib, importlib.util, itertools, json
from pathlib import Path
root=Path('runs/long-context-continuation-v2')
p=root/'reviewed_reducer.py'
spec=importlib.util.spec_from_file_location('reviewed_reducer',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def event(i,b,r,a,t=None):
 return dict(event_id=i,book_id=b,revision=r,action=a,title=t)
events=[event('a','one',5,'delete'),event('z','one',4,'upsert','stale'),event('e9','two',2,'upsert','lexical winner'),event('e10','two',2,'delete'),event('q','unknown',9,'upsert','ignored'),event('p','three',1,'upsert','retained')]
expected={'two':'lexical winner','three':'retained'}
checks=0
for perm in itertools.permutations(events):
 assert m.reduce_events(perm,{'one','two','three'})==expected;checks+=1
before=copy.deepcopy(events)
assert m.reduce_events(iter(events),{'one','two','three'})==expected;checks+=1
assert events==before;checks+=1
assert m.reduce_events(events+copy.deepcopy(events),{'one','two','three'})==expected;checks+=1
assert m.reduce_events(events,set())=={};checks+=1
assert m.reduce_events([event('z','one',6,'upsert','restored')]+events,{'one'})=={'one':'restored'};checks+=1
report={'implementation_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'independent_checks':checks,'permutation_checks':720,'displayed_regression_subcases':9,'result':'pass','limits':'Valid event schema and identical payloads for duplicate IDs, as stated in conversation.'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
