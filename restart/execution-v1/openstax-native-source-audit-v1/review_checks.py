"""Read-only OpenStax preparation audit, simulated I/O controls only."""
import hashlib,importlib.util,json,pathlib,sys,tempfile,xml.etree.ElementTree as ET
from unittest.mock import patch
D=pathlib.Path(__file__).resolve().parent;S=D.parent/'openstax-native-source-preparation-v1'
spec=importlib.util.spec_from_file_location('acquire',S/'acquire.py');a=importlib.util.module_from_spec(spec);sys.modules['acquire']=a;spec.loader.exec_module(a)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
policy,pins=a.pins();inputs={str(S/n):sha(S/n) for n in ['acquire.py','check_offline.py','policy.json','code-pins.json','ready.json','offline-checks.json']}
# Reexecute original controls with only their output-directory handle redirected.
run=D/'offline-control-run';run.mkdir(exist_ok=True)
with patch.object(a,'HERE',run):exec(compile((S/'check_offline.py').read_bytes(),str(S/'check_offline.py'),'exec'),{'__name__':'__review_controls__'})
for path,h in inputs.items():assert sha(pathlib.Path(path))==h
# Independently reconstruct source tree correspondence and collection first-seen order.
tree_path=next(pathlib.Path(n) for n in policy['input_evidence_SHA256'] if n.endswith('tree.json'));tree=json.loads(tree_path.read_text());assert tree['sha']==policy['tree_SHA1'] and tree['truncated'] is False
index={x['path']:x for x in tree['tree']};all_ids=[];appearances={};book_specs=[]
for which in [1,2]:
 path=next(pathlib.Path(n) for n in policy['input_evidence_SHA256'] if n.endswith(f'volume{which}.collection.xml'));root=ET.fromstring(path.read_bytes());ids=[x.attrib['document'] for x in root.iter() if x.tag.endswith('}module') and 'document' in x.attrib];book_specs.append(ids)
 for pos,mid in enumerate(ids,1):
  if mid not in all_ids:all_ids.append(mid)
  appearances.setdefault(mid,[]).append((which,pos))
assert all_ids==[x['module_ID'] for x in policy['items']]
for item in policy['items']:
 t=index[item['native_path']];assert t['type']=='blob' and t['size']==item['expected_bytes'] and t['sha']==item['expected_Git_blob_SHA1']
 observed=[(1 if x['book_title']=='World History Volume 1, to 1500' else 2,x['one_based_module_position']) for x in item['collection_appearances']];assert observed==appearances[item['module_ID']]
# Concrete failure: code-pins registry can omit every code/policy entry and pins() passes.
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)/'empty-code-pins.json';p.write_text(json.dumps({'input_code_SHA256':{}}))
 with patch.object(a,'PINS',p):_,returned=a.pins();assert returned['input_code_SHA256']=={}
 blank_registry_accepts=True
# The policy remains independently pinned, even under omitted code pins.
assert sha(a.POLICY)==a.EXPECTED_POLICY_SHA
report={'status':'AUDIT_CONTROLS_AND_SOURCE_PINS_VERIFIED_BLOCKING_CODE_PIN_REGISTRY_GAP','baseline_offline_cases':json.loads((run/'offline-checks.json').read_text())['case_count'],'source_unique_modules':len(all_ids),'source_collection_appearances':sum(map(len,book_specs)),'source_expected_bytes':sum(x['expected_bytes'] for x in policy['items']),'source_body_reservations':sum(x['body_cap'] for x in policy['items']),'all162_tree_sizes_blob_ids_and_order_rechecked':True,'empty_code_registry_accepted':blank_registry_accepts,'input_hashes':inputs,'no_original_inputs_modified':all(sha(pathlib.Path(n))==h for n,h in inputs.items()),'network_requests':0,'actual_acquisition_launched':False,'global_ledger_writes':0}
(D/'checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
