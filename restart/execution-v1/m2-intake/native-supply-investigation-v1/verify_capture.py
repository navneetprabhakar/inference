"""Read-only source/tree/ledger verification after terminal capture."""
import fcntl,hashlib,json,os,sqlite3
from pathlib import Path
from lxml import etree
import capture_metadata as c
checks={};proposal,pins=c.pins();out=c.DEST;w=json.loads((out/'worker-result.json').read_text());s=json.loads((out/'supervisor-result.json').read_text())
checks['terminal_worker_and_supervisor_complete']=w['status']=='COMPLETE_FIVE_METADATA_LICENSE_CAPTURES_NO_ADMISSION' and s['status']=='COMPLETE' and s['worker_exit_code']==0 and not s['external_timeout'] and s['elapsed_seconds']<120
checks['supervisor_binds_worker_receipt']=s['worker_result_sha256']==c.sha((out/'worker-result.json').read_bytes())
d=sqlite3.connect('file:'+str((c.ROOT/'charges/ledger.sqlite').resolve())+'?mode=ro',uri=True);attempts=[]
try:
 for i,item in enumerate(proposal['items']):
  raw=(out/item['file']).read_bytes();r=json.loads((out/f'response-{i:03d}.receipt.json').read_text());q=json.loads((out/f'request-{i:03d}.json').read_text())
  checks[f'response{i}_raw_URL_hash_size_TLS_precharge']=r['body_sha256']==c.sha(raw) and r['body_bytes']==len(raw)<item['body_cap'] and r['url']==r['effective_URL']==q['url']==item['url'] and r['TLS_certificate_and_hostname_verified'] and q['charged_before_IO'] and not r['redirect']
  row=d.execute('select key,charge,state,actual_bytes,body_sha256 from attempts where key=?',(r['key'],)).fetchone();charge=json.loads(row[1])
  checks[f'response{i}_exact_complete_global_ledger']=row[2]=='complete' and row[3]==len(raw) and row[4]==c.sha(raw) and charge['requests']==1 and charge['body_bytes']==item['body_cap']
  attempts.append({'key':row[0],'charge':charge,'state':row[2],'actual_bytes':row[3],'body_sha256':row[4]})
 checks['exact_five_no_additional_attempts']=d.execute("select count(*) from attempts where key like 'openstax-historical-metadata-license-v1-%'").fetchone()[0]==5
finally:d.close()
with (c.ROOT/'charges/job.lock').open('r+') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:checks['global_ledger_lock_released']=False
 else:checks['global_ledger_lock_released']=True;fcntl.flock(lock,fcntl.LOCK_UN)
try:os.kill(s['worker_pid'],0)
except ProcessLookupError:checks['worker_gone']=True
else:checks['worker_gone']=False
checks['actual_and_reserved_byte_totals']=sum(r['actual_bytes'] for r in attempts)==w['actual_response_bytes']==354716 and sum(r['charge']['body_bytes'] for r in attempts)==c.BODY_CAP and sum(r['charge']['output_bytes'] for r in attempts)==c.CAP
checks['all_files_output_bound']=c.size()<c.CAP
pre=json.loads((out/'preflight.json').read_text());checks['strict_TLS_preflight']=pre['strict_TLS']['check_hostname'] and pre['strict_TLS']['verify_mode_CERT_REQUIRED'] and pre['strict_TLS']['minimum_TLS']=='TLSv1.2'
tree=json.loads((out/'world-history-2024-tree.json').read_text());entries=tree['tree'];mapping={e['path']:e for e in entries}
checks['complete_pinned_commit_tree']=not tree['truncated'] and tree['sha']=='8a4dd8ae49f82bc734713e30586a6e017ba51915'==json.loads((c.HERE/'world-history-2024-commit.json').read_text())[0]['commit']['tree']['sha']
def git_hash(kind,b):return hashlib.sha1((kind+' '+str(len(b))).encode()+b'\0'+b).hexdigest()
def verify_tree(prefix,expected):
 children=[e for e in entries if '/' in e['path'] and e['path'].rsplit('/',1)[0] == prefix] if prefix else [e for e in entries if '/' not in e['path']]
 def key(e):return e['path'].rsplit('/',1)[-1].encode()+ (b'/' if e['type']=='tree' else b'')
 b=b''
 for e in sorted(children,key=key):
  name=e['path'].rsplit('/',1)[-1]
  mode=e['mode'].lstrip('0');b+=mode.encode()+b' '+name.encode()+b'\0'+bytes.fromhex(e['sha'])
  if e['type']=='tree':verify_tree(e['path'],e['sha'])
 assert git_hash('tree',b)==expected,(prefix,'Git tree hash mismatch')
verify_tree('',tree['sha']);checks['all_recursive_Git_tree_object_hashes_recomputed']=True
bindings={'world-history-2024-LICENSE.txt':'LICENSE','world-history-2024-books.xml':'META-INF/books.xml','world-history-2024-volume1.collection.xml':'collections/world-history-volume-1.collection.xml','world-history-2024-volume2.collection.xml':'collections/world-history-volume-2.collection.xml'}
for local,native in bindings.items():
 b=(out/local).read_bytes();checks['Git_blob_'+local]=git_hash('blob',b)==mapping[native]['sha'] and len(b)==mapping[native]['size'] and mapping[native]['mode']=='100644'
license=(out/'world-history-2024-LICENSE.txt').read_text();checks['historical_LICENSE_is_CC_BY4']=license.startswith('Attribution 4.0 International') and 'Creative Commons Attribution 4.0 International Public License' in license
parser=etree.XMLParser(resolve_entities=False,no_network=True,load_dtd=False)
books=etree.fromstring((out/'world-history-2024-books.xml').read_bytes(),parser);refs=books.findall('{https://openstax.org/namespaces/book-container}book');checks['two_pinned_book_container_entries']=len(refs)==2
collections=[];unique={}
for n in [1,2]:
 root=etree.fromstring((out/f'world-history-2024-volume{n}.collection.xml').read_bytes(),parser);ns={'md':'http://cnx.rice.edu/mdml','col':'http://cnx.rice.edu/collxml'};md=root.find('col:metadata',ns)
 assert md.find('md:license',ns).get('url')=='http://creativecommons.org/licenses/by/4.0/' and md.findtext('md:language',namespaces=ns)=='en'
 mods=[e.get('document') for e in root.findall('.//col:module',ns)]
 for mid in mods:
  path='modules/'+mid+'/index.cnxml';e=mapping[path];assert e['type']=='blob' and e['mode']=='100644';unique[path]=e
 collections.append({'title':md.findtext('md:title',namespaces=ns),'uuid':md.findtext('md:uuid',namespaces=ns),'license':md.find('md:license',ns).get('url'),'referenced_modules':len(mods),'ordered_module_IDs':mods})
checks['both_collection_licenses_and_all_native_module_tree_references']=True
checks['zero_corpus_or_admission']=w['corpus_modules_or_media_downloaded']==w['new_admitted_documents']==w['new_admitted_tokens']==0
assert all(checks.values()),checks
report={'status':'PASS_TERMINAL_METADATA_AND_HISTORICAL_GIT_BINDINGS','checks':checks,'check_count':len(checks),'actual_response_bytes':354716,'conservative_reserved_response_bytes':c.BODY_CAP,'ledger_attempts':attempts,'collections':collections,'unique_referenced_native_module_count':len(unique),'unique_referenced_native_module_listed_bytes':sum(e['size'] for e in unique.values()),'all_repository_native_module_count':sum(e['path'].startswith('modules/') and e['path'].endswith('/index.cnxml') for e in entries),'pilot_modules':[mapping['modules/'+m+'/index.cnxml'] for m in ['m00053','m00054','m00055','m00056']],'source_receipts_sha256':{f.name:c.sha(f.read_bytes()) for f in out.glob('*.receipt.json')},'source_license_clearance':'CC-BY4 grant captured at exact historical tree; per-module licenses and third-party objects/quotations still unreviewed. Not admission.','new_admitted_documents':0,'new_admitted_tokens':0}
with (out/'independent-terminal-source-verification.json').open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'checks':len(checks),'unique_modules':len(unique),'listed_native_XML_bytes':report['unique_referenced_native_module_listed_bytes'],'collections':[(x['title'],x['referenced_modules']) for x in collections],'report_sha256':c.sha((out/'independent-terminal-source-verification.json').read_bytes())}))
