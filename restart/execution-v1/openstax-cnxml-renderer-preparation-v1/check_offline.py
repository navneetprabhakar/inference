"""Synthetic fixture profile only: urn:synthetic:module-fixture is not CNXML evidence."""
import copy,json,tempfile
from pathlib import Path
from unittest.mock import patch
from lxml import etree
import render as r
cases=[]
RAW=b'''<document xmlns="urn:synthetic:module-fixture" xmlns:m="urn:synthetic:math" xmlns:md="http://cnx.rice.edu/mdml"><title>Fixture only</title><md:license url="http://creativecommons.org/licenses/by/4.0/"/><para>before <emphasis>bold</emphasis> after<!-- preserved comment --> end<?review fixture?> tail</para><table><tgroup cols="2"><row><entry morerows="1">A</entry><entry>B</entry></row></tgroup></table><equation><m:math><m:mi>x</m:mi><m:mo>=</m:mo><m:mn>2</m:mn></m:math></equation><figure><media><image src="../media/map.svg"/></media><caption>Unresolved map caption</caption></figure><list><item>One</item><item>Two</item></list><link target-id="section-x">cross reference</link><quote>Credited quotation</quote><unknown-future foo="literal">Unknown preserved</unknown-future><script>alert('never executed')</script></document>'''
def expected(raw=RAW):return {'module_ID':'synthetic-only','native_path':'SYNTHETIC_FIXTURE_NOT_OBSERVED_MODULE','expected_bytes':len(raw),'expected_Git_blob_SHA1':r.git_blob(raw),'collection_appearances':[{'book':'syntheticA'},{'book':'syntheticB'}]}
def fail(f):
 try:f()
 except (ValueError,TimeoutError,etree.XMLSyntaxError):return
 raise AssertionError('expected refusal')
x=r.render_module(RAW,expected());receipt=x['receipt'];ast=x['AST'];view=x['HTML'].decode()
assert receipt['all_native_text_and_tails_conserved'] and receipt['native_text_SHA256']==r.sha(''.join(etree.fromstring(RAW).itertext()).encode());cases.append('synthetic_exact_native_text_and_tails_conserved')
assert receipt['root_qualified_name']=='{urn:synthetic:module-fixture}document' and receipt['unmapped_node_count']==receipt['node_count']-2;cases.append('all_unverified_names_held_no_CNXML_schema_assumption')
assert 'native_CNXML_namespace_and_schema_profile_unverified' in receipt['holds'];cases.append('unknown_schema_stays_held')
assert any(d.get('literal_target')=='../media/map.svg' for d in receipt['dependency_inventory']) and any(d.get('literal_target')=='section-x' for d in receipt['dependency_inventory']);cases.append('relative_media_and_symbolic_xref_targets_preserved_unfetched')
assert all(name in [r.local(d.get('qualified_name')) for d in receipt['dependency_inventory']] for name in ['table','equation','math','figure','list','item','quote']);cases.append('tables_math_figures_lists_quotes_inventoried_not_stripped')
assert 'morerows' in json.dumps(ast) and 'Unresolved map caption' in view and 'Unknown preserved' in view;cases.append('table_span_attributes_caption_and_unknown_content_preserved')
assert 'serialized_original_XML' in json.dumps(ast) and 'preserved comment' in view and 'review fixture' in view;cases.append('comments_processing_instructions_preserved_as_inert_literal_XML')
assert '<script>' not in view and 'alert(&#x27;never executed&#x27;)' in view and "connect-src &#x27;none&#x27;" in view and 'src="../media/map.svg"' not in view;cases.append('script_and_network_targets_inert_CSP_blocks_fetches')
assert receipt['observed_CC_URIs'][0]['matches_expected_historical_CC_BY4'] and receipt['rights_field_inventory'] and 'per_module_and_object_rights_review_pending' in receipt['holds'];cases.append('observed_CC_BY_URI_is_not_object_rights_clearance')
restricted=RAW.replace(b'licenses/by/4.0/',b'licenses/by-nc-nd/4.0/');rx=r.render_module(restricted,expected(restricted));assert 'other_CC_URI_or_license_scope_conflict_requires_review' in rx['receipt']['holds'] and 'expected_historical_CC_BY4_URI_not_observed_in_module' in rx['receipt']['holds'];cases.append('NC_ND_conflict_held')
no_license=b'<root xmlns="urn:synthetic">No license</root>';assert 'expected_historical_CC_BY4_URI_not_observed_in_module' in r.render_module(no_license,expected(no_license))['receipt']['holds'];cases.append('missing_license_not_inferred_from_collection')
for name,raw in [('DTD',b'<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><x>&e;</x>'),('NUL',b'<x>\0</x>'),('malformed',b'<x>')]:fail(lambda:r.render_module(raw,expected(raw)));cases.append(name+'_refused_without_external_access')
fail(lambda:r.render_module(RAW+b' ',expected()));cases.append('exact_historical_native_hash_and_length_required')
with patch.object(r,'MAX_NODES',2):fail(lambda:r.render_module(RAW,expected()))
cases.append('node_count_bound')
with patch.object(r,'MAX_DEPTH',1):fail(lambda:r.render_module(RAW,expected()))
cases.append('depth_bound')
with patch.object(r,'MAX_SECONDS',0):fail(lambda:r.render_module(RAW,expected()))
cases.append('elapsed_bound')
with tempfile.TemporaryDirectory() as t:
 p=Path(t);budget=r.OutputBudget(p,10);budget.write_many([('a',b'12345')]);fail(lambda:budget.write_many([('b',b'123'),('c',b'123')]))
 assert (p/'a').read_bytes()==b'12345' and not(p/'b').exists();cases.append('aggregate_module_output_cap_before_any_module_write')
 fail(lambda:budget.write_many([('../escape',b'1')]));cases.append('output_escape_refused')
 (p/'symlink').symlink_to(p/'a');fail(lambda:budget.used());cases.append('output_symlinks_refused')
assert len(receipt['collection_appearances'])==2 and receipt['new_admitted_documents']==receipt['new_admitted_tokens']==receipt['external_resources_fetched']==0;cases.append('shared_appearances_retained_zero_admission_or_fetch')
result={'status':'PASS_SYNTHETIC_ONLY_NO_NATIVE_CNXML_MODULE_OBSERVED','synthetic_namespace':'urn:synthetic:module-fixture','case_count':len(cases),'cases':cases,'source_modules_read':0,'network_requests':0,'new_admitted_documents':0,'new_admitted_tokens':0}
(r.HERE/'offline-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
