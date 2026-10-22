import json
import render as r
from lxml import etree
cases=[]
def test(body):
 raw=('<document xmlns="'+r.CN+'"><title>Fixture</title><content>'+body+'</content></document>').encode();expected={'module_ID':'fixture','native_path':'fixture.cnxml','expected_bytes':len(raw),'expected_Git_blob_SHA1':r.generic.git_blob(raw),'collection_appearances':[]};return raw,r.render(raw,expected)
raw,(out,text,_,ast)=test('<para>Onl<emphasis>in</emphasis>e information.</para><glossary><definition><term>state</term><meaning>a political organization</meaning></definition></glossary>');assert 'Online information.' in text and 'state: a political organization' in text;cases+=['inline_split_word_adjacency','term_meaning_boundary']
raw,(out,text,_,_)=test('<list><item><para>First</para><para>Second</para></item><item>Third</item></list>');assert 'First' in text and 'Second' in text and '• Third' in text;cases.append('list_item_and_nested_paragraph_boundaries')
raw,(out,text,_,_)=test('<para>See <link target-id="fig"/> next.</para><figure id="fig"><title>Literal figure title</title><media alt="Native alternative"><image src="../x.png"/></media><caption>Exact credit.</caption></figure>');assert '[reference:' in text and 'Literal figure title' in text and 'Exact credit.' in text and 'Native alternative' in text;assert any(d.get('local_ID_resolved') for d in out['dependencies']);cases.append('empty_xref_literal_marker_target_identity_figure_credit_and_alt_preserved')
raw,(out,text,_,_)=test('<exercise><problem><link class="os-embed" url="#exercise/native-id"/></problem></exercise><para>Dependent paragraph remains.</para>');assert '[UNRESOLVED EMBEDDED QUESTION: #exercise/native-id]' in text and 'Dependent paragraph remains.' in text and 'unresolved_embedded_question' in out['holds'];cases.append('missing_question_explicit_hold_dependent_paragraph_not_stripped')
raw,(out,text,view,_)=test('<para>Visit <link url="https://example.invalid?a=1&amp;b=2">native label</link>.</para><table><title>Table title</title><tgroup><tbody><row><entry>left</entry><entry>right</entry></row></tbody></tgroup><caption>Table caption</caption></table>');assert 'native label' in text and 'https://example.invalid?a=1&amp;b=2' not in text and 'https://example.invalid?a=1&b=2' in text and 'left | right' in text and 'Table caption' in text and 'table_layout_semantic_review' in out['holds'];assert '<a ' not in view;cases.append('literal_external_reference_table_boundaries_no_click_or_fetch')
raw,(out,text,_,_)=test('<para attr="x &gt; y">é<emphasis>word</emphasis> tail</para>');
for b in out['blocks']:assert r.sha(raw[b['source_start_byte']:b['source_end_byte']])==b['source_exact_subtree_sha256']
cases.append('exact_original_byte_spans_unicode_quoted_gt_and_self_closing')
print(json.dumps({'status':'PASS_FOCUSED_SYNTHETIC_PROFILE','case_count':len(cases),'cases':cases}))
