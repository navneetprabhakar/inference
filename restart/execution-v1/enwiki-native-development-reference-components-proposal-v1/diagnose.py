"""Synthetic reference-content diagnostics, no retained source access."""
from pathlib import Path
import sys,json,hashlib,importlib.util
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
sys.path.insert(0,str(BASE/'tool-dependencies/mwparserfromhell-0.7.2'))
import mwparserfromhell as parser
assert parser.__version__=='0.7.2' and parser.parser.use_c and Path(parser.__file__).resolve().is_relative_to(BASE/'tool-dependencies/mwparserfromhell-0.7.2')
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
literal=module('literal',BASE/'enwiki-generic-AST-policy-preparation-v4/policy_core.py');ref=module('reference',BASE/'enwiki-page-local-reference-preparation-v2/reference_core.py')
examples=[]
for name,source in [('explanatory_note','The total is 40.<ref>The total excludes offshore operations and is disputed.</ref>'),('citation_only','The total is 40.<ref>{{cite book|title=Annual report|author=A. Writer|year=2020|page=12}}</ref>'),('citation_with_quote','The total is 40.<ref>{{cite book|title=Annual report|quote=The total excludes offshore operations.}}</ref>'),('explicit_note_group','The total is 40.<ref group="note">The total excludes offshore operations.</ref>')]:
 r=ref.resolve_page(source,parser,None,literal)
 assert len(r['ref_occurrences'])==1 and len(r['citation_companions'])==1
 examples.append({'name':name,'source':source,'source_SHA256':ref.H(source),'existing_resolver_holds':r['source_partition'][0]['holds'],'existing_resolver_marker':r['citation_companions'][0]['marker'],'raw_entire_content_retained':r['citation_companions'][0]['all_raw_explanatory_text_and_qualifiers_retained'],'interpretation':'Existing resolver proves source-bound definition/reference linkage and retains complete raw companion, but does not classify citation-only versus explanatory content. New gate must not treat marker replacement as proof of standalone prose independence.'})
(HERE/'synthetic-diagnostics.json').write_text(json.dumps({'status':'SOURCE_FREE_SYNTHETIC_DIAGNOSTICS','fixtures':examples,'retained_source_reads':0,'new_core_implemented':False},indent=2)+'\n')
print(json.dumps({'status':'PASS','fixtures':len(examples),'retained_source_reads':0}))
