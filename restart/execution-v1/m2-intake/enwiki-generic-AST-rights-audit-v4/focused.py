"""Independent cross-context synthetic AST controls; never parse retained sources."""
import pathlib,sys,importlib.util,json,hashlib
B=pathlib.Path(__file__).resolve().parents[2];P=B/'enwiki-generic-AST-policy-preparation-v4';H=pathlib.Path(__file__).resolve().parent;T=B/'tool-dependencies/mwparserfromhell-0.7.2';sys.path.insert(0,str(T));import mwparserfromhell as m
assert pathlib.Path(m.__file__).resolve().is_relative_to(T.resolve()) and m.parser.use_c and m.__version__=='0.7.2';spec=importlib.util.spec_from_file_location('audited_policy4',P/'policy_core.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c);results=[]
def test(src,held,expected=None):
 r=c.sections(src,m);assert ''.join(u['raw'] for u in r['sections'])==src
 for u in r['sections']:
  a,b=u['source_byte_span'];assert src.encode()[a:b]==u['raw'].encode() and ''.join(n['raw'] for n in u['top_nodes'])==u['raw']
 u=r['sections'][0];assert (u['preview'] is None)==held,(src,u)
 if held:assert u['preview_SHA256'] is None and u['holds'] and u['status']=='HELD_COMPLETE_SECTION_NO_PARTIAL_SILENT_DROP'
 if expected is not None:assert u['preview']==expected
 results.append({'source':src,'held':held,'preview':u['preview'],'holds':u['holds'],'source_inverse_verified':True})
for src in ['Lead [[{{PAGENAME}}]].','Lead [https://{{site}}/page Label].','Lead [[Foo|{{unknown}}]].','Lead [[A&amp;B]].','Lead [[A&amp]].','Lead [[A&amp|Label]].','Lead [https://example.org/a&amp Label].','Lead [[{{{target}}}|Readable]].','Lead [[A<!--comment-->B|Readable]].','Lead [https://{{{host}}}/path Label].','Lead [[A|<b>{{unknown}}</b>]].','Lead [https://example.org <i>{{unknown}}</i>].','== [[{{unknown}}|Heading]] ==\nComplete paragraph.','Complete opening.\n\nLate [[A|{{unknown}}]].','Lead [[A&#xD800;|Readable]].','Lead [https://example.org/&#999999999999999999999; Readable].']:
 test(src,True)
for src,out in [('Lead [[AT&T]].','Lead AT&T.'),('[https://example.org/?a=1&b=2 Label]','Label (https://example.org/?a=1&b=2)'),('in[[line|line]] text.','inline text.'),('A &amp; B &#65; &#x1F600;','A & B A 😀')]:test(src,False,out)
r=c.sections('é lead {{unknown}}\n== Complete ==\nWhole first paragraph.\n\nWhole last paragraph.',m);assert r['sections'][0]['preview'] is None and r['sections'][1]['preview']=='Complete\n\nWhole first paragraph.\n\nWhole last paragraph.';assert ''.join(x['raw'] for x in r['sections']).encode()==r['sections'][0]['raw'].encode()+r['sections'][1]['raw'].encode();results.append({'separate_H2_section_preserved_while_complete_lead_held':True})
o={'status':'PASS21_INDEPENDENT_CROSS_CONTEXT_SYNTHETIC_CHECKS_NO_RETAINED_SOURCE_PARSE','count':len(results),'cases':results,'policy_core_SHA256':hashlib.sha256((P/'policy_core.py').read_bytes()).hexdigest(),'source_records_ASTparsed':0};(H/'focused-result.json').write_text(json.dumps(o,indent=2)+'\n');print(json.dumps({'checks':len(results),'SHA256':hashlib.sha256((H/'focused-result.json').read_bytes()).hexdigest()}))
