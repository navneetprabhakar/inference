"""Independent retained-lesson plan/trace checks; no generator/model import."""
import collections,hashlib,json,os,pathlib,sqlite3
os.nice(10);R=pathlib.Path(__file__).resolve().parents[2];D=R/'data/own-base-tool-session-extension-v1'
assert not(R/'runs/STOP').exists() and not(D/'STOP').exists()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.load(open(D/'candidate-manifest.json'));policy=json.load(open(D/'policy.json'));assert sha(D/'candidates.sqlite')==m['database']['sha256'] and sha(D/'policy.json')==m['policy_sha256'];src={x['doc_id']:x for x in json.load(open(D/'source-records.json'))};forms={x[0]:x for x in policy['train_forms']+policy['development_forms']};units={'mm':.001,'cm':.01,'m':1,'kg':1000,'g':1,'l':1000,'ml':1,'h':3600,'min':60};counts=collections.Counter()
def calc(op,a,b):return a+b if op=='add' else a-b if op=='subtract' else a*b if op=='multiply' else a/b
for did,raw,audit,adapted in sqlite3.connect(D/'candidates.sqlite').execute('select doc_id,original_lesson_json,audit_json,adapted_json from documents'):
 o=json.loads(raw);s=src[did];p=s['parameters'];_,text1,text2,k,x,y,op2,op3,k4,x4,y4=forms[s['family'].split('/')[1]]
 h=o['history'];users=[x['text'] for x in h if x['role']=='user'];assert users[:2]==[text1.format(**p),text2.format(**p)];calls=[x['call'] for x in h if 'call' in x];assert len(calls)==4
 v1=p['a']*units[x]/units[y] if k=='convert' else calc(x,p['a'],p['b']);v2=calc(op2,v1,p['b'] if k=='convert' else p['c']);v3=calc(op3,v2,p['d']);v4=v3*units[x4]/units[y4] if k4=='convert' else calc(x4,v3,p['b']);expected=[v1,v2,v3,v4]
 observations=o['observations'];assert [x['data']['result'] for x in observations]==expected;assert all(x['source']=='offline fixture' and x['ok'] for x in observations);assert [x['call_id'] for x in observations]==['c1','c2','c3','c4'];assert calls[1]['arguments']['a']==v1 and calls[2]['arguments']['a']==v2 and calls[3]['arguments'].get('value',calls[3]['arguments'].get('a'))==v3
 assert s['third_turn_mode']==2 and [x['permit_calls'] for x in o['policy']]==[True,True,False];assert str(p['a']+1) in h[-1]['text'] and 'not been recalculated or updated' in h[-1]['text'];assert len(json.loads(adapted))==3;counts[s['split']]+=1
assert dict(counts)=={'train':32,'exposed-development':8}
out=dict(state='PASS_independent_symbolic_retained_only',training_admitted=False,counts=dict(counts),candidate_manifest_sha256=sha(D/'candidate-manifest.json'),verifier_sha256=sha(pathlib.Path(__file__)),limitation='Retained lessons only; all third-turn recall variants failed frozen fit. No late-position coverage claim.');(D/'symbolic-verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
