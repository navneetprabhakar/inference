"""Read exactly one existing record; compare raw-DOM structural block rendering."""
import hashlib,json,platform,sys
from pathlib import Path
from importlib.metadata import version
from bs4 import BeautifulSoup
from render import STRUCTURAL_TAGS,render_html
D=Path(__file__).resolve().parent
SOURCE=D.parent/'m2-intake/wikibooks-discovery-v2/source-records.jsonl'
def sha(b):return hashlib.sha256(b).hexdigest()
def file_sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
with SOURCE.open('rb') as f:line=f.readline(4*1024*1024+1)
if len(line)>4*1024*1024:raise ValueError('First record exceeds fixed record limit')
r=json.loads(line);html=r['article_body']['html'];new=render_html(html)
soup=BeautifulSoup(html,'lxml');content=soup.body or soup;old=[]
for n in content.find_all(list(STRUCTURAL_TAGS)):
 if any(p.name in STRUCTURAL_TAGS for p in n.parents if p is not content):continue
 text=n.get_text('\n' if n.name in ['pre','table'] else ' ',strip=True)
 if n.name not in ['pre','table']:text=' '.join(text.split())
 else:text=text.strip()
 if text:old.append({'kind':n.name,'text':text,'sha256':sha(text.encode())})
assert len(old)==len(new['blocks'])
comparison=[{'block':i,'kind':a['kind'],'baseline':a['text'],'prototype':b['text'],'changed':a['text']!=b['text']} for i,(a,b) in enumerate(zip(old,new['blocks']))]
assert any('Onl in e' in x['baseline'] and 'Online' in x['prototype'] for x in comparison)
assert any('in formation' in x['baseline'] and 'information' in x['prototype'] for x in comparison)
(D/'first-record.exact.jsonl').write_bytes(line)
(D/'first-page.original.html').write_bytes(html.encode())
(D/'first-page.rendered.json').write_text(json.dumps(new,indent=2,ensure_ascii=False)+'\n')
report={'status':'FIRST_PAGE_RENDERING_COMPARISON_ONLY','source_file':str(SOURCE),'source_file_sha256':file_sha(SOURCE),'source_exact_line_sha256':sha(line),'source_record_bytes':len(line),'page_id':r['identifier'],'revision_id':r['version']['identifier'],'title':r['name'],'original_html_sha256':sha(html.encode()),'prototype_sha256':file_sha(D/'render.py'),'baseline_method':'Same highest structural blocks on raw original DOM; BeautifulSoup get_text(space,strip=True), whitespace fold except pre/table. This comparison does not claim full extractor navigation/hold-policy equivalence.','blocks':len(old),'changed_blocks':sum(x['changed'] for x in comparison),'comparisons':comparison,'holds':new['holds'],'observations':['Inline split-word spacing errors repaired from actual DOM adjacency, without inserting guessed words or spaces.','Existing meaningful source whitespace retained/collapsed according to HTML flow; explicit structural boundaries retained.','This verifies a first-page extraction mechanism, not source readability, factual accuracy, licensing, ancestry or representative quality.'],'training_admitted':False,'dependencies':{'python':platform.python_version(),'beautifulsoup4':version('beautifulsoup4'),'lxml':version('lxml')}}
(D/'first-page-comparison.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:report[k] for k in ['status','page_id','blocks','changed_blocks','holds','source_exact_line_sha256','prototype_sha256']}))
