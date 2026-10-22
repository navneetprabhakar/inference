import importlib.util,hashlib,json,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'hansard-question-group-preparation-v2'
spec=importlib.util.spec_from_file_location('candidate_core',P/'core.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
N=[]
def test(name,t,fn):
 p=m.segment(t);assert ''.join(x['raw_text'] for x in p)==t
 for x in p:assert sha_bytes(t.encode()[x['UTF8_start']:x['UTF8_end']])==x['raw_SHA256']
 assert fn(p),name;N.append(name)
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def gs(p):return [x for x in p if x['kind']=='QUESTION_ANSWER_GROUP']
q='Lord Ash: To ask why.\n\nLord Birch: Because é🙂.\n\n'
test('two_departments_replace_context_not_merge_answers','Home Office\n\n'+q+'Ministry of Justice\n\n'+q,lambda p:[x['department_context']['label'] for x in gs(p)]==['Home Office','Ministry of Justice'])
test('context_propagates_subsequent_question_groups','Home Office\n\n'+q+q,lambda p:len(gs(p))==2 and all(x['department_context']['label']=='Home Office' for x in gs(p)))
test('unknown_after_supported_remains_ambiguous_not_new_department','Home Office\n\n'+q+'Department of Fiction\n\n'+q,lambda p:any(x['kind']=='HELD_AMBIGUOUS_HEADING_OWNERSHIP' and 'Department of Fiction' in x['raw_text'] for x in p) and len([x for x in p if x['kind']=='DEPARTMENT_CONTEXT_SIDECAR'])==1)
test('nonblank_before_department_not_detached',q.rstrip()+'\nMinistry of Justice\n\n'+q,lambda p:not any(x['kind']=='DEPARTMENT_CONTEXT_SIDECAR' for x in p))
test('case_variant_not_guessed','home office\n\n'+q,lambda p:not any(x['kind']=='DEPARTMENT_CONTEXT_SIDECAR' for x in p))
test('shared_questions_and_URL_footnote_preserved','Home Office\n\nLord Ash: To ask why.\n\nLord Oak: To ask when.\n\nLord Birch: Because it works.\nhttps://example.org/é\n[1] Footnote.\n',lambda p:len(gs(p))==1 and gs(p)[0]['question_turns']==2 and 'https://' in gs(p)[0]['raw_text'])
cp=json.loads((P/'code-pins.json').read_text())['SHA256'];assert all(sha(Path(p))==v for p,v in cp.items());N.append('all24_exact_code_inventory_pins')
cmd=[sys.executable,'-B',str(P/'run.py'),'--profile-sha256','b3d82a330b8331aff8d6450fafe42232b7b966c40f70e511b9fe6a200d59f746','--code-pins-sha256','dd4db0513cd90842ab751d68b3953c5b21bf266875bef7e6054536b818498200'];r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode==0,r.stderr;N.append('actual_nonexecuting_static_preflight')
print(json.dumps({'status':'PASS_FOCUSED_SYNTHETIC_AND_STATIC_ONLY','independent_controls':len(N),'names':N,'code_inventory':len(cp),'source_body_reads':0,'retained_application':0},indent=2))
