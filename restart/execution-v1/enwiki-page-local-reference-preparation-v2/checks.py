"""Synthetic references only. No retained native page resolved/rendered."""
import pathlib,sys,importlib.util,json,hashlib
H=pathlib.Path(__file__).resolve().parent;B=H.parent;T=B/'tool-dependencies/mwparserfromhell-0.7.2';sys.path.insert(0,str(T));sys.path.insert(0,str(H));import mwparserfromhell as m,reference_core as r
sp=importlib.util.spec_from_file_location('frozen_literal_validation',B/'enwiki-generic-AST-policy-preparation-v4/policy_core.py');v=importlib.util.module_from_spec(sp);sp.loader.exec_module(v);cases=[]
assert m.parser.use_c and pathlib.Path(m.__file__).resolve().is_relative_to(T.resolve())
def plan(s):
 p=r.resolve_page(s,m,literal_policy=v);assert p['source_SHA256']==r.H(s)
 assert ''.join(x['raw'] for x in p['source_partition'])==s
 for x in p['source_partition']+p['ref_occurrences']:
  a,b=x['source_byte_span'];assert s.encode()[a:b]==x['raw'].encode() and r.H(x['raw'])==x['raw_SHA256']
 for c in p['citation_companions']:
  for d in c['definitions']:
   x=d['content'];a,b=x['source_byte_span'];assert s.encode()[a:b]==x['raw'].encode()
 return p

def check(name,s,held=False,companions=None,markers=None):
 p=plan(s);hs=[x['holds'] for x in p['source_partition']]
 assert bool(any(hs))==held,(name,p)
 if companions is not None:assert len(p['citation_companions'])==companions,(name,p)
 if markers is not None:assert [x['marker'] for x in p['ref_occurrences']]==markers
 for sec in p['source_partition']:
  proxy=r.synthetic_section_proxy(sec)
  if sec['holds']:assert proxy is None and sec['marker_operations']==[]
  else:
   # Exact inverse from ordered source-bound operations and marker-length positions.
   rebuilt=[];cursor=0;shift=0
   for op in sec['marker_operations']:
    a,b=op['source_char_span'];a-=sec['source_char_span'][0];b-=sec['source_char_span'][0];x=a+shift;assert proxy[x:x+len(op['replacement_marker'])]==op['replacement_marker'];rebuilt.extend([proxy[cursor:x],op['raw']]);cursor=x+len(op['replacement_marker']);shift+=len(op['replacement_marker'])-(b-a)
   rebuilt.append(proxy[cursor:]);assert ''.join(rebuilt)==sec['raw']
 cases.append({'name':name,'PASS':True});return p
check('unnamed_definition','Text<ref>Plain citation.</ref>.',companions=1,markers=['⟦ref:g0:1⟧'])
check('named_definition_reuse','A<ref name="a">Citation.</ref> B<ref name=a/>.',companions=1,markers=['⟦ref:g0:1⟧','⟦ref:g0:1⟧'])
check('forward_reuse_across_complete_H2','A<ref name=x/>.\n== Sources ==\nB<ref name=x>Citation.</ref>.',companions=1,markers=['⟦ref:g0:1⟧','⟦ref:g0:1⟧'])
check('same_name_distinct_groups','A<ref name=x group=a>One.</ref>B<ref name=x group=b>Two.</ref>C<ref group=a name=x/>.',companions=2,markers=['⟦ref:g1:1⟧','⟦ref:g2:1⟧','⟦ref:g1:1⟧'])
check('repeated_identical_defs_preserve_both','A<ref name=x>Same.</ref>B<ref name="x">Same.</ref>',companions=1)
check('unnamed_identical_not_deduped','A<ref>Same.</ref>B<ref>Same.</ref>',companions=2)
check('missing_definition','A<ref name=x/>.',held=True,companions=0)
check('cross_section_conflict_all_affected','A<ref name=x>One.</ref>\n== Other ==\nB<ref name=x>Two.</ref>\n== Reuse ==\nC<ref name=x/>.',held=True,companions=0)
check('groups_missing_not_borrowed','A<ref name=x group=a>One.</ref>B<ref name=x group=b/>',held=True,companions=1)
check('empty_name_hold','A<ref name="">Citation.</ref>',held=True)
check('unnamed_reuse_hold','A<ref/>',held=True)
check('numeric_name_hold','A<ref name=12>Citation.</ref>',held=True)
check('nonliteral_name_hold','A<ref name="{{x}}">Citation.</ref>',held=True)
check('duplicate_name_attr_hold','A<ref name=x name=y>Citation.</ref>',held=True)
check('unknown_attribute_cannot_shadow_valid','A<ref name=x>First.</ref>\n== Other ==\nB<ref name=x follow=x>Other.</ref>',held=True,companions=0)
check('unknown_template_ref_cannot_define_or_shadow','A<ref name=x/>\n== Other ==\n{{unknown|<ref name=x>Hidden.</ref>}}',held=True,companions=0)
check('ref_in_link_context_not_laundered','A<ref name=x>Known.</ref>[[A|<ref name=x>Hidden.</ref>]]',held=True,companions=0)
check('unsupported_list_definitions_explicit','A<ref name=x/>\n== Notes ==\n<references><ref name=x>Citation.</ref></references>',held=True,companions=0)
check('reference_list_display_not_silently_dropped','A<ref name=x>Citation.</ref>\n== Notes ==\n<references/>',held=True,companions=1)
check('reflist_template_remains_unsupported_owner_integration_dependency','A<ref>Citation.</ref>{{reflist}}',companions=1)
check('literal_cite_web_fields_and_raw_URL','A<ref>{{cite web|url=https://example.org/?a=1&b=2|title=A &amp; B|date=1 May 2020}}</ref>.',companions=1)
check('literal_cite_news','A<ref>{{cite news|title=News|work=Paper|date=2020}}</ref>',companions=1)
p=check('nested_citation_value_exact_raw_component','A<ref>{{cite web|title={{unknown|x}}}}</ref>',companions=1);assert p['source_partition'][0]['semantic_companion_holds'] and p['citation_companions'][0]['definitions'][0]['content']['raw']=='{{cite web|title={{unknown|x}}}}'
check('malformed_citation_literal_entity_hold','A<ref>{{cite web|title=A&amp}}</ref>',held=True)
check('invalid_numeric_citation_entity_hold','A<ref>{{cite web|title=A&#xD800;}}</ref>',held=True)
check('duplicate_citation_parameter_whitespace_hold','A<ref>{{cite web|url=https://a.org| url =https://b.org}}</ref>',held=True)
check('unsupported_citation_template_hold','A<ref>{{unverified|foo=bar}}</ref>',held=True)
check('nested_reference_hold','A<ref>Outer<ref name=x/>citation.</ref>',held=True)
check('inline_formatting_offset','é <b>Word<ref name=x>Citation.</ref></b> end.',companions=1)
check('wiki_italics_offset',"é ''Word<ref>Citation.</ref>''.",companions=1)
check('malformed_unparsed_ref_Text_cannot_shadow','A<ref name=x>Known.</ref>\n== Other ==\n<ref name=x broken',held=True,companions=0)
check('reserved_marker_collision','A<ref>Citation.</ref> ⟦ref:g0:1⟧',held=True)
p=plan('No references.');assert not p['ref_occurrences'] and not p['citation_companions'];cases.append({'name':'no_reference_no_fake_companion','PASS':True})
s='Lead<ref>Citation.</ref>\n== Next ==\nWhole.'
try:r.resolve_page(s,m,expected_regions=[[0,len(s)]],literal_policy=v)
except ValueError:cases.append({'name':'saved_region_mismatch_refused','PASS':True})
else:raise AssertionError('expected saved partition refusal')
try:r.resolve_page(s,m)
except ValueError:cases.append({'name':'missing_pinned_literal_policy_refused','PASS':True})
else:raise AssertionError('expected literal policy refusal')
for unresolved in ['{{sfn|Smith|2020}}','{{refn|Unbound footnote.}}','{{efn|Unbound endnote.}}','{{reflist}}']:
 p=plan('A<ref>Literal source.</ref>'+unresolved);proxy=r.synthetic_section_proxy(p['source_partition'][0]);assert unresolved in proxy and p['prior_structural_holds_cleared'] is False
 result=v.sections(proxy,m);assert result['sections'][0]['preview'] is None
 cases.append({'name':'unbound_semantic_template_retained_and_base_policy_hold_'+unresolved.split('|')[0],'PASS':True})
p=plan('A<ref name=x>Citation.</ref> B<ref name=x/>.');assert len(p['citation_companions'][0]['definitions'])==1 and p['citation_companions'][0]['occurrence_indices']==[0,1];cases.append({'name':'definition_source_with_reuse_complete_mapping','PASS':True})
p=check('visualeditor_quoted_colon_zero','A<ref name=":0"/>B<ref name=":0">Source.</ref>',companions=1,markers=['⟦ref:g0:1⟧','⟦ref:g0:1⟧'])
check('unquoted_colon_name_conservative_hold','A<ref name=:0>Source.</ref>',held=True)
check('attribute_entity_not_guessed','A<ref name="A&amp;B">Source.</ref>',held=True)
p=check('opaque_named_does_not_poison_other_key','A<ref name=y>Y.</ref>\n== Unknown ==\n{{unknown|<ref name=x>X.</ref>}}',held=True,companions=1);assert not p['source_partition'][0]['holds'] and p['opaque_propagation']['exact_named_keys']==[['','x']]
p=check('opaque_unnamed_does_not_poison_independent_unnamed','A<ref>Known.</ref>\n== Unknown ==\n{{unknown|<ref>Hidden.</ref>}}',held=True,companions=1);assert not p['source_partition'][0]['holds']
p=check('opaque_group_not_other_group','A<ref name=x group=other>Y.</ref>\n== Unknown ==\n{{unknown|<ref name=x group=hidden>X.</ref>}}',held=True,companions=1);assert not p['source_partition'][0]['holds']
p=check('unbound_opaque_retains_global_guard','A<ref name=y>Y.</ref>\n== Unknown ==\n{{unknown|<ref name="{{bad}}">X.</ref>}}',held=True,companions=0);assert p['opaque_propagation']['unbound_identity_global_guard']
p=check('nested_reference_cannot_shadow_other_known_key','A<ref name=y>Known.</ref>\n== Bad ==\n<ref name=x>Outer<ref name=y>Hidden.</ref></ref>',held=True,companions=0)
p=check('recognized_nested_bibliography_does_not_become_missing_definition','A<ref name=x>{{cite book|title=[[A|Label]]|date={{date|2020}}}}</ref>B<ref name=x/>',companions=1);assert all(not o['holds'] for o in p['ref_occurrences']) and p['source_partition'][0]['semantic_companion_holds']
p=check('footnote_qualifier_preserved_exact','A<ref>Contrary to earlier accounts, this is uncertain. {{cite news|title=Source}}</ref>',companions=1);assert p['citation_companions'][0]['definitions'][0]['content']['raw'].startswith('Contrary to earlier accounts')
check('unknown_semantic_footnote_still_held','A<ref>Important {{unknown|qualifier}}.</ref>',held=True)
p=check('opaque_list_group_inherited_for_shadow_guard','A<ref name=x group=note>Known.</ref>\n== Notes ==\n<references group=note><ref name=x>Hidden.</ref></references>',held=True,companions=0);assert p['opaque_propagation']['exact_named_keys']==[['note','x']]
print(json.dumps({'status' :'PASS_SYNTHETIC_PAGE_LOCAL_REF_CONTROLS_NO_RETAINED_SOURCE_RUN','count':len(cases),'cases':cases},indent=2))
