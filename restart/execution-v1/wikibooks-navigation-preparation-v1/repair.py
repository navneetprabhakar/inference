"""One frozen page DEVELOPMENT repair. Complete transcluded paragraphs only."""
import hashlib,html,json,pathlib,sys,time
from html.parser import HTMLParser
from bs4 import BeautifulSoup,NavigableString
P=pathlib.Path(__file__).resolve().parent;E=P.parent;SOURCE=E/'m2-intake/wikibooks-navigation-discovery-v1';D=E/'m2-intake/wikibooks-navigation-development-v1';RECORD_SHA='66f1b4deb61273aeaf1a1416ff63b80418625b3b0902bc6b2ff146b91b94219d';HTML_SHA='894eafe92a8c28ba9efbdc26049e87f685d3359ba57d52d964f9e3710c39fdb6';sha=lambda b:hashlib.sha256(b).hexdigest();TARGETS={'mwAg':'#mwt1','mwIA':'#mwt2'};TEMPLATE='Demystifying Depression navbar'
def validate_container(p,ident,about):
 if p.name!='p' or p.get('id')!=ident:raise ValueError('Complete exact paragraph required')
 direct=[c for c in p.children if not isinstance(c,NavigableString)]
 if len(direct)!=6 or [c.name for c in direct]!=['span','a','span','small','span','link']:raise ValueError('Exact observed sibling shape required')
 if any(c.get('about')!=about for c in direct) or any(isinstance(c,NavigableString) and c.strip() for c in p.children):raise ValueError('Paragraph contains material outside transclusion')
 first=direct[0];data=json.loads(first.get('data-mw','{}'));parts=data.get('parts',[])
 if first.get('typeof')!='mw:Transclusion' or len(parts)!=1 or parts[0].get('template',{}).get('target')!={'wt':TEMPLATE,'href':'./Template:Demystifying_Depression_navbar'}:raise ValueError('Exact native template identity required')
 if direct[-1].get('rel')!=['mw:PageProp/Category']:raise ValueError('Exact observed category tail required')
 return True
class Offsets(HTMLParser):
 def __init__(self,text):
  super().__init__(convert_charrefs=False);self.text=text;self.lines=[0];self.stack=[];self.rows={}
  for i,c in enumerate(text):
   if c=='\n':self.lines.append(i+1)
 def char_offset(self):l,c=self.getpos();return self.lines[l-1]+c
 def handle_starttag(self,tag,attrs):
  if tag=='p':self.stack.append((dict(attrs).get('id'),self.char_offset()))
 def handle_endtag(self,tag):
  if tag=='p':
   ident,start=self.stack.pop();end=self.text.index('>',self.char_offset())+1
   if ident in TARGETS:
    if ident in self.rows:raise ValueError('Duplicate target paragraph ID')
    self.rows[ident]=(start,end)
 def handle_startendtag(self,tag,attrs):pass

def selected(text):
 soup=BeautifulSoup(text,'html.parser')
 for ident,about in TARGETS.items():
  matches=soup.find_all(id=ident)
  if len(matches)!=1:raise ValueError('Unique exact paragraph ID required')
  validate_container(matches[0],ident,about)
 offsets=Offsets(text);offsets.feed(text);offsets.close();assert set(offsets.rows)==set(TARGETS)
 return soup,offsets.rows

def main():
 started=time.monotonic();raw=(SOURCE/'original-record.json').read_bytes();assert sha(raw)==RECORD_SHA;record=json.loads(raw);original=record['article_body']['html'];b=original.encode();assert sha(b)==HTML_SHA and record['identifier']==29818 and record['version']['identifier']==3080083
 soup,offsets=selected(original);tests=[]
 # Refuse broader or partial deletion, mixed prose, and ambiguous about-group.
 p=soup.find(id='mwAg');validate_container(p,'mwAg','#mwt1');tests.append('actual_exact_six_sibling_transclusion_group_accepted')
 altered=BeautifulSoup(str(p),'html.parser').p;altered.append(' Narrative must remain.')
 try:validate_container(altered,'mwAg','#mwt1')
 except ValueError:pass
 else:raise AssertionError('mixed prose accepted')
 tests.append('mixed_paragraph_prose_refused')
 altered=BeautifulSoup(str(p),'html.parser').p;altered.find('small')['about']='#unrelated'
 try:validate_container(altered,'mwAg','#mwt1')
 except ValueError:pass
 else:raise AssertionError('partial transclusion accepted')
 tests.append('mismatched_sibling_group_refused')
 try:validate_container(p.find('span'),'mwAw','#mwt1')
 except ValueError:pass
 else:raise AssertionError('partial node accepted')
 tests.append('partial_template_span_refused')
 nodes=[];segments=[];cursor=0
 for ident,(a,z) in sorted(offsets.items(),key=lambda x:x[1][0]):
  assert original[a:z].startswith('<p id="'+ident+'">') and original[a:z].endswith('</p>');bs=len(original[:a].encode());be=len(original[:z].encode());chunk=b[bs:be];assert chunk.decode()==original[a:z]
  if cursor<bs:segments.append({'action':'keep','source_start_byte':cursor,'source_end_byte':bs,'sha256':sha(b[cursor:bs])})
  segments.append({'action':'remove','node_id':ident,'source_start_byte':bs,'source_end_byte':be,'sha256':sha(chunk)});cursor=be;nodes.append({'node_id':ident,'about':TARGETS[ident],'DOM_path':'p#'+ident,'source_start_codepoint':a,'source_end_codepoint':z,'source_start_byte':bs,'source_end_byte':be,'exact_source_HTML':chunk.decode(),'sha256':sha(chunk),'reason':'Complete paragraph contains only exact observed native navbar transclusion siblings and category tail.'})
 if cursor<len(b):segments.append({'action':'keep','source_start_byte':cursor,'source_end_byte':len(b),'sha256':sha(b[cursor:])})
 derivative=b''.join(b[x['source_start_byte']:x['source_end_byte']] for x in segments if x['action']=='keep');assert b''.join(b[x['source_start_byte']:x['source_end_byte']] for x in segments)==b
 for ident in TARGETS:soup.find(id=ident).decompose()
 derived_soup=BeautifulSoup(derivative.decode(),'html.parser')
 def signature(tree):
  return [('text',str(n)) if isinstance(n,NavigableString) else ('element',n.name,json.dumps(n.attrs,sort_keys=True)) for n in tree.descendants if not isinstance(n,NavigableString) or n.strip()]
 assert signature(soup)==signature(derived_soup);assert all(derived_soup.find(id=i) is None for i in TARGETS);assert len(derived_soup.find_all('section'))==2
 # Exact retained prose nodes and punctuation, including current held health claims.
 original_soup=BeautifulSoup(original,'html.parser');proseids=['mwBg','mwCg','mwDg','mwEg','mwEw','mwFw','mwGw','mwHw']
 for ident in proseids:assert str(original_soup.find(id=ident))==str(derived_soup.find(id=ident))
 tests+=['all_other_DOM_elements_attributes_and_nonblank_text_identical','all_eight_main_prose_paragraphs_exact_including_punctuation','both_original_sections_retained','source_keep_remove_byte_reconstruction_exact']
 sys.path.insert(0,str(E/'wikibooks-residual-render-preparation-v2'));import extraction_core as core
 parent=core.extract_record(record);new=json.loads(raw);new['article_body']['html']=derivative.decode();rendered=core.extract_record(new);text=rendered['text'];assert 'Next page:' not in text and 'Previous page:' not in text;assert 'Sleeping Medication' in text
 D.mkdir(exist_ok=False)
 def write(name,data):
  value=data if isinstance(data,bytes) else (json.dumps(data,indent=2,ensure_ascii=False)+'\n').encode()
  if time.monotonic()-started>=55 or sum(p.stat().st_size for p in D.iterdir() if p.is_file())+len(value)>4900000:raise ValueError('55second/5MB output bound')
  with (D/name).open('xb') as f:f.write(value)
 write('original-record.json',raw);write('original-html.bin',b);write('derived-html.txt',derivative);write('removed-nodes.json',nodes);write('derived-preview.txt',text.encode())
 view='<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><style>body{font:16px system-ui;max-width:900px;margin:25px auto}pre{white-space:pre-wrap}</style><h1>Development navigation removal — factual hold retained</h1><p>Only two complete frozen navigation paragraphs removed. The health claims below remain unverified and held.</p><pre>'+html.escape(text)+'</pre>';write('review.html',view.encode())
 receipt={'status':'ONE_FROZEN_RECORD_DEVELOPMENT_FILTER_REPAIR_NOT_ADMITTED','source_ordinal':2374,'page_id':29818,'revision_id':3080083,'source_record_sha256':RECORD_SHA,'source_HTML_sha256':HTML_SHA,'derived_HTML_sha256':sha(derivative),'derived_text_sha256':sha(text.encode()),'source_title':record['name'],'same_work_family':'Demystifying Depression','removed_complete_paragraphs':2,'removed_node_ids':list(TARGETS),'all_other_source_HTML_bytes_unchanged':True,'all_other_nonblank_DOM_text_and_nodes_unchanged':True,'whitespace_scope':'Every retained source HTML byte, including whitespace, remains exact. Reparsing may coalesce adjacent whitespace-only DOM strings around a removed node.','holds':sorted(set(rendered.get('structural_holds',[])+['DEVELOPMENT_ONLY_NO_ACCEPTANCE','PRIOR_PARENT_FACTUAL_HOLD_RETAINED_HEALTH_CLAIMS_UNVERIFIED','RIGHTS_AND_CROSS_SOURCE_LEAKAGE_PENDING'])),'original_extractor_holds':parent.get('structural_holds',[]),'development_extractor_holds':rendered.get('structural_holds',[]),'generalization':'No rule generalized beyond this exact record/revision/HTML hash and exact two transclusion groups.','new_admitted_documents':0,'new_admitted_tokens':0,'network_requests':0,'model_operations':0,'tests':tests,'elapsed_seconds':time.monotonic()-started};write('receipt.json',receipt);write('recipe.json',{'profile':'only_exact_frozen_2374_two_complete_navbar_paragraphs_v1','source_record_sha256':RECORD_SHA,'source_HTML_sha256':HTML_SHA,'derived_HTML_sha256':sha(derivative),'ordered_source_segments':segments,'original_captured_licenses':record['license'],'source_preserved':True,'admission':False});assert sha((SOURCE/'original-record.json').read_bytes())==RECORD_SHA;manifest={p.name:sha(p.read_bytes()) for p in D.iterdir() if p.is_file()};write('manifest.json',manifest);print(json.dumps({'status':receipt['status'],'tests':len(tests),'manifest_SHA256':sha((D/'manifest.json').read_bytes()),'output_bytes':sum(p.stat().st_size for p in D.iterdir() if p.is_file())}))
if __name__=='__main__':main()
