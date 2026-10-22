"""Synthetic-only semantic composition checks, no retained bodies."""
from pathlib import Path
import sys,json
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import run
m,core=run.parser_preflight();cases=[]
def examine(name,text,available=None,semantic=None):
 f=core.sections(text,m)
 assert f['exact_roundtrip'] and ''.join(s['raw'] for s in f['sections'])==text
 for s in f['sections']:
  a,b=s['source_char_span'];ba,bb=s['source_byte_span'];assert text[a:b]==s['raw'] and text.encode()[ba:bb]==s['raw'].encode();assert s['no_admission']
 if available is not None:assert (f['sections'][0]['provisional_prose_preview'] is not None)==available,(name,f['sections'][0])
 if semantic is not None:assert bool(f['sections'][0]['reference_content_semantic_holds'])==semantic,(name,f['sections'][0])
 cases.append(name);return f
f=examine('cite_only_exact_named_definition_reuse','Claim<ref name="A">{{cite book|title=Report|last=Author|year=2020|page=2}}</ref>.\n== Other ==\nSecond claim<ref name="A"/>.',True,False)
assert f['sections'][0]['provisional_prose_preview'].count('⟦ref:g0:1⟧')==1 and f['sections'][1]['provisional_prose_preview'].count('⟦ref:g0:1⟧')==1
examine('free_explanatory_note_entire_unit_held','Claim<ref>The value excludes offshore operations.</ref>.',False,True)
examine('mixed_note_and_citation_held','Claim<ref>The measurement is disputed. {{cite book|title=Report}}</ref>.',False,True)
examine('quote_parameter_semantic_hold','Claim<ref>{{cite book|title=Report|quote=Excludes offshore operations.}}</ref>.',False,True)
examine('unknown_field_semantic_hold','Claim<ref>{{cite book|title=Report|newfield=Unknown semantics}}</ref>.',False,True)
examine('group_note_hold','Claim<ref group="note">{{cite book|title=Report}}</ref>.',False,True)
examine('missing_citation_identity_hold','Claim<ref>{{cite book|author=Person}}</ref>.',False,True)
examine('nested_title_unknown_hold','Claim<ref>{{cite book|title={{lang|fr|Title}}}}</ref>.',False,True)
examine('duplicate_field_binding_stillheld','Claim<ref>{{cite book|title=A|title=B}}</ref>.',False)
examine('missing_ref_definition_stillheld','Claim<ref name="missing"/>.',False)
examine('conflicting_definition_stillheld','Claim<ref name="A">{{cite book|title=A}}</ref><ref name="A">{{cite book|title=B}}</ref>.',False)
f=examine('same_note_reuse_holds_other_dependent_H2','Claim<ref name="N">An important qualification.</ref>.\n== Other ==\nSecond claim<ref name="N"/>.',False,True)
assert f['sections'][1]['reference_content_semantic_holds'] and f['sections'][1]['provisional_prose_preview'] is None
f=examine('note_not_used_elsewhere_does_not_hold_independent_whole_H2','Claim<ref>Qualification.</ref>.\n== Independent ==\nA separate complete paragraph.',False,True)
assert f['sections'][1]['provisional_prose_preview'] is not None
f=examine('standalone_date_maintenance_exact_raw_companion','{{Use dmy dates|date=May 2020}}\nComplete paragraph.',True,False)
assert f['exact_raw_metadata_companions'][0]['raw']=='{{Use dmy dates|date=May 2020}}'
examine('inline_maintenance_not_detached','Complete {{Use dmy dates}} paragraph.',False)
f=examine('standalone_infobox_all_values_and_independence_hold','{{Infobox settlement|name=Place|population_total=100}}\nComplete paragraph.',True)
assert f['sections'][0]['component_independence_holds'] and f['exact_raw_metadata_companions'][0]['no_values_discarded']
examine('unknown_infobox_name_not_generic_stripped','{{Infobox unknown schema|name=Place}}\nComplete paragraph.',False)
for literal in ['{{convert|5|km}}','{{lang|fr|Nom}}','{{reign|123|456}}']:
 examine('substantive_inline_'+literal,'Complete '+literal+' paragraph.',False)
examine('subject_list_not_keyword_prose','* A referenced destination\n* Another destination',False)
f=examine('plain_ref_bibliographic_looking_text_not_assumed_citeonly','Claim<ref>Author, Report (2020), p. 2.</ref>.',False,True)
examine('numbered_author_fields_schema','Claim<ref>{{cite book|title=T|last1=A|first1=B|year=2000}}</ref>.',True,False)
examine('parameter129_unknown','Claim<ref>{{cite book|title=T|last129=A}}</ref>.',False,True)
examine('shortnote_unknown_bibfield_propagation','Claim{{sfn|Smith|2000}}.\n== Sources ==\n* {{cite book|last=Smith|year=2000|title=T|unknown=Qualifies}}',False,True)
examine('shortnote_quote_bibfield_propagation','Claim{{sfn|Smith|2000}}.\n== Sources ==\n* {{cite book|last=Smith|year=2000|title=T|quote=Important qualification}}',False,True)
examine('encoded_reserved_marker_injection_stillheld','Claim&#x27e6;ref:g0:1⟧<ref>{{cite book|title=T}}</ref>.',False)
examine('defaultsort_parameter_schema_refusal_not_laundered','{{DEFAULTSORT:Example|bad=value}}\nComplete paragraph.',False,True)
print(json.dumps({'status':'PASS_SEMANTIC_COMPONENT_SYNTHETIC_ONLY','checks':len(cases),'cases':cases,'retained_source_reads':0},indent=2))
