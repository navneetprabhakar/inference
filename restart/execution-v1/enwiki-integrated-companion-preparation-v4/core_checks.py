from pathlib import Path
import sys,json
B=Path(__file__).resolve().parent.parent;sys.path[:0]=[str(Path(__file__).resolve().parent),str(B/'tool-dependencies/mwparserfromhell-0.7.2'),str(B/'enwiki-generic-AST-policy-preparation-v4'),str(B/'enwiki-page-local-reference-preparation-v2'),str(B/'enwiki-structural-companion-policy-preparation-v1'),str(B/'enwiki-short-footnote-preparation-v2'),str(B/'enwiki-literal-year-qualifier-preparation-v1')]
import mwparserfromhell as m,policy_core as literal,reference_core as ref,rules,integrated_core as core
assert m.__version__=='0.7.2' and m.parser.use_c
checks=[]
def page(s):
 r=core.develop_page(s,m,literal,ref,rules)
 assert ''.join(x['raw'] for x in r['sections'])==s and ''.join(x['raw'] for x in r['all_original_top_nodes'])==s
 for u in r['sections']:
  a,b=u['source_char_span'];ba,bb=u['source_byte_span'];assert s[a:b]==u['raw'] and s.encode()[ba:bb]==u['raw'].encode()
  if u['operations_applied_to_provisional_markup']:
   changed=core.apply_ops(u['raw'],a,u['source_operations']);assert core.invert_ops(changed,a,u['source_operations'])==u['raw']
 return r

def check(name,s,expected=None,held=False):
 r=page(s)
 if expected is not None:assert r['sections'][0]['provisional_prose_preview']==expected,(name,r)
 if held:assert r['sections'][0]['provisional_prose_preview'] is None
 checks.append({'name':name,'PASS':True});return r
for name,text in [('lowercase_file_inline','X[[file:A.png]]Y'),('lowercase_category_inline','X[[category:Example]]Y'),('uppercase_module','X[[MODULE:Example]]Y'),('leadingwhitespace','[[ File:A.png]]'),('prefixspace','[[File :A.png]]'),('prefixunderscore','[[File_:A.png]]'),('aftercolonspace','[[File: A.png]]'),('leadingcolon','[[:File:A.png]]'),('leadingcoloncategory','[[:category:Example]]'),('leadingcolonunknown','[[:Book:Title]]')]:check('namespace_variant_'+name,text,held=True)
r=check('lowercase_standalone_file_companion','[[file:A.png|Caption]]','');assert r['exact_raw_metadata_companions'][0]['raw_link_target']=='file:A.png'
r=check('mixedcase_category_companion','[[cAtEgOrY:History]]','');assert r['exact_raw_metadata_companions'][0]['raw_link_target']=='cAtEgOrY:History'
check('ordinary_exactparagraph','First.\n\nSecond.','First.\n\nSecond.')
check('colon_booktitle_notnamespace','Read [[The Real North Korea: Life and Politics]].','Read The Real North Korea: Life and Politics.')
r=check('standalone_category_completecompanion','[[Category:History]]','');assert r['exact_raw_metadata_companions'][0]['raw_link_target']=='Category:History'
check('inline_category_hold','Before [[Category:History]] after.',held=True)
r=check('standalone_media_caption_companion','[[File:A.jpg|Caption with {{unknown}}]]','');assert 'Caption with {{unknown}}' in r['exact_raw_metadata_companions'][0]['raw_link_display_or_options'] and r['sections'][0]['semantic_companion_holds']
check('inline_file_hold','Before [[File:A.jpg|Caption]] after.',held=True)
check('namespace_target_unknown_notlaundered','[[File:{{unknown}}|Caption]]',held=True)
check('media_alias_hold','[[Image:A.jpg|Caption]]',held=True)
for name,text in [('targettemplate','[[{{PAGENAME}}]]'),('URLtemplate','[https://{{site}}/x Label]'),('targetentity','[[A&amp;B]]'),('malformedentity','[[A&amp|Label]]'),('numericentity','A&#1;B')]:check(name,text,held=True)
r=check('standalone_maintenance_companion','{{Use dmy dates|date=2019}}\n\nWhole prose.','\n\nWhole prose.');assert r['exact_raw_metadata_companions'][0]['raw_parameters'][0]['value_raw']=='2019'
check('metadata_nestedunknown_notlaundered','{{Use dmy dates|date={{unknown}}}}\n\nWhole prose.',held=True)
check('inline_metadata_notdropped','Before {{Use dmy dates|date=2019}} after.',held=True)
r=check('semantic_infobox_rawvalues_retained','{{Infobox settlement|population=174|unknown={{semantic}}}}\n\nVillage prose.','\n\nVillage prose.');assert r['sections'][0]['semantic_companion_holds'] and '{{semantic}}' in r['exact_raw_metadata_companions'][0]['raw']
r=check('shortdescriptionsemanticcompanion','{{Short description|A real summary}}\n\nProse.','\n\nProse.');assert 'A real summary' in r['exact_raw_metadata_companions'][0]['raw']
check('unknown_inline_hold_no_prefix','Good opening. {{unresolved}} More.',held=True)
check('table_content_not_dropped','Opening.\n{|\n| 174\n|}\nAfter.',held=True)
check('quote_template_not_metadata','{{Quote box|quote=Semantic words}}\nRest.',held=True)
check('span_realwords_and_punctuation','in<span data-darkreader-inline-color="" data-darkreader-inline-bgcolor="">line, text</span>.','inline, text.')
check('span_nested_unknown_hold','A<span data-darkreader-inline-color="">{{unknown}}</span>B',held=True)
check('span_unknownattr_hold','A<span onclick="x">words</span>B',held=True)
check('ref_inline_marker_citation_raw','Fact<ref name="a">{{cite web|title=Source|url=https://example.org}}</ref>.','Fact⟦ref:g0:1⟧.')
r=check('forward_reuse_group','A<ref name="x" group="g"/>B<ref name="x" group="g">Source.</ref>','A⟦ref:g1:1⟧B⟦ref:g1:1⟧');assert len(r['reference_resolution']['citation_companions'])==1
check('missing_definition_hold','Fact<ref name="missing"/>',held=True)
check('conflicting_definition_hold','A<ref name="a">One</ref>B<ref name="a">Two</ref>',held=True)
check('unknownancestor_ref_cannotlaunder','{{Unknown|<ref name="a">Source</ref>}}<ref name="a"/>',held=True)
r=check('ref_nested_semanticcite_companion_hold','Fact<ref>{{cite web|title={{unknown}}}}</ref>','Fact⟦ref:g0:1⟧');assert r['sections'][0]['semantic_companion_holds'] and r['sections'][0]['reference_semantic_companion_holds']
check('ref_inside_span_remains_opaque','A<span data-darkreader-inline-color=""><ref name="a">Source</ref></span>B<ref name="a"/>',held=True)
r=page('Good<ref>Source</ref>.\n== Held ==\nMissing<ref name="a"/>');assert r['sections'][0]['provisional_prose_preview']=='Good⟦ref:g0:1⟧.\n' and r['sections'][1]['provisional_prose_preview'] is None;checks.append({'name':'independent_complete_section_not_prefix_salvage','PASS':True})
r=page('é<ref>Source</ref>.');assert r['reference_resolution']['ref_occurrences'][0]['source_byte_span'][0]==2;checks.append({'name':'multibyte_ref_sourcepositions','PASS':True})
r=page('Independent<ref name=y>Y.</ref>.\n== Unknown ==\n{{unknown|<ref name=x>X.</ref>}}');assert r['sections'][0]['provisional_prose_preview']=='Independent⟦ref:g0:1⟧.\n' and r['sections'][1]['provisional_prose_preview'] is None;checks.append({'name':'opaque_named_does_not_poison_unrelated_complete_region','PASS':True})
r=page('Independent<ref name=y>Y.</ref>.\n== Unknown ==\n{{unknown|<ref name="{{bad}}">X.</ref>}}');assert all(s['provisional_prose_preview'] is None for s in r['sections']) and r['reference_limitations']['opaque_page_guard_conservative_not_assertion_of_missing_refs'];checks.append({'name':'opaque_unbound_identity_global_guard_still_wins','PASS':True})
r=page('A<ref name=x>{{cite web|title={{unknown}}}}</ref>.\n== Reuse ==\nB<ref name=x/>.');assert all(s['provisional_prose_preview'] is not None and s['reference_semantic_companion_holds'] and set(s['reference_semantic_companion_holds'])<=set(s['semantic_companion_holds']) for s in r['sections']);checks.append({'name':'nested_citation_component_holds_propagate_to_all_reuse_regions','PASS':True})
r=check('visualeditor_name_binding','A<ref name=":0"/> B<ref name=":0">Source.</ref>.','A⟦ref:g0:1⟧ B⟦ref:g0:1⟧.')
r=check('unresolved_explanatory_footnote_not_bibliography','A<ref>Important {{unknown|qualifier}}.</ref>.',held=True)
r=page('A<ref>{{cite web|title={{unknown}}}}</ref>.')
original=ref.resolve_page
try:
 def modified(*args,**kwargs):
  q=original(*args,**kwargs);q['source_partition'][0]['semantic_companion_holds'].append('fixture_partition_hold');q['citation_companions'][0]['component_holds'].append('fixture_citation_hold');return q
 ref.resolve_page=modified
 q=page('A<ref>{{cite web|title={{unknown}}}}</ref>.');assert {'fixture_partition_hold','fixture_citation_hold'}<=set(q['sections'][0]['semantic_companion_holds']);checks.append({'name':'both_partition_and_citation_component_hold_channels_union','PASS':True})
finally:ref.resolve_page=original
s='A<ref>{{cite web|title=T|url=https://example.org}}</ref> {{As of|2011}}, statement{{sfn|Smith|2020|p=2}}.\n== Sources ==\n* {{cite book|last=Smith|year=2020|title=T}}'
r=page(s);assert r['sections'][0]['provisional_prose_preview']=='A⟦ref:g0:1⟧ As of 2011, statement⟦sfn:1⟧.\n';assert len(r['sections'][0]['source_operations'])==3;checks.append({'name':'ordinary_owned_ref_shortnote_literal_year_same_whole_region','PASS':True})
assert r['bibliography_never_deleted_or_rendered'] and '{{cite book|last=Smith|year=2020|title=T}}' in r['sections'][1]['raw'] and r['sections'][1]['provisional_prose_preview'] is None and not r['sections'][1]['source_operations'];checks.append({'name':'bibliography_raw_retained_never_deleted_or_rendered','PASS':True})
r=page('A{{sfn|Smith|2020}}.\n== Sources ==\n{{cite book|last=Smith|year=2020|title={{unknown}}}}');assert r['sections'][0]['provisional_prose_preview']=='A⟦sfn:1⟧.\n' and r['sections'][0]['shortnote_bibliographic_semantic_companion_holds'];checks.append({'name':'bibliographic_nested_value_component_holds_propagate_to_main','PASS':True})
r=check('year_qualifier_nested_in_citation_never_sourceop','A<ref>{{cite web|title={{As of|2011}}}}</ref>.','A⟦ref:g0:1⟧.');assert all(o['kind']!='literal_year_temporal_qualifier' for o in r['sections'][0]['source_operations'])
check('unsupported_year_options_remain_whole_region_hold','Opening {{As of|2011|lc=y}} ending.',held=True)
check('shortnote_reserved_marker_holds_whole_region','A{{sfn|Smith|2020}} ⟦sfn:1⟧.\n== Sources ==\n{{cite book|last=Smith|year=2020|title=T}}',held=True)
check('reference_reserved_marker_holds_whole_region','A<ref>Source.</ref> ⟦ref:g0:1⟧.',held=True)
for label,ops in [('overlap',[{'source_char_span':[0,2],'raw':'AB','raw_SHA256':core.H('AB'),'replacement':'X'},{'source_char_span':[1,3],'raw':'BC','raw_SHA256':core.H('BC'),'replacement':'Y'}]),('wrongpreimage',[{'source_char_span':[0,2],'raw':'XX','raw_SHA256':core.H('XX'),'replacement':'X'}])]:
 try:core.apply_ops('ABC',0,ops)
 except ValueError:checks.append({'name':'source_operation_'+label+'_refused','PASS':True})
 else:raise AssertionError(label)
try:core.invert_ops('wrong',0,[{'source_char_span':[0,2],'raw':'AB','replacement':'X'}])
except ValueError:checks.append({'name':'operation_inverse_wrong_marker_refused','PASS':True})
else:raise AssertionError('inverse should refuse')
import short_core
oldshort=short_core.resolve_page
try:
 def altered(*args,**kwargs):
  q=oldshort(*args,**kwargs);q['source_partition'][0]['semantic_companion_holds'].append('fixture_short_partition_hold');q['bibliographic_companions'][0]['component_holds'].append('fixture_bibliography_hold');return q
 short_core.resolve_page=altered
 r=page('A{{sfn|Smith|2020}}.\n== Sources ==\n{{cite book|last=Smith|year=2020|title=T}}');assert {'fixture_short_partition_hold','fixture_bibliography_hold'}<=set(r['sections'][0]['semantic_companion_holds']);checks.append({'name':'both_short_partition_and_linked_bibliographic_hold_channels_union','PASS':True})
finally:short_core.resolve_page=oldshort
print(json.dumps({'status'  :'PASS_SYNTHETIC_INTEGRATED_ONLY_NO_NATIVE_APPLICATION','checks':len(checks),'cases':checks},indent=2))
