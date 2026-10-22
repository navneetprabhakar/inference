"""Isolated native C parser import, synthetic proof or native20 AST roundtrip."""
import argparse,collections,hashlib,json,pathlib,sys,time
sha=lambda b:hashlib.sha256(b).hexdigest()
def run(target,mode,source,output,inventory):
 target=pathlib.Path(target).resolve();expected=json.loads(pathlib.Path(inventory).read_text())
 for name,v in expected['files'].items():
  p=target/name
  if p.is_symlink() or sha(p.read_bytes())!=v['SHA256']:raise ValueError('installed_exact_file_hash')
 sys.path.insert(0,str(target));import mwparserfromhell as mw
 import mwparserfromhell.parser as parser
 import mwparserfromhell.parser._tokenizer as native
 from importlib.metadata import distribution
 if pathlib.Path(distribution('mwparserfromhell')._path).resolve()!=target/'mwparserfromhell-0.7.2.dist-info':raise ValueError('distribution_metadata_origin')
 if mw.__version__!='0.7.2' or distribution('mwparserfromhell').version!='0.7.2' or pathlib.Path(mw.__file__).resolve()!=target/'mwparserfromhell/__init__.py' or pathlib.Path(native.__file__).resolve()!=target/'mwparserfromhell/parser/_tokenizer.cpython-312-darwin.so':raise ValueError('isolated_version_module_native_origin')
 if not parser.use_c or not isinstance(parser.Parser()._tokenizer,native.CTokenizer):raise ValueError('actual_C_tokenizer_required_no_fallback')
 # Every mwparser module imported must originate in this isolated target.
 origins={name:str(pathlib.Path(module.__file__).resolve()) for name,module in sys.modules.items() if name.startswith('mwparserfromhell') and getattr(module,'__file__',None)}
 if any(not pathlib.Path(p).is_relative_to(target) for p in origins.values()):raise ValueError('module_origin_escape')
 fixtures=['[[Target|display]] {{outer|x={{inner|1=a}}}}\n<ref name="x">citation</ref>',"==Heading==\n'''bold''' ''italic'' <!-- comment --> &amp;\n{| class=\"wikitable\"\n| a || b\n|}", '{{As of|2011}} India census\r\n#REDIRECT [[Other]]', '<noinclude>{{Notice|a=b}}</noinclude> text <span data-darkreader-inline-color="">words</span>', '{{unclosed|[[literal]]']
 synthetic=[]
 for text in fixtures:
  code=mw.parse(text)
  if str(code)!=text:raise ValueError('synthetic_AST_roundtrip_identity')
  synthetic.append({'input_SHA256':sha(text.encode()),'roundtrip_exact':True,'recursive_node_types':dict(collections.Counter(type(n).__name__ for n in code.ifilter(recursive=True)))})
 result={'status':'PASS_ISOLATED_PACKAGE_AND_SYNTHETIC_C_AST_ONLY','version':mw.__version__,'native_C_parser':True,'module_origins':origins,'synthetic_fixtures':synthetic,'network_requests':0,'extraction_or_strip_code_or_template_expansion':False,'new_admitted_documents':0,'new_admitted_tokens':0}
 if mode=='native20':
  root=pathlib.Path(source);decisions=json.loads((root/'all20-native-decisions.json').read_text());rows=[]
  if len(decisions)!=20:raise ValueError('exact20_negative_cases_kept')
  for row in decisions:
   raw=(root/row['source_text_file']).read_bytes();text=raw.decode('utf8',errors='strict')
   if sha(raw)!=row['source_text']['local_SHA256'] or len(raw)!=row['source_text']['bytes']:raise ValueError('exact_native_source_text_pin')
   code=mw.parse(text);roundtrip=str(code)
   if roundtrip!=text or roundtrip.encode()!=raw:raise ValueError('native_AST_roundtrip_source_identity')
   rows.append({'index_row_ordinal':row['selected_index_row']['row_ordinal'],'page_ID':row['native_page_id'],'revision_ID':row['native_revision']['id'],'native_title':row['native_title'],'native_ns':row['native_ns'],'prior_status':row['status'],'prior_holds':row['holds'],'source_text_SHA256':sha(raw),'source_text_bytes':len(raw),'roundtrip_SHA256':sha(roundtrip.encode()),'byte_exact_AST_roundtrip':True,'recursive_node_types':dict(collections.Counter(type(n).__name__ for n in code.ifilter(recursive=True))),'top_level_node_types':dict(collections.Counter(type(n).__name__ for n in code.nodes))})
  result.update(status='COMPLETE_NATIVE20_AST_ROUNDTRIP_ONLY_NO_EXTRACTION',native20_rows=rows,all20negative_cases_preserved=True,source_decisions_SHA256=sha((root/'all20-native-decisions.json').read_bytes()))
 body=(json.dumps(result,indent=2,ensure_ascii=False)+'\n').encode()
 if len(body)>16000000:raise ValueError('16MB_AST_evidence_cap')
 with pathlib.Path(output).open('xb') as f:f.write(body)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--target',required=True);p.add_argument('--mode',choices=['synthetic','native20'],required=True);p.add_argument('--source',default='');p.add_argument('--output',required=True);p.add_argument('--inventory',required=True);a=p.parse_args();run(a.target,a.mode,a.source,a.output,a.inventory)
