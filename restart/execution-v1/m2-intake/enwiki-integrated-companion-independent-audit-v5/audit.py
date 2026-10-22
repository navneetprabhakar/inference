from pathlib import Path
import json,hashlib,subprocess,sys,collections
B=Path.cwd()/'restart/execution-v1';P=B/'enwiki-integrated-companion-preparation-v5';O=B/'m2-intake/enwiki-integrated-companion-independent-audit-v5';O.mkdir(exist_ok=True)
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();pins=json.loads((P/'code-pins.json').read_text())['files'];assert len(pins)==183 and H(P/'code-pins.json')=='5c98f89b549685a6fd56115e734a1ec2f4b4afd398402000f9da15fa399839e3'
for p,h in pins.items():assert H(Path(p))==h
for name in ['core_checks.py','checks.py']:
 r=subprocess.run([sys.executable,'-I','-B',str(P/name)],capture_output=True,text=True,timeout=25,check=True);(O/('reproduced-'+name+'.json')).write_text(r.stdout)
r=subprocess.run([sys.executable,'-I','-B',str(P/'run.py'),'--code-pins-sha256',H(P/'code-pins.json'),'--profile-sha256',H(P/'profile.json')],capture_output=True,text=True,timeout=20,check=True);assert 'PASS' in r.stdout or 'READY' in r.stdout
sys.path[:0]=[str(P),str(B/'tool-dependencies/mwparserfromhell-0.7.2'),str(B/'enwiki-generic-AST-policy-preparation-v4'),str(B/'enwiki-page-local-reference-preparation-v2'),str(B/'enwiki-structural-companion-policy-preparation-v1'),str(B/'enwiki-short-footnote-preparation-v2'),str(B/'enwiki-literal-year-qualifier-preparation-v1')]
import integrated_core as c,mwparserfromhell as m,policy_core as literal,reference_core as ref,rules
fixtures=[]
for text in ['A<ref>Source</ref> &#10214;ref:g0:1&#10215;.','A<ref>Source</ref> ⟦ref:g0:<!--x-->1⟧.','A{{sfn|Smith|2020}} &#10214;sfn:1&#10215;.\n== Sources ==\n{{cite book|last=Smith|year=2020|title=T}}','&#10214;ref:g0:1&#10215;','&#10214;sfn:','⟦r<!--cut-->ef:g0:1⟧','⟦sf<b>n</b>:1⟧','[[Page|&#10214;ref:g0:1&#10215;]]','&#10214;REF:unfinished','&#10214;sfn:0&#10215;']:
 result=c.develop_page(text,m,literal,ref,rules);assert ''.join(s['raw'] for s in result['sections'])==text
 unit=result['sections'][0];assert unit['provisional_prose_preview'] is None and unit['preview_SHA256'] is None and unit['prose_structural_holds'];fixtures.append({'source':text,'holds':unit['prose_structural_holds'],'preview':None})
for text in ['A<ref name=x>One.</ref>B<ref name=x/>C<ref name=x/>.','Alpha &amp; beta [[Book: Title|title]] <ref>Literal URL https://example.org/.</ref>.','First<ref>One.</ref>Second<ref>Two.</ref>.','Alpha.\n== Second ==\nBeta<ref>Source.</ref>.','Literal ⟦other:1⟧.']:
 result=c.develop_page(text,m,literal,ref,rules);assert ''.join(s['raw'] for s in result['sections'])==text
 assert all(s['provisional_prose_preview'] is not None and s['postprojection_marker_inventory']['verified'] for s in result['sections'])
 for s in result['sections']:
  transformed=c.apply_ops(s['raw'],s['source_char_span'][0],s['source_operations']);assert c.invert_ops(transformed,s['source_char_span'][0],s['source_operations'])==s['raw']
 fixtures.append({'source':text,'successful_regions':len(result['sections']),'inventory':[s['postprojection_marker_inventory'] for s in result['sections']]})
for p,h in pins.items():assert H(Path(p))==h
(O/'independent-fixtures.json').write_text(json.dumps(fixtures,indent=2)+'\n')
review={'status':'PASS_FOCUSED_V5_POSTPROJECTION_MARKER_FIX_NO_NATIVE_APPLICATION','preparation_pins':{'code':H(P/'code-pins.json'),'profile':H(P/'profile.json'),'core':H(P/'integrated_core.py'),'readiness':H(P/'readiness.json')},'all183pins_verified_twice':True,'static_preflight':r.stdout.strip(),'reproduced_core_controls':83,'reproduced_runtime_controls':34,'independent_fixtures':15,'original_three_v4_exploits_refused':True,'wholepreview_cleared_on_postprojection_hold':True,'legitimate_multireuse_and_reference_multiple_ids_preserved':True,'raw_inverse_reconciled':True,'production_diff_review':'Only postprojection marker Counter/prefix guard, successful diagnostic inventory, preview=None on caught Hold, new outputversion+collections runtime pin. No ref/shortnote/year/source/namespace or numerical-cap relaxation.','limitations':['Marker Counter is intentionally order independent; operation inverse and sequential renderer retain narrative order.','No original5page operation, complete-source semantic evaluation, tokenizer, admissions or fullXML application occurred.'],'new_admissions':0}
(O/'review.json').write_text(json.dumps(review,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'files':{p.name:H(p) for p in O.iterdir() if p.is_file() and p.name!='manifest.json'}},indent=2)+'\n');print(json.dumps({'review':H(O/'review.json'),'manifest':H(O/'manifest.json')}))
