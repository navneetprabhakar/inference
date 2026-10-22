import sys,json,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
TARGET=HERE.parent/'tool-dependencies/mwparserfromhell-0.7.2'
sys.path.insert(0,str(TARGET));sys.path.insert(0,str(HERE))
import mwparserfromhell as m
from policy_core import sections
assert m.__version__=='0.7.2' and Path(m.__file__).resolve().is_relative_to(TARGET.resolve())
assert m.parser.use_c
cases=[]
def check(name,s,expected=None,held=False,n=1):
 r=sections(s,m);assert len(r['sections'])==n
 assert ''.join(x['raw'] for x in r['sections'])==s
 assert ''.join(x['raw'] for x in r['sections']).encode()==s.encode()
 for u in r['sections']:
  a,b=u['source_byte_span'];assert s.encode()[a:b]==u['raw'].encode();assert ''.join(x['raw'] for x in u['top_nodes'])==u['raw']
 if expected is not None:assert r['sections'][0]['preview']==expected,(name,r)
 if held:assert r['sections'][0]['preview'] is None and r['sections'][0]['holds']
 cases.append({'name':name,'PASS':True})
for name,value in [('NUL','&#0;'),('C0','&#1;'),('surrogate','&#xD800;'),('outofrange','&#x110000;'),('DEL','&#127;'),('C1','&#x80;'),('unterminated_numeric','&#12'),('malformed_hex','&#xzz;'),('unknown_named','&notAnEntity;'),('unterminated_amp','&amp')]:check('invalid_entity_'+name,'A'+value+'B' if name not in ('unterminated_numeric','unterminated_amp') else 'A'+value,held=True)
check('huge_numeric_entity_whole_hold','A&#'+('9'*5000)+';B',held=True)
check('legitimate_numeric_entities','&#65;&#x1F600;','A😀')
check('ordinary_ampersand','AT&T and A & B.','AT&T and A & B.')
for name,value in [('template_implicit','[[{{PAGENAME}}]]'),('template_explicit','[[{{PAGENAME}}|Readable label]]'),('argument_implicit','[[{{{target}}}]]'),('argument_explicit','[[{{{target}}}|Readable label]]'),('entity_implicit','[[A&amp;B]]'),('entity_explicit','[[A&amp;B|Readable label]]'),('comment_destination','[[A<!-- note -->B|Readable]]'),('external_template','[https://{{site}}/page Label]'),('external_argument','[https://{{{site}}}/page Label]'),('external_entity','[https://example.org/a&amp;b Label]')]:check('destination_AST_'+name,'Lead '+value+'.',held=True)
check('ordinary_query_URL','[https://example.org/?a=1&b=2 Label]','Label (https://example.org/?a=1&b=2)')
check('whole_paragraphs_punctuation','First paragraph.\n\nSecond paragraph!','First paragraph.\n\nSecond paragraph!')
check('inline_link_no_inserted_spaces','in[[line|line]] text.','inline text.')
check('link_punctuation','[[Alpha|A]], [[Beta]].','A, Beta.')
check('literal_target','[[New York]]','New York')
check('nonASCII_byte_offsets','é [[Éire|Éire]]','é Éire')
check('comment_exact_inverse_adjacency','in<!-- source comment -->line','inline')
check('entity','A &amp; B','A & B')
check('italic_bold',"A ''word'' and '''bold'''.",'A word and bold.')
check('br','A<br />B','A\nB')
check('label_and_literal_external_URL','[https://example.org/a Label]','Label (https://example.org/a)')
check('bare_external_URL','https://example.org/a','https://example.org/a')
check('whole_section_template_hold','Good paragraph.\n\n{{value|x}}\n\nOther paragraph.',held=True)
check('nested_template_link_hold','[[A|{{lang|en|text}}]]',held=True)
check('ref_definition_hold','Fact.<ref name="a">Source.</ref>',held=True)
check('ref_reuse_hold','Fact.<ref name="a"/>',held=True)
check('unknown_extension_hold','A<math>x+y</math>B',held=True)
check('list_whole_section_hold','* First\n* Second',held=True)
check('table_whole_section_hold','{|\n| cell\n|}',held=True)
check('media_hold','[[File:A.jpg|caption]]',held=True)
check('category_hold','[[Category:A]]',held=True)
check('implicit_underscore_display_hold','[[New_York]]',held=True)
check('implicit_fragment_display_hold','[[A#B]]',held=True)
check('empty_pipe_hold','[[A|]]',held=True)
check('numbered_external_link_hold','[https://example.org]',held=True)
check('formatting_crosses_heading_hold','<b>Start\n== Heading ==\nEnd</b>',held=True)
check('unsupported_tag_hold','<div>A</div>',held=True)
check('heading_partition_allbytes','Lead.\n\n== One ==\nWhole paragraph.\n=== Child ===\nMore.\n== Two ==\nEnd.',n=3)
r=sections('{{infobox}}\n== Whole ==\nA complete paragraph.\n\nAnother one.',m);assert r['sections'][0]['preview'] is None and r['sections'][1]['preview']=='Whole\n\nA complete paragraph.\n\nAnother one.';cases.append({'name':'held_lead_does_not_delete_independent_complete_section','PASS':True})
# No partial prefix emitted when a late dependency is unresolved.
r=sections('Full opening.\n\nTrailing {{unknown}}',m);assert r['sections'][0]['preview'] is None;cases.append({'name':'late_dependency_no_partial_preview','PASS':True})
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY_NO_NATIVE_EXTRACTION','checks':len(cases),'cases':cases,'parser_origin':m.__file__,'compiled_C_tokenizer':True},indent=2))
