import copy,json
import policy
n=0
def test(text,held,reason=None):
 global n;r=policy.filter_raw(text);assert bool(r['reasons'])==held
 if reason:assert reason in [v['reason'] for v in r['reasons']]
 assert r['derivative_SHA256']==policy.sha(text.encode()) and r['omitted_source_bytes']==0;n+=1

test('A short definition explains a term.',False)
test('A procedure\n1. Open the valve.\n2. Read the gauge.\n3. Record the result.',False)
test('As of 2004, the company reported growth. The historical date remains explicit.',False)
test('The code calls f() and then prints the result.\nprint(result)',False)
test('A reference list\nAuthor (1990). Study.\nAuthor (1991). Another study.',False)
test('The figure illustrates the point (Figure 2). Its explanatory prose stands alone.',False)
test('Figure 1\nA semantic description of a diagram.',False)
test('Discussion of the licence.\nLicence: CC BY\nFormat: PDF\nA single source credit.',False)
test('Resources\nLicence: CC BY\nFormat: PDF\nAnother resource\nLicense: CC BY-SA\nFormats: EPUB',True,'REPEATED_RESOURCE_CATALOG_FIELDS')
test('Resource links\nPrimary Source Text: Read the letter https://example.org/1\nSecondary Source Video: View this https://example.org/2',True,'LINKED_SOURCE_INDEX_WITH_NO_MAIN_EXPOSITION')
test('Lesson\nThis complete explanation uses the following primary sources.\nPrimary Source Text: Read https://example.org/1\nSecondary Source Text: Read https://example.org/2',False)
test('Chapter\n// program comment class Main { public static void main(String[] args) { int x=1; } }',True,'LINE_COMMENT_CONTAINS_FLATTENED_PROGRAM')
test('Chapter\n// program comment\nclass Main {\n public static void main(String[] args) { int x=1; }\n}',False)
test('A class Main is a class. A static method may contain a statement;',False)
test('Both surfaces ( and ) have the same field.',True,'EMPTY_PAIRED_LABELS')
test('The field is equal on surfaces A and B, and f() is a function call.',False)
test('The statement uses [latex][/latex] as its formula.',True,'EMPTY_MATH_ELEMENT')
test('The relation [latex]F=ma[/latex] is intact.',False)
test('x=\\[ \\] is empty.',True,'EMPTY_MATH_ELEMENT')
test('x=\\[x+y\\] is present.',False)
test('Glossary\nterm: definition\nReferences\nA source.',False)
test('A poem\nThe waves were high.\nThe moon was bright.',False)
test('A minor typo in teh paragraph alone does not establish missing meaning.',False)
test('Writing about formats and licences is not itself a catalogue.',False)
test("The conjunction (and) joins clauses.",False)
test("The conjunction (or) offers alternatives.",False)
test("This lesson teaches the literal token '( and )' as a character sequence.",False)
test("A short definition.\nPrimary Source Text: Read https://example.org/1\nSecondary Source Text: Read https://example.org/2",False)
test("An intact main explanation is here.\nLicence: CC BY\nFormat: PDF\nResource two\nLicence: CC BY-SA\nFormat: EPUB",False)
test('For the relation\nⓐ Find the domain.\nⓑ Find the range.',True,'UNBOUND_MATH_EXERCISE_INTRO')
test('For the relation\n{(1,2), (3,4)}\nⓐ Find the domain.',False)
test('For the relation between two people, read the full paragraph.',False)
test('It is estimated to be about\nHowever, no value follows.',True,'INTRODUCED_VALUE_ABSENT_AT_DISCOURSE_BOUNDARY')
test('It is estimated to be about 42.\nHowever, this estimate is uncertain.',False)
test('The additional education is measured by the horizontal distance between B and C and.',True,'DANGLING_MEASURED_VALUE_CLAUSE')
test('The distance is measured by the map and the result is recorded.',False)
test('The word and is a conjunction. Literal teaching of "and." is intact.',False)
# Complete source partition with whole main section and attribution sidecar.
s='Whole coherent section.\nAttribution: Author, CC BY.';end=s.index('Attribution')
proof={'source_SHA256':policy.sha(s.encode()),'native_projection_whole_text_verified':True,'native_artifact_SHA256':'a'*64,'projection_policy_SHA256':'b'*64,'independent_boundary_review_SHA256':'c'*64,'components':[{'id':'main','char_start':0,'char_end':end,'role':'MAIN_PROSE','native_locator':'/article/section[1]','source_span_SHA256':policy.sha(s[:end].encode()),'authored_unit_kind':'SECTION','semantic_independence':'VERIFIED_WHOLE_AUTHORED_UNIT','dependencies':[]},{'id':'credit','char_start':end,'char_end':len(s),'role':'ATTRIBUTION','native_locator':'/article/footer','source_span_SHA256':policy.sha(s[end:].encode())}]}
r=policy.separate_components(s,proof);assert r['exact_inverse'] and len(r['derivatives'])==1 and ''.join(p['text'] for p in r['components'])==s;n+=1
assert policy.separate_components(s,None)['derivatives']==[];n+=1
q=copy.deepcopy(proof);q['components'][0]['dependencies']=[{'component_id':'credit','required':True,'available':False}];assert policy.separate_components(s,q)['derivatives']==[];n+=1
q=copy.deepcopy(proof);q['components'][0]['dependencies']=[{'component_id':'credit','required':False,'available':False}];assert len(policy.separate_components(s,q)['derivatives'])==1;n+=1
q=copy.deepcopy(proof);q['components'][0]['semantic_independence']='UNKNOWN';assert not policy.separate_components(s,q)['derivatives'];n+=1
for mutation in ['sha','gap','overlap','unknownrole','duplicateID','paragraphcrop','hash','projection','dependency','proofhash']:
 q=copy.deepcopy(proof)
 if mutation=='sha':q['source_SHA256']='f'*64
 if mutation=='gap':q['components'][1]['char_start']+=1
 if mutation=='overlap':q['components'][1]['char_start']-=1
 if mutation=='unknownrole':q['components'][1]['role']='REMOVE'
 if mutation=='duplicateID':q['components'][1]['id']='main'
 if mutation=='paragraphcrop':q['components'][0]['authored_unit_kind']='SENTENCE'
 if mutation=='hash':q['components'][0]['source_span_SHA256']='d'*64
 if mutation=='projection':q['native_projection_whole_text_verified']=False
 if mutation=='dependency':q['components'][0]['dependencies']=[{'component_id':'absent','required':True,'available':True}]
 if mutation=='proofhash':q['native_artifact_SHA256']='bad'
 try:policy.separate_components(s,q)
 except ValueError:n+=1
 else:raise AssertionError(mutation)
# Unicode char->byte mapping is lossless, not offset-normalized.
t='É English。\n';rr=policy.filter_raw(t);assert rr['source_UTF8_bytes']==len(t.encode()) and rr['source_characters']==len(t);n+=1
try:policy.filter_raw('x'*(policy.MAX_BYTES+1))
except ValueError:n+=1
else:raise AssertionError('cap')
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':n,'development_or_fullsource_policy_runs':0}))
# Actual fixed30 production engine, synthetic files only; all raw candidates copied unchanged.
import tempfile,os
from pathlib import Path
import engine
with tempfile.TemporaryDirectory() as z:
 d=Path(z);out=d/'out';out.mkdir();inputs=[];labels={};total=0
 for i in range(30):
  raw=(f'Original whole section {i}. Its explanation is intact.\n').encode();p=d/f'{i}.utf8';p.write_bytes(raw);st=p.stat();hh=policy.sha(raw);total+=len(raw)
  inputs.append({'source_id':1,'ordinal':i+1,'text_path':str(p),'bytes':len(raw),'SHA256':hh,'stat':[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns],'raw_JSON':{'path':'synthetic referenced original','SHA256':'a'*64},'draws':[{'draw':i+1}],'existing_language_pass':True})
  labels[hh]={'verdict':'HOLD_SOURCE_FIDELITY_REVIEW' if i==0 else 'READABLE_COHERENT_PROSE_RESEARCH_PROXY'}
 pp={'inputs':inputs,'expected_input_text_bytes':total,'development_labels':labels};rr=engine.run(pp,out,lambda extra=0:None)
 assert rr['whole_units']==30 and rr['diagnostics']['unchanged_raw_candidate_units']==29 and rr['diagnostics']['known_HOLD_generic_not_flagged']==1
 for item in inputs[1:]:assert (out/f"source-1-row-{item['ordinal']:06d}.candidate.utf8").read_bytes()==Path(item['text_path']).read_bytes()
 n+=1
 # Hash/stat mutation cannot create a new candidate silently.
 p=Path(inputs[0]['text_path']);p.write_text('changed')
 second=d/'second';second.mkdir()
 try:engine.run(pp,second,lambda extra=0:None)
 except ValueError:n+=1
 else:raise AssertionError('source mutation')
 print(json.dumps({'status':'PASS_PRODUCTION_ENGINE_SYNTHETIC_ONLY','total_policy_and_engine_controls':n,'retained_source_policy_runs':0}))
