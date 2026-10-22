from pathlib import Path
import sys,json,hashlib,subprocess
O=Path(__file__).resolve().parent;B=O.parent;P=B/'enwiki-integrated-companion-preparation-v6';S=B/'enwiki-short-footnote-preparation-v3';H=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
expected={'code-pins.json':'4fc9bfc4772de692888778fc3afaf72fcb1b329daad521d4c4993ac6971c3ec0','profile.json':'7c96d530915aa6012938bebf7d6e1da34efc365cb8e21c9d5afd95bd977d7f7b','readiness.json':'5d071f8c904c98631e880dc6123edda934fabdb2c5eec1735fbc968a80aeca3c'}
for f,h in expected.items():assert H(P/f)==h
for base in [P,S]:
 for f,h in json.loads((base/'manifest.json').read_text())['files'].items():assert H(base/f)==h
for f,h in json.loads((P/'code-pins.json').read_text())['files'].items():assert H(f)==h
assert H(S/'short_core.py')=='f433f645fd6e356df8802e2c6e7e59913e973f087355920b845276916826edda';assert (P/'integrated_core.py').read_bytes()==(B/'enwiki-integrated-companion-preparation-v5/integrated_core.py').read_bytes()
results=[]
for base,f in [(S,'checks.py'),(P,'core_checks.py'),(P,'checks.py')]:
 q=subprocess.run([sys.executable,'-I','-B',str(base/f)],capture_output=True,text=True,timeout=20);assert q.returncode==0,(base,f,q.stdout,q.stderr);x=json.loads(q.stdout);results.append({'path':str(base/f),'count':x.get('count',x.get('checks')),'PASS':True})
q=subprocess.run([sys.executable,'-I','-B',str(P/'run.py'),'--code-pins-sha256',expected['code-pins.json'],'--profile-sha256',expected['profile.json']],capture_output=True,text=True,timeout=20);assert q.returncode==0 and 'READY_STATIC_PREFLIGHT_SYNTHETIC_ONLY' in q.stdout
sys.path[:0]=[str(S),str(B/'tool-dependencies/mwparserfromhell-0.7.2'),str(B/'enwiki-page-local-reference-preparation-v2'),str(B/'enwiki-generic-AST-policy-preparation-v4')];import short_core as c,mwparserfromhell as m,reference_core as ref,policy_core as literal
cases=[]
def resolve(s):return c.resolve_page(s,m,literal,ref)
def bibliography(author,year='2014',extra=''):return '{{cite book|last='+author+'|year='+year+'|title=T'+extra+'}}'
uncertain='\n== Other ==\n{{cite web|author=[[Unknown Author]]|year=2020|title=T}}'
for author,year,held in [('Smith','2014',False),('Smith','2020',True),('Another','2020a',True),('Different','2020z',True)]:
 s='A{{sfn|'+author+'|'+year+'}}.\n== Sources ==\n'+bibliography(author,year)+uncertain;x=resolve(s);assert bool(x['source_partition'][0]['holds'])==held and not x['unbound_bibliographic_global_shadow'];cases.append({'author':author,'year':year,'held':held,'no_author_guessed':True})
for extra in ['|ref={{unknown}}','|author1=Other','|last=Other','|year={{unknown}}','|date=2021-01-01','|title=T<ref>Nested</ref>']:
 # Replace the literal year when testing a dynamic one rather than manufacture duplicatekeys only.
 u='{{cite web|author=[[Unknown Author]]|year=2020|title=T'+extra+'}}'
 if extra=='|year={{unknown}}':u='{{cite web|author=[[Unknown Author]]|year={{unknown}}|title=T}}'
 x=resolve('A{{sfn|Smith|2014}}.\n== Sources ==\n'+bibliography('Smith')+'\n'+u);assert x['source_partition'][0]['holds'] and x['unbound_bibliographic_global_shadow'];cases.append({'global_refusal':extra})
for bad in ['{{cite web|author=[[{{unknown}}]]|year=2020|title=T}}','{{cite web|author=Before [[X]]|year=2020|title=T}}','{{cite web|author=[[A&amp]]|year=2020|title=T}}']:
 x=resolve('A{{sfn|Smith|2014}}.\n== Sources ==\n'+bibliography('Smith')+'\n'+bad);assert x['unbound_bibliographic_global_shadow'];cases.append({'non_simple_author_still_global':bad})
x=resolve('A{{sfn|Smith|2014}}.\n== Sources ==\n'+bibliography('Smith')+'\n{{cite web|author=[[Unknown Author]]|year=2020|ref={{sfnRef|Other|2010}}|title=T}}');assert not x['source_partition'][0]['holds'] and not x['unbound_bibliographic_global_shadow'];cases.append({'valid_explicit_ref_not_unknown_partial_constraint':True})
x=resolve('A{{sfn|Shaw|2012}}.\n== Sources ==\n'+bibliography('Shaw','2012')+'\n{{unknown|'+bibliography('Shaw','2012')+'}}');assert x['source_partition'][0]['holds'];cases.append({'opaque_exact_key_still_held':True})
x=resolve('A{{sfn|Smith|2014}}.\n== Sources ==\n'+bibliography('Smith')+uncertain);u=x['bibliographic_companions'][-1];assert u['holds'] and u['component_holds'] and u['potential_shadow_constraint']['defines_usable_bibliography']is False and '[[Unknown Author]]' in u['raw'];cases.append({'unresolved_author_raw_component_never_qualified_as_bibliography':True})
for f,h in json.loads((P/'code-pins.json').read_text())['files'].items():assert H(f)==h
out={'status':'PASS_FOCUSED_SHORTV3_INTEGRATEDV6_AUDIT_SYNTHETIC_ONLY','top_pins':expected,'short_core_SHA256':H(S/'short_core.py'),'unchanged_v5_integrated_core_SHA256':H(P/'integrated_core.py'),'all183pins_verified_before_after':True,'reproduced_controls':results,'independent_cases':cases,'actual_nonexecuting_preflight':q.stdout.strip(),'review_scope':'Narrow known base-year shadow for a single literal WikiLink author only. No author rendering/guessed identity, all same-base-year author/year suffix keys held; explicit ref/other author fields/nestedref/invalid year-date/other unknown retain global guard. Existing source/namespace/marker/resource controls unchanged. No partial preview or component-hold clearing.','retained_source_application':False,'new_admitted_documents':0};(O/'review.json').write_text(json.dumps(out,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'files':{p.name:H(p) for p in O.iterdir() if p.is_file() and p.name!='manifest.json'}},indent=2)+'\n');print('review',H(O/'review.json'));print('manifest',H(O/'manifest.json'))
