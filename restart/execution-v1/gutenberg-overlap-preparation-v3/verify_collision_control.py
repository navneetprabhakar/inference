import hashlib,json,pathlib,subprocess,tempfile
P=pathlib.Path(__file__).resolve().parent;E=P.parent;program=E.parents[1]/'restart/corpus-audit-v1/containment';text='one two three four five six seven eight nine ten eleven twelve'
results={}
with tempfile.TemporaryDirectory() as td:
 d=pathlib.Path(td);(d/'input').write_text(text+'\n')
 for name,pid in [('collision',1),('disjoint',1000000)]:
  (d/'protected').write_text(str(pid)+'\t'+text+'\n');subprocess.run([str(program),str(d/'protected'),str(d/'input'),str(d/'out')],check=True,capture_output=True);results[name]=(d/'out').read_text().splitlines()
assert not results['collision'] and len(results['disjoint'])==1
result={'status':'PASS_OFFLINE_CPP_ID_COLLISION_REPRODUCED_AND_DISJOINT_ID_CATCHES','same_numeric_ID_exemption_reproduced':True,'disjoint_ID_catches_exact12word_protection':True,'program_SHA256':hashlib.sha256(program.read_bytes()).hexdigest(),'results':results,'network_requests':0}
(P/'collision-control.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
