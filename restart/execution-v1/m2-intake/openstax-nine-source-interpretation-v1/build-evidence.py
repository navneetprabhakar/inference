from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
base=Path('/Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1'); src=base/'m2-intake/openstax-breadth-nine-metadata-v1'; out=base/'m2-intake/openstax-nine-source-interpretation-v1';out.mkdir(exist_ok=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,obj): (out/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
inputs=[]; responses=[]
for f in sorted(src.glob('*.metadata')):
 key=f.stem;rec=json.loads((src/(key+'.receipt.json')).read_text());head=json.loads((src/(key+'.headers.json')).read_text()); raw=f.read_bytes();assert rec['SHA256']==sha(f);assert rec['received_body_bytes']==len(raw)
 hb=bytes.fromhex(head['prefix_hex']); assert len(hb)==head['header_bytes'];assert hashlib.sha256(hb).hexdigest()==head['header_SHA256']
 responses.append(dict(key=key,bytes=len(raw),SHA256=sha(f),status=head['status'],URL=head['effective_URL'],header_SHA256=head['header_SHA256'],full_headers_retained=True,Link_headers=[x for x in hb.decode().splitlines() if x.lower().startswith('link:')]))
 for p in [f,src/(key+'.receipt.json'),src/(key+'.headers.json')]: inputs.append(dict(path=str(p),bytes=p.stat().st_size,SHA256=sha(p)))
for name in ['worker-result.json','supervisor-result.json','ownership.json']:
 p=src/name
 if p.exists():inputs.append(dict(path=str(p),bytes=p.stat().st_size,SHA256=sha(p)))
assert sha(src/'worker-result.json')=='1f64a70ad286d97cb6ecbc602f32514ccd5fe8c9891f74374aae77eb0899ac61'
ns={'c':'http://cnx.rice.edu/collxml','m':'http://cnx.rice.edu/mdml'}
raw=(src/'us-history-exact-collection.metadata').read_bytes();assert b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper();root=ET.fromstring(raw)
modules=[];chapters=[]
def walk(e,anc):
 if e.tag=='{http://cnx.rice.edu/collxml}subcollection':
  t=e.find('m:title',ns);title=''.join(t.itertext()) if t is not None else None;anc=anc+[title];chapters.append(dict(ordinal=len(chapters)+1,title=title))
 if e.tag=='{http://cnx.rice.edu/collxml}module':modules.append(dict(ordinal=len(modules)+1,document=e.get('document'),chapter_path=anc,attributes=e.attrib))
 for c in e:walk(c,anc)
walk(root,[])
commit=json.loads((src/'us-history-exact-commit.metadata').read_text());meta=root.find('c:metadata',ns)
metadata=[]
for e in meta:metadata.append(dict(expanded_name=e.tag,attributes=e.attrib,text=''.join(e.itertext())))
write('us-history-module-references.json',dict(source_SHA256=sha(src/'us-history-exact-collection.metadata'),module_reference_count=len(modules),unique_module_IDs=len({r['document'] for r in modules}),chapter_count=len(chapters),chapters=chapters,ordered_module_references=modules,warning='References are not proof of existing module files, bytes, prose quality or usable counts. m00001 requires exact tree lookup; no corruption inference.'))
hist=[];future=[]
future.append(dict(key='us-history-exact-recursive-tree',URL=commit['commit']['tree']['url']+'?recursive=1',response_cap=2097152,reason='Reconcile all 177 module references with exact tree paths/blob IDs/sizes; require matching tree SHA and truncated=false.'))
for f in sorted(src.glob('*license-history-first5.metadata')):
 records=json.loads(f.read_text());assert len(records)==3
 repo=f.stem.removesuffix('-license-history-first5');new=records[0];assert len(new['parents'])==1;parent=new['parents'][0]['sha']
 hist.append(dict(repository=repo,source_SHA256=sha(f),returned_commits=len(records),history_complete_claim=False,pagination_evidence='All retained complete response headers contain no Link header; this remains a captured path-history response, not proof of all license/component history.',change_commit=new['sha'],change_date=new['commit']['committer']['date'],change_message=new['commit']['message'],pre_change_parent=parent,disposition='HISTORICAL_LICENSE_AND_CONTAINER_CAPTURE_PENDING',limits='History message identifies NC-SA transition but does not establish exact prior license text or component coverage.',observed_history=[dict(commit=r['sha'],date=r['commit']['committer']['date'],message=r['commit']['message'],parents=[p['sha'] for p in r['parents']]) for r in records]))
 for suffix,cap,url in [('commit',65536,f'https://api.github.com/repos/openstax/{repo}/commits/{parent}'),('license',32768,f'https://raw.githubusercontent.com/openstax/{repo}/{parent}/LICENSE'),('container',16384,f'https://raw.githubusercontent.com/openstax/{repo}/{parent}/META-INF/books.xml')]:future.append(dict(key=repo+'-historical-'+suffix,URL=url,response_cap=cap,reason='Exact observed pre-change parent; metadata only. No guessed collection path, tree SHA or module URL.'))
write('five-license-history-dispositions.json',hist)
review=dict(status='SOURCE_METADATA_INTERPRETATION_NO_ADMISSION',scope='Complete nine retained metadata bodies, exact receipts and full headers; no module bodies, extra GETs, clone or pagination.',responses=responses,us_history=dict(commit=commit['sha'],commit_date=commit['commit']['committer']['date'],tree_SHA=commit['commit']['tree']['sha'],tree_URL=commit['commit']['tree']['url'],snapshot='2025-12-04 exact commit; not current 2026 book',commit_file_list_limit='Only README.md changed; files[] is not a repository module inventory.',license=dict(disposition='EXACT_HISTORICAL_CC_BY_4_0_SOURCE_CANDIDATE',LICENSE_SHA256=sha(src/'us-history-exact-license.metadata'),collection_license_URL='http://creativecommons.org/licenses/by/4.0/',scope='Complete captured repository LICENSE and same-commit collection license declaration agree. No NC/SA/LLM restriction appears in this captured LICENSE.',limits=['Licensor grants only rights it controls; embedded third-party quotations, figures and credited components require source-specific treatment.','Preserve attribution, source URLs, license notice, disclaimer and modification notices.','A later licensing change does not itself terminate the already offered license, subject to its conditions; this does not bind newer snapshots or establish a model-weights license.','No module content has been fetched or quality reviewed in this task.']),collection_metadata=metadata,collection_attributes=root.attrib,container_book_slug='us-history',container_collection_ID='col11740',container_resolved_collection_path='collections/us-history.collection.xml',modules=177,chapters=32,unusual_reference='m00001 is present; verify against exact tree, do not infer missing/corrupt from its spelling.'),five_other_sources='Exact pre-NC-SA parent candidates identified; no historical-license clearance until actual parent LICENSE/container/commit evidence is captured.',family_and_quality_plan=['Use whole-book UUID/slug/edition/module ancestry as a family; reconcile reuses/adaptations across sources, not repository name alone.','Exact tree metadata should establish module paths/blob IDs and sizes; preserve chapter order and note/image/quotation dependencies before finite whole-unit discovery.','Do not treat xml:lang=en as semantic quality, author-original-English proof or usable-token count.','Preserve historical subject framing and factual-risk review separately from readable/coherent prose assessment.'],new_admitted_documents=0,new_admitted_tokens=0,network_requests_by_this_review=0)
write('review.json',review)
write('finite-followup-metadata-proposal.json',dict(status='PROPOSAL_ONLY_NO_REQUESTS',requests=future,maximum_requests=len(future),sum_response_caps=sum(x['response_cap'] for x in future),recommended_output_reservation=4_000_000,serial_minimum_start_interval_seconds=1,no_redirects=True,no_retries=True,ledger_precharge_required=True,scope='Repository metadata/LICENSE/container only; no module/media/PDF bodies, clone, pagination or source admission. Parent must review a separately pinned executor before dispatch.',next_stage='Only after actual historical LICENSE/container/commit evidence: resolve each exact returned collection path/tree SHA; do not guess or automatically follow.'))
write('inputs.json',inputs)
manifest={'status':'COMPLETE_METADATA_REVIEW_NO_ADMISSION','outputs':[dict(path=str(p),bytes=p.stat().st_size,SHA256=sha(p)) for p in sorted(out.iterdir())]};write('manifest.json',manifest)
for f in ['review.json','finite-followup-metadata-proposal.json','manifest.json']:print(f,sha(out/f))
print('modules',len(modules),'chapters',len(chapters),'followup_requests',len(future),'caps',sum(x['response_cap'] for x in future))
