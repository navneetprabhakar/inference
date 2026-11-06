"""Bind final family coverage to custody; no protected content read."""
import collections,hashlib,json,pathlib,sqlite3
R=pathlib.Path(__file__).resolve().parents[2];D=R/'data/own-base-tool-review-v1';V=R/'data/own-base-tool-candidates'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert not(R/'runs/STOP').exists() and not(D/'STOP').exists()
m=json.load(open(V/'candidate-manifest.json'));assert sha(V/'candidates.sqlite')==m['database']['sha256']
for p,h in m['code_and_protocol'].items():assert sha(R/p)==h
ex=set(json.load(open(V/'custody.json'))['excluded_doc_ids']);con=sqlite3.connect(f'file:{V}/candidates.sqlite?mode=ro',uri=True);con.row_factory=sqlite3.Row;selected={};counts=collections.defaultdict(collections.Counter);families=collections.defaultdict(set);signatures=collections.defaultdict(set);pairs=collections.defaultdict(set)
questions={'missing_divisor':'What number should I divide by?','missing_start':'What was the starting quantity?','missing_target':'Which unit should I convert to?','missing_source':'What is the original unit?'}
for row in con.execute('select * from documents'):
 d=dict(row);o=json.loads(d['original_lesson_json']);mode=d['family'].split('/')[1];h=o['history']
 if mode in questions:assert h[1]==dict(role='assistant',text=questions[mode]) and o['policy'][0]['permit_calls'] is False and h[2]['role']=='user'
 if d['doc_id'] in ex:continue
 key=(d['split'],d['family']);rank=hashlib.sha256(('tool-review-v1|'+d['doc_id']).encode()).hexdigest()
 if key not in selected or rank<selected[key][0]:selected[key]=(rank,d)
 c=counts[d['split']];c['lessons']+=1;c['rows']+=d['rows'];c['targets']+=d['target_tokens'];families[d['split']].add(d['family'])
 if d['first_call_signature']:signatures[d['split']].add(d['first_call_signature'])
 if mode=='paired_observation':pairs[(d['split'],h[0]['text'],d['first_call_signature'])].add(o['observations'][0]['data']['result'])
assert not families['train']&families['exposed-development'];assert not signatures['train']&signatures['exposed-development']
selection=json.load(open(D/'custody-selection.json'));assert selection['custody_sha256']==sha(V/'custody.json');assert selection['sample_sha256']==sha(D/'custody-family-samples.jsonl');assert set(selection['ids'])=={d['doc_id'] for _,d in selected.values()}
out=dict(state='passed_custody_eligible_family_selection_not_admitted',training_admitted=False,counts=dict(counts),families={s:len(f) for s,f in families.items()},observational_pair_groups=sum(len(v)>=2 for v in pairs.values()),family_overlap=0,nonnull_first_signature_overlap=0,custody_sha256=sha(V/'custody.json'),selection_sha256=sha(D/'custody-selection.json'),source_pins_unchanged=True)
(D/'custody-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
