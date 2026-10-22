"""Tiny synthetic build+actualtwooverlays only. Never completecatalogderivation."""
import copy,json,sqlite3,tempfile
from pathlib import Path
from unittest.mock import patch
import frame as f
c=f.c;cases=[]
def test(name,ok):assert ok,name;cases.append(name)
def refuse(fn):
 try:fn()
 except Exception:return True
 return False
raw=(c.ROOT/'gutenberg-discovery-pilot-v2/metadata.raw').read_bytes();native=c.parse_rdf.parse(raw,'pg1342.rdf')
row=f.classified(native,{'test_fixture':True});test('all_native_fields_losslessly_reconstructed',f.restore_native(row)==native and c.unpack(*c.pack(row))==row)
for label,languages,status in [('English',['en'],'ELIGIBLE'),('French',['fr'],'EXCLUDED'),('mixed',['en','fr'],'HELD'),('missing',[],'HELD')]:
 n=copy.deepcopy(native);n['languages']=languages;r=f.classified(n,{});test('language_'+label,r['discovery_status'].startswith(status) and r['original_English_composition'].startswith('UNVERIFIED'))
n=copy.deepcopy(native);agent=copy.deepcopy(n['contributors_and_all_roles'][0]);agent['role_qualified_name']='{http://id.loc.gov/vocabulary/relators/}trl';n['contributors_and_all_roles'].append(agent);r=f.classified(n,{});test('English_with_translator_never_originalEnglish_or_rights_cleared',r['contributors_and_all_roles']==n['contributors_and_all_roles'] and r['original_English_composition'].startswith('UNVERIFIED') and r['edition_and_jurisdiction_rights'].startswith('UNVERIFIED') and not r['training_admitted'])
n=copy.deepcopy(native);n['holds']=['unmapped_native_book_fields_preserved_as_hashes'];r=f.classified(n,{});test('unknown_native_field_hold_never_waived',r['discovery_status']=='HELD_METADATA_REPAIR_OR_REVIEW' and f.restore_native(r)['holds']==n['holds'])
n=copy.deepcopy(native);n['native_relations_and_credits']=[{'attributes':{},'text':'https://www.gutenberg.org/ebooks/'+suffix} for suffix in ['1234suffix','1234?x=1','1234#section','1234/','1234']];test('relation_edges_require_complete_canonical_URL',f.strict_relation_IDs(n)==[1234])
rows=[]
for i in range(1,5):
 n=copy.deepcopy(native);n['ebook_ID']=i;n['titles']=['Synthetic Work '+str(i)];binding={'original_source_hold_history':'oversize_RDF_member_not_parsed' if i==4 else None};rows.append((i,'VERIFIED_OVERSIZE_DERIVED_OVERLAY' if i==4 else 'ORIGINAL_SOURCE_PARSED',n,binding))
rows[1][2]['titles']=rows[0][2]['titles'];rows[2][2]['native_relations_and_credits']=[{'attributes':{},'text':'https://www.gutenberg.org/ebooks/2'}]
with tempfile.TemporaryDirectory() as temporary:
 root=Path(temporary);out=root/'build';out.mkdir();count=[0]
 def stream():
  count[0]+=1
  yield from copy.deepcopy(rows)
 stats=f.build(stream(),f.Guard(out,c.clock()),expected_rows=4);db=sqlite3.connect('file:'+str(out/'frame.sqlite3')+'?mode=ro',uri=True)
 try:
  test('one_source_stream_pass_only',count[0]==1 and stats['source_stream_passes']==1 and stats['rows']==4)
  families=db.execute('select ebook_ID,component_ID from families order by ebook_ID').fetchall();test('transitive_same_author_title_and_explicit_relation_families',families==[(1,1),(2,1),(3,1),(4,4)])
  test('shared_creator_or_contributor_alone_not_family',families[-1]==(4,4))
  record=c.unpack(*db.execute('select raw_bytes,raw_hash,packed_hash,codec,payload from frame where ordinal=4').fetchone());test('original_oversize_held_history_retained_in_overlay_layer',record['source_binding']['original_source_hold_history']=='oversize_RDF_member_not_parsed' and stats['original_source_oversize_holds_historically_retained']==1)
  test('all_status_counts_reconcile_without_training',sum(stats['counts']['status'].values())==4 and stats['training_admitted']==stats['usable_tokens']==0)
 finally:db.close()
 test('no_terminal_journal',not list(out.glob('*.sqlite3-journal')))
 for label,changed in [('duplicateID',[(1,rows[0][1],rows[0][2],{})]*2),('wrongcount',rows[:1])]:
  out=root/label;out.mkdir();test(label+'_rejected',refuse(lambda:f.build(copy.deepcopy(changed),f.Guard(out,c.clock()),expected_rows=4)))
 out=root/'cap';out.mkdir()
 with patch.object(f,'DB_CAP',65536):test('SQLite_hard_DB_maxpages_guard',refuse(lambda:f.build(copy.deepcopy(rows),f.Guard(out,c.clock()),expected_rows=4)))
 test('DBhardcap_not_overshot',all(p.stat().st_size<=65536 for p in out.glob('*.sqlite3')))
 out=root/'journal';out.mkdir();(out/'frame.sqlite3-journal').write_bytes(b'x')
 with patch.object(f,'JOURNAL_CAP',1000):test('journal_prewrite_guard',refuse(lambda:f.Guard(out,c.clock()).check(1000)))
 with patch.object(f,'OUTPUT',2000000),patch.object(f,'HEADROOM',320000):test('aggregate_prewrite_output_guard',refuse(lambda:f.Guard(out,c.clock()).check(700000)))
 test('worker_deadline_guard',refuse(lambda:f.Guard(out,c.clock()-571).check()))
actual=f.overlay_records();test('exact_two_independently_verified_native_overlays_loaded',set(actual)=={17579,18683} and [actual[i][0]['ebook_ID'] for i in sorted(actual)]==[25851,26849])
proposal=json.loads(f.PROPOSAL.read_text())
with tempfile.TemporaryDirectory() as temporary:
 path=Path(temporary)/'proposal.json'
 for label in ['missing','extra','ordinal','compressedhash','rawJSONhash','wrongID','wrongmember']:
  bad=copy.deepcopy(proposal)
  if label=='missing':bad['overlays'].pop()
  elif label=='extra':bad['overlays'].append(copy.deepcopy(bad['overlays'][0]))
  elif label=='ordinal':bad['overlays'][0]['ordinal']=1234
  elif label=='compressedhash':bad['overlays'][0]['derived_metadata_compressed_SHA256']='0'*64
  elif label=='rawJSONhash':bad['overlays'][0]['derived_metadata_JSON_SHA256']='0'*64
  elif label=='wrongID':bad['overlays'][0]['ebook_ID']=1342
  else:bad['overlays'][0]['native_member']['name']='wrong.rdf'
  path.write_text(json.dumps(bad))
  with patch.object(f,'PROPOSAL',path):test('overlay_'+label+'_tamper_rejected',refuse(f.overlay_records))
w=json.loads((f.SOURCE/'worker-result.json').read_text());db=c.readonly_union([f.SOURCE/x['file'] for x in w['database_shards']])
try:plan=[r[3] for r in db.execute('explain query plan '+f.source_query())]
finally:db.close()
test('indexed_source_query_no_wholecatalog_temp_materialization',not any('MATERIALIZE' in r or 'TEMP B-TREE' in r for r in plan) and any('MERGE (UNION ALL)' in r for r in plan))
test('frozen_classifier_byte_identical',(f.HERE/'classify.py').read_bytes()==(f.EXEC/'gutenberg-English-frame-preparation-v1/derive.py').read_bytes())
(f.HERE/'checks.json').write_text(json.dumps({'status':'PASS','cases':cases,'count':len(cases),'source_query_plan':plan,'full_catalog_derivations':0,'network_requests':0},indent=2)+'\n');print(len(cases),'PASS')
good={'environment':c.environment(),'files_SHA256':{str(p.resolve()):c.file_sha(p) for p in f.dependencies()}}
with tempfile.TemporaryDirectory() as td:
 path=Path(td)/'manifest.json'
 def verify(m,expected=None):
  path.write_text(json.dumps(m))
  with patch.object(f,'MANIFEST',path):return f.pins(c.file_sha(path) if expected is None else expected)
 verify(good);test('explicit_parent_SHA_exact_inventory_all_source_and_overlay_pins',True)
 for label in ['empty','missing','extra','substitute','runtime']:
  bad=copy.deepcopy(good)
  if label=='empty':bad['files_SHA256']={}
  elif label=='missing':bad['files_SHA256'].pop(next(iter(bad['files_SHA256'])))
  elif label=='extra':bad['files_SHA256']['/tmp/unreviewed']='0'*64
  elif label=='substitute':bad['files_SHA256'][next(iter(bad['files_SHA256']))]='0'*64
  else:bad['environment']={}
  test('manifest_'+label+'_tamper_rejected',refuse(lambda:verify(bad)))
 test('manifest_container_digest_tamper_rejected',refuse(lambda:verify(good,'0'*64)))
(f.HERE/'checks.json').write_text(json.dumps({'status':'PASS','cases':cases,'count':len(cases),'source_query_plan':plan,'full_catalog_derivations':0,'network_requests':0},indent=2)+'\n');print(len(cases),'total PASS')
