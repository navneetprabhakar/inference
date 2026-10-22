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
