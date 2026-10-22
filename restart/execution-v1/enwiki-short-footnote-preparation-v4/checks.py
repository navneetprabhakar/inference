from pathlib import Path
import sys,importlib.util,json
P=Path(__file__).resolve().parent;B=P.parent;sys.path[:0]=[str(P),str(B/'tool-dependencies/mwparserfromhell-0.7.2'),str(B/'enwiki-page-local-reference-preparation-v2'),str(B/'enwiki-generic-AST-policy-preparation-v4')]
import short_core as c,mwparserfromhell as m,reference_core as r,policy_core as literal
cases=[]
def run(s):
 q=c.resolve_page(s,m,literal,r);assert ''.join(x['raw'] for x in q['source_partition'])==s
 for x in q['source_partition']+q['short_footnote_occurrences']+q['bibliographic_companions']+q['opaque_contexts']:
  a,b=x['source_char_span'];ba,bb=x['source_byte_span'];assert s[a:b]==x['raw'] and s.encode()[ba:bb]==x['raw'].encode() and c.H(x['raw'])==x['raw_SHA256']
 for sec in q['source_partition']:
  if sec['holds']:assert sec['marker_operations']==[];continue
  start=sec['source_char_span'][0];cursor=0;out=[]
  for op in sec['marker_operations']:
   a,b=op['source_char_span'];a-=start;b-=start;assert a>=cursor and sec['raw'][a:b]==op['raw'];out.extend([sec['raw'][cursor:a],op['replacement_marker']]);cursor=b
  out.append(sec['raw'][cursor:]);changed=''.join(out);cursor=0;delta=0;back=[]
  for op in sec['marker_operations']:
   a,b=op['source_char_span'];pos=a-start+delta;rep=op['replacement_marker'];assert changed[pos:pos+len(rep)]==rep;back.extend([changed[cursor:pos],op['raw']]);cursor=pos+len(rep);delta+=len(rep)-(b-a)
  back.append(changed[cursor:]);assert ''.join(back)==sec['raw']
 return q
def check(n,s,bound=1,held=False):
 q=run(s);assert sum(bool(o.get('bibliography_ID')) for o in q['short_footnote_occurrences'])==bound,(n,q);assert bool(q['source_partition'][0]['holds'])==held,(n,q);cases.append({'name':n,'PASS':True});return q
bib='\n== Sources ==\n* {{cite book|last=Smith|year=2020|title=Book}}'
check('literal_author_year_forward','A{{sfn|Smith|2020|p=3}}.'+bib)
q=check('qualifiers_exact_preserved','A{{sfn|Smith|2020|pp=3–5|loc=Chapter 2}}.'+bib);assert q['short_footnote_occurrences'][0]['qualifiers']['loc']['value_raw']=='Chapter 2'
check('explicit_custom_sfnRef','A{{sfn|Agency Name|2020|loc=2:30}}.\n== Sources ==\n* {{cite AV media|title=Film|publisher=[[Agency Name]]|ref={{sfnRef|Agency Name|2020}}}}')
check('full_validated_date','A{{sfn|Smith|2020}}.\n== Sources ==\n* {{cite news|last=Smith|date=5 June 2020|title=T}}')
check('iso_validated_date','A{{sfn|Smith|2020}}.\n== Sources ==\n* {{cite news|last=Smith|date=2020-02-29|title=T}}')
check('multiple_authors','A{{sfn|Smith|Jones|2020a}}.\n== Sources ==\n* {{cite book|last1=Smith|last2=Jones|year=2020a|title=T}}')
check('missing_key','A{{sfn|Unknown|2020}}.'+bib,bound=0,held=True)
check('duplicate_key_even_identical','A{{sfn|Smith|2020}}.'+bib+'\n* {{cite book|last=Smith|year=2020|title=Book}}',bound=0,held=True)
check('conflicting_key','A{{sfn|Smith|2020}}.'+bib+'\n* {{cite book|last=Smith|year=2020|title=Other}}',bound=0,held=True)
check('unknown_explicitref_no_auto_fallback','A{{sfn|Smith|2020}}.\n== Sources ==\n{{cite book|last=Smith|year=2020|title=T|ref={{unknown}}}}',bound=0,held=True)
check('unknown_binding_ast','A{{sfn|Smith|2020}}.\n== Sources ==\n{{cite book|last={{unknown}}|year=2020|title=T}}',bound=0,held=True)
check('unsupported_short_qualifier','A{{sfn|Smith|2020|ps=Important qualifier}}.'+bib,bound=0,held=True)
check('nested_short_qualifier','A{{sfn|Smith|2020|p={{unknown}}}}.'+bib,bound=0,held=True)
check('two_location_page_fields','A{{sfn|Smith|2020|p=2|pp=3}}.'+bib,bound=0,held=True)
check('duplicate_short_parameter','A{{sfn|Smith|2020|p=2|p=3}}.'+bib,bound=0,held=True)
check('author_case_not_fuzzymatched','A{{sfn|smith|2020}}.'+bib,bound=0,held=True)
check('year_suffix_not_fuzzymatched','A{{sfn|Smith|2020a}}.'+bib,bound=0,held=True)
q=check('nested_nonkey_raw_component_hold','A{{sfn|Smith|2020}}.\n== Sources ==\n{{cite book|last=Smith|year=2020|title={{lang|en|Title}}}}');assert q['source_partition'][0]['semantic_companion_holds'] and '{{lang|en|Title}}' in q['bibliographic_companions'][0]['raw']
check('invalid_date','A{{sfn|Smith|2020}}.\n== Sources ==\n{{cite book|last=Smith|date=2020-02-31|title=T}}',bound=0,held=True)
check('year_date_conflict','A{{sfn|Smith|2020}}.\n== Sources ==\n{{cite book|last=Smith|year=2020|date=5 June 2019|title=T}}',bound=0,held=True)
check('opaque_key_shadow','A{{sfn|Smith|2020}}.'+bib+'\n{{unknown|{{cite book|last=Smith|year=2020|title=Hidden}}}}',bound=0,held=True)
check('opaque_unbound_key_shadow','A{{sfn|Smith|2020}}.'+bib+'\n{{unknown|{{cite book|last={{unknown}}|year=2020|title=Hidden}}}}',bound=0,held=True)
check('no_author_cannot_match_supported_author_year_key','A{{sfn|Smith|2020}}.'+bib+'\n<ref>{{cite web|url=https://example.org|title=No author or date}}</ref>')
check('nested_sfn_in_explanatory_note_not_silently_detached','A<ref>Qualifier {{sfn|Smith|2020}}</ref>.'+bib,bound=0,held=True)
check('nested_ref_in_bibliography','A{{sfn|Smith|2020}}.\n== Sources ==\n{{cite book|last=Smith|year=2020|title=A<ref>Nested</ref>}}',bound=0,held=True)
check('multibyte_source_offsets','é{{sfn|Smith|2020|p=三}}.'+bib)
check('marker_collision','A{{sfn|Smith|2020}}. ⟦sfn:1⟧'+bib,held=True)
try:c.resolve_page('Text',m,literal,r,[[1,4]])
except ValueError:cases.append({'name':'saved_partition_mismatch_refused','PASS':True})
else:raise AssertionError('partition mismatch')
q=check('ordinary_validated_ref_no_sfn_no_new_hold','A<ref>{{cite web|title=T|url=https://example.org}}</ref>.',bound=0);assert q['reference_handoff']['structurally_owned_reference_occurrences']==1
check('ordinary_ref_and_unrelated_sfn_no_requarantine','A<ref>{{cite web|title=T|url=https://example.org}}</ref>B{{sfn|Smith|2020}}.'+bib)
check('validated_ref_can_supply_exact_page_bibliographic_key','A<ref>{{cite book|last=Smith|year=2020|title=T}}</ref>B{{sfn|Smith|2020}}.')
q=check('unknown_nested_key_in_owned_ref_without_sfn_component_only','A<ref>{{cite web|title=T|ref={{unknown}}}}</ref>.',bound=0);assert q['source_partition'][0]['semantic_companion_holds'] and q['unbound_bibliographic_global_shadow']
check('unknown_owned_ref_key_still_shadows_actual_sfn','A<ref>{{cite web|title=T|ref={{unknown}}}}</ref>B{{sfn|Smith|2020}}.'+bib,bound=0,held=True)
s='A<ref>Source.</ref>.';rp=r.resolve_page(s,m,literal_policy=literal)
for bad in ['source','occurrence']:
 import copy
 wrong=copy.deepcopy(rp)
 if bad=='source':wrong['source_SHA256']='0'*64
 else:wrong['ref_occurrences'][0]['raw_SHA256']='0'*64
 try:c.resolve_page(s,m,literal,r,reference_plan=wrong)
 except ValueError:cases.append({'name':'wrong_reference_handoff_'+bad+'_refused','PASS':True})
 else:raise AssertionError('wrong handoff')
# Only a finite single author-wikilink failure with unambiguous literal year/date
# becomes a potential ANY_AUTHOR_BASE_YEAR shadow, never a bibliography source.
base='{{cite book|last=Smith|year=2012|title=Valid}}'
linked='{{cite web|author=[[Unknown Author]]|date=26 December 2020|title=Opaque}}'
q=check('linked_author_2020_does_not_globally_shadow_2012','A{{sfn|Smith|2012}}.'+base+linked);assert not q['unbound_bibliographic_global_shadow'] and len(q['partial_bibliographic_shadow_constraints'])==1 and q['bibliographic_companions'][-1]['component_holds']
for y in ['2020','2020a']:
 q=check('unknown_any_author_same_base_year_'+y,'A{{sfn|Different|'+y+'}}.{{cite book|last=Different|year='+y+'|title=T}}'+linked,bound=0,held=True);assert 'potential_bibliography_base_year_shadow_guard' in q['source_partition'][0]['holds']
for bad in ['{{cite web|author=[[Unknown]]|date={{unknown}}}}','{{cite web|author=[[Unknown]]|date=2020|ref={{unknown}}}}','{{cite web|author=[[Unknown]]|date=2020|year=2019}}','{{cite web|author=[[Unknown|{{unknown}}]]|date=2020}}','{{cite web|author=[[Unknown]]|date=2020|author=other}}','{{cite web|author=[[Unknown]]|date=2020|title=<ref>Hidden</ref>}}']:
 q=check('partial_scope_unknown_falls_back_global_'+str(len(cases)),'A{{sfn|Smith|2012}}.'+base+bad,bound=0,held=True);assert q['unbound_bibliographic_global_shadow']
# Exact observed author-value shapes copied as literals into synthetic controls;
# no savedsource resolver application. Preserve whitespace in the recorded rawvalue.
for author in ['[[Tsutomu Nishioka]] ','[[Robert R. King]] ','[[Chris Smith (New Jersey politician)|Chris Smith]] ',' \t[[Some Person]] \n']:
 linked='{{cite web|author='+author+'|date=26 December 2020|title=T}}'
 q=check('only_surrounding_whitespace_author_inspection_'+str(len(cases)),'A{{sfn|Smith|2012}}.'+base+linked);assert not q['unbound_bibliographic_global_shadow'] and q['partial_bibliographic_shadow_constraints'][0]['constraint']['unresolved_author_raw']==author
for author in ['Prefix [[Some Person]] ','[[Some Person]] Suffix','[[One]][[Two]] ','<!--x-->[[Name]] ','[[Name]]<b>extra</b>']:
 q=check('semantic_author_extra_not_whitespace_'+str(len(cases)),'A{{sfn|Smith|2012}}.'+base+'{{cite web|author='+author+'|date=2020|title=T}}',bound=0,held=True);assert q['unbound_bibliographic_global_shadow']
print(json.dumps({'status' :'PASS_SYNTHETIC_ONLY_NO_NATIVE_SOURCE_APPLICATION','count':len(cases),'cases':cases},indent=2))
