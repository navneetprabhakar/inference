from pathlib import Path
import sys,json,subprocess,hashlib
O=Path(__file__).resolve().parent;B=O.parent;P=B/'enwiki-literal-year-qualifier-preparation-v1';H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();ready=json.loads((P/'readiness.json').read_text());assert H(P/'code-pins.json')==ready['code_pins_SHA256'];registry=json.loads((P/'code-pins.json').read_text());print(registry.keys())
files=registry.get('files',registry.get('files_SHA256'))
for p,h in files.items():assert H(Path(p))==h
z=subprocess.run([sys.executable,'-I','-B',str(P/'checks.py')],capture_output=True,text=True,timeout=10);assert z.returncode==0;controls=json.loads(z.stdout);assert controls['checks']==23
sys.path[:0]=[str(P),str(B/'tool-dependencies/mwparserfromhell-0.7.2')];import qualifier_core as c,mwparserfromhell as m
extra=[]
for s in ['{{As of|2011<!--comment-->}}','{{As of|1=2011|1=2011}}','{{As of|2=2011}}','{{As of|2011|}}','{{As of|2011{{unknown}}}}','{{As of|0=2011}}']:
 try:c.literal_year_qualifier(m.parse(s).nodes[0])
 except c.Hold:extra.append({'held':s})
 else:raise AssertionError(s)
s='é Before {{As of|2011}}, afterward.';node=m.parse(s).filter_templates()[0];op=c.literal_year_qualifier(node);a=s.index(op['raw']);b=a+len(op['raw']);ba=len(s[:a].encode());bb=len(s[:b].encode());assert s.encode()[ba:bb].decode()==op['raw'];changed=s[:a]+op['replacement']+s[b:];assert changed[:a]+op['raw']+changed[a+len(op['replacement']):]==s;extra.append({'multibyte_inverse':True})
x={'status':'PASS_FINITE_LITERAL_YEAR_ADAPTER_SYNTHETIC_ONLY','input_pins':{str(p):H(p) for p in P.iterdir() if p.is_file()},'registry_pins_verified':len(files),'baseline_controls':controls,'independent_controls':extra,'review':'Core only maps exactly supported literal year AST to temporal qualifier; raw/preimage/hash retained and caller explicitly required to supply original complete node bounds. Options, nested/dynamic/entity values and uncertain AsOf? remain held. No source or fact validation implied.','integration_requirements':['Complete original top-level template node only','Bind exact raw source char/byte preimage and verify inverse','Do not substitute inside citation parameters, unknown containers or transformed-source inventories','Preserve all unrelated structural/component/reference/source gates'],'source_applications':0};(O/'review.json').write_text(json.dumps(x,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'files':{p.name:H(p) for p in O.iterdir() if p.is_file() and p.name!='manifest.json'}},indent=2)+'\n');print('review',H(O/'review.json'));print('manifest',H(O/'manifest.json'))
