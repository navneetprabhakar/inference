from pathlib import Path
import sys,json,subprocess,hashlib
B=Path(__file__).resolve().parents[2];P=B/'wikibooks-three-renewed-custody-preparation-v1';O=Path(__file__).resolve().parent;H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sys.path.insert(0,str(P));import audit
ready=json.loads((P/'readiness.json').read_text());assert H(P/'code-pins.json')==ready['code_pins_SHA256'];assert H(P/'profile.json')==ready['profile_SHA256']
for name,h in json.loads((P/'manifest.json').read_text())['files'].items():assert H(P/name)==h
results={}
for f in ['checks.py','adapter_cases.py','memory_cases.py','revision_cases.py']:
 z=subprocess.run([sys.executable,'-B',str(P/f)],capture_output=True,text=True,timeout=15);assert z.returncode==0,(f,z.stderr);results[f]=json.loads(z.stdout)
for case in ['deadline','term','int','slot-setup-failure']:
 z=subprocess.run([sys.executable,'-B',str(P/'lifecycle_cases.py'),'--case',case],capture_output=True,text=True,timeout=5);assert z.returncode==0,(case,z.stderr);results[case]=json.loads(z.stdout)
entries=json.loads((P/'body-sources.json').read_text());assert len(entries)==837
rows=json.loads((B/'m2-intake/gutenberg-post1900-first-complete-units-v1/documents.json').read_text())['documents'];expected={str((B/'m2-intake/gutenberg-post1900-first-complete-units-v1'/r['file']).resolve()) for r in rows}
assert len(expected)==29 and expected<={e['path'] for e in entries if e['required_current_candidate_body_coverage']}
candidates=json.loads((P/'candidates.json').read_text());assert len(candidates)==3
for c in candidates:
 raw=Path(c['captured_raw_source_ancestor']['path']).read_bytes();der=Path(c['file']).read_bytes();a=c['original_source_interval'];assert raw[a['start']:a['end_exclusive']]==der;assert b'\r' not in der
 role={'page_id':c['page_id'],'revision_id':c['revision_id'],'text_sha256':c['captured_raw_source_ancestor']['SHA256'],'family':c['family_ID']};meta={'source_ordinal':c['source_ordinal'],'current_global_finalizer_role':role}
 assert audit.own_ancestor(c,'unrelated/path#ordinal',meta)
 for k in role:assert not audit.own_ancestor(c,'unrelated/path#ordinal',{**meta,'current_global_finalizer_role':{**role,k:'wrong'}})
 assert not audit.own_ancestor(c,'unrelated/path#ordinal',{**meta,'source_ordinal':-1})
x={'status':'PASS_FOCUSED_PREPARATION_AUDIT_NO_RETAINED_SCAN_OR_RECOUNT','preparation':str(P),'pins':{'codepins':H(P/'code-pins.json'),'profile':H(P/'profile.json'),'manifest':H(P/'manifest.json'),'readiness':H(P/'readiness.json')},'reproduced_controls':results,'total_control_count':sum(results[k]['count'] for k in ['checks.py','adapter_cases.py','memory_cases.py','revision_cases.py'])+4,'independent_controls':['All29 current PG mains/notes scheduled required within837 adapters','All3 exact byte ancestors inverse; no CRLF-normalization count drift','All3 WB renderer ancestry requires exact ordinal/page/revision/family/full parent hash; five independent wrong-field refusals each','All current finalizer holds preserved and protected roles override own ancestry','Immutable same matcher; exact >=.8 cardinality bound and whole containment retained','Four large-WB exceptions require source ordinal/page/revision/family/exact normalized hash+measured words and are compared anew; no transfer of old match results','Family enumeration uses WB finalized pages, not PG catalog','Actual supervisor alarms/termination before verify/discovery/disk, cleanup guarded by created; four lifecycle fixtures reproduced'],'scope':'Source-specific import/component rights and language/factual decisions remain pending. No candidate tokenization, retained body matching, admission, network or globalledger writes. Existing frozen M1 may recount3 only after parent dispatch.','unqualified_current_all_future_coverage_claim':False}
(O/'review.json').write_text(json.dumps(x,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'files':{p.name:H(p) for p in O.iterdir() if p.is_file() and p.name!='manifest.json'}},indent=2)+'\n');print('review',H(O/'review.json'));print('manifest',H(O/'manifest.json'))
