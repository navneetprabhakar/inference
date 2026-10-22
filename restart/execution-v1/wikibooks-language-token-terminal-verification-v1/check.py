import importlib.util,pathlib,json,hashlib
P=pathlib.Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('v',P/'verify.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v);checks=[]
def check(n,b):
 assert b,n;checks.append(n)
x=list(v.windows('a'*1024+'b'*40));check('eligible40char_tail_preserved',len(x)==3 and x[-1][4] and x[-1][2]-x[-1][1]==40)
x=list(v.windows('a'*1024+'b'*39));check('39char_tail_explicit_skip',not x[-1][4] and x[-1][5]=='fewer_than_40_alphabetic_characters')
x=list(v.windows('1234'));check('whole_always_scored_even_short',x[0][4] and not x[1][4]);check('unicode_codepoints_not_utf8_offsets',list(v.windows('é'*1025))[-1][1:3]==(1024,1025));check('unicode_alphabetics',list(v.windows('字'*40))[-1][4]);check('blank_whole_preserved',list(v.windows(''))[0][1:5]==(0,0,0,True));check('exactwidth_no_phantom_tail',len(list(v.windows('a'*1024)))==2);check('projection_hash_distinguishes_raw',v.digest(b'a\nb')!=v.digest(b'a b'))
r={'status':'PASS','checks':checks,'count':len(checks),'verifier_SHA256':hashlib.sha256((P/'verify.py').read_bytes()).hexdigest()};(P/'prepared-checks.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
