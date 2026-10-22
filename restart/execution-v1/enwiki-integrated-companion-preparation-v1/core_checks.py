from pathlib import Path
import sys,json
B=Path(__file__).resolve().parent.parent;sys.path[:0]=[str(Path(__file__).resolve().parent),str(B/'tool-dependencies/mwparserfromhell-0.7.2'),str(B/'enwiki-generic-AST-policy-preparation-v4'),str(B/'enwiki-page-local-reference-preparation-v1'),str(B/'enwiki-structural-companion-policy-preparation-v1')]
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
check('ref_nested_semanticcite_hold','Fact<ref>{{cite web|title={{unknown}}}}</ref>',held=True)
check('ref_inside_span_remains_opaque','A<span data-darkreader-inline-color=""><ref name="a">Source</ref></span>B<ref name="a"/>',held=True)
r=page('Good<ref>Source</ref>.\n== Held ==\nMissing<ref name="a"/>');assert r['sections'][0]['provisional_prose_preview']=='Good⟦ref:g0:1⟧.\n' and r['sections'][1]['provisional_prose_preview'] is None;checks.append({'name':'independent_complete_section_not_prefix_salvage','PASS':True})
r=page('é<ref>Source</ref>.');assert r['reference_resolution']['ref_occurrences'][0]['source_byte_span'][0]==2;checks.append({'name':'multibyte_ref_sourcepositions','PASS':True})
print(json.dumps({'status':'PASS_SYNTHETIC_INTEGRATED_ONLY_NO_NATIVE_APPLICATION','checks':len(checks),'cases':checks},indent=2))
