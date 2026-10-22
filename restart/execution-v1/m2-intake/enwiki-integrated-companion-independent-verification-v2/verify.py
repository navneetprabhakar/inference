from pathlib import Path
import sys,json,hashlib,collections,time,signal
HERE=Path(__file__).resolve().parent;BASE=HERE.parents[1];ROOT=BASE/'m2-intake';OUT=ROOT/'enwiki-native20-integrated-companions-development-v2';SRC=ROOT/'enwiki-native-20row-capture-v1';PREP=BASE/'enwiki-integrated-companion-preparation-v2'
H=lambda raw:hashlib.sha256(raw).hexdigest()
def sha(p):return H(p.read_bytes())
def verify_bound(source,item):
 a,b=item['source_char_span'];ba,bb=item['source_byte_span'];assert source[a:b]==item['raw'] and source.encode()[ba:bb]==item['raw'].encode() and H(item['raw'].encode())==item['raw_SHA256']
def main():
 started=time.monotonic();signal.signal(signal.SIGALRM,lambda s,f:(_ for _ in ()).throw(TimeoutError('verification30s')));signal.alarm(30)
 try:
  assert sha(PREP/'code-pins.json')=='27f9bee4ce57ea7ee4bfc981f549abe6c7545e60da7679a87922d6ba6eb1b4b0';pins=json.loads((PREP/'code-pins.json').read_text())['files']
  for p,h in pins.items():assert sha(Path(p))==h
  sys.path.insert(0,str(BASE/'tool-dependencies/mwparserfromhell-0.7.2'));import mwparserfromhell as m
  assert m.__version__=='0.7.2' and m.parser.use_c
  w=json.loads((OUT/'result.json').read_text());s=json.loads((OUT/'supervisor.json').read_text());assert w['status']=='COMPLETE_NATIVE20_INTEGRATED_COMPANIONS_DEVELOPMENT_ONLY' and s['status']=='COMPLETE_DEVELOPMENT_ONLY' and s['worker_exit_code']==0 and s['worker_receipt_SHA256']==sha(OUT/'result.json');assert s['elapsed_seconds']<60 and s['peak_observed_tree_RSS_bytes']<=1000000000 and sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())<=5000000
  prior=json.loads((SRC/'all20-native-decisions.json').read_text());stats=collections.Counter();pages=[];roles=collections.Counter()
  for p in prior:
   row=p['selected_index_row']['row_ordinal'];q=OUT/f'row-{row}.json';r=json.loads(q.read_text());entry=next(x for x in w['records'] if x['row']==row);assert entry['SHA256']==sha(q)
   assert (r['native_page_ID'],r['native_revision_ID'],r['native_title'],r['prior_holds'],r['prior_status'],r['source_text_SHA256'])==(p['native_page_id'],p['native_revision']['id'],p['native_title'],p['holds'],p['status'],p['source_text']['local_SHA256'])
   role='redirect' if p['native_redirect_attributes'] is not None else 'nonarticle' if p['native_ns']!='0' else 'pending';assert r['preserved_role']==role;roles[role]+=1
   if role!='pending':assert 'frame' not in r;continue
   raw=(SRC/p['source_text_file']).read_bytes();source=raw.decode();f=r['frame'];assert H(raw)==f['source_SHA256']==p['source_text']['local_SHA256'];assert ''.join(x['raw'] for x in f['all_original_top_nodes'])==source==''.join(x['raw'] for x in f['sections']);a=ba=0
   for i,n in enumerate(f['all_original_top_nodes']):verify_bound(source,n);assert n['top_node_path']==[i] and n['source_char_span'][0]==a and n['source_byte_span'][0]==ba;a=n['source_char_span'][1];ba=n['source_byte_span'][1]
   assert (a,ba)==(len(source),len(raw));companions={x['companion_ID']:x for x in f['exact_raw_metadata_companions']}
   for c in companions.values():
    verify_bound(source,c);nodes=m.parse(c['raw']).nodes;assert len(nodes)==1;n=nodes[0]
    if type(n).__name__=='Template':assert c['raw_parameters']==[{'raw':str(x),'name_raw':str(x.name),'value_raw':str(x.value),'showkey':bool(x.showkey)} for x in n.params]
    else:assert type(n).__name__=='Wikilink' and c['raw_link_target']==str(n.title) and c['raw_link_display_or_options']==(str(n.text) if n.text is not None else None)
    if c['class'] not in ['maintenance_metadata','sort_metadata']:assert c['component_holds']
   rr=f['reference_resolution'];observed=collections.Counter(str(t) for t in m.parse(source).filter_tags(recursive=True) if str(t.tag).lower()=='ref');accounted=collections.Counter()
   for o in rr['ref_occurrences']:
    verify_bound(source,o);accounted[o['raw']]+=1
    if 'content' in o:verify_bound(source,o['content'])
   for o in rr['opaque_reference_contexts']:
    verify_bound(source,o)
    for t in o['ref_raws_and_hashes']:
     assert t['raw'] in o['raw'] and H(t['raw'].encode())==t['SHA256']
     if o['unknown_parent_type']!='unbound_or_invalid_ref_occurrence':accounted[t['raw']]+=1
   assert accounted==observed,(row,len(list(observed.elements())),len(list(accounted.elements())))
   assert rr['citation_companions']==[] # actual observed outcome, not a policy claim
   sections=[];pos=bp=0
   for u in f['sections']:
    verify_bound(source,u);assert u['source_char_span'][0]==pos and u['source_byte_span'][0]==bp;pos=u['source_char_span'][1];bp=u['source_byte_span'][1];stats['regions']+=1
    assert u['provisional_prose_preview'] is None and u['preview_SHA256'] is None and u['prose_structural_holds'];assert u['prior_source_rights_quality_language_leakage_gates_unchanged'] and u['no_admission']
    ops=sorted(u['source_operations'],key=lambda x:x['source_char_span']);last=u['source_char_span'][0];forward=[];source_operations=[]
    for op in ops:
     verify_bound(source,op);a,b=op['source_char_span'];assert a>=last and b<=u['source_char_span'][1];forward.extend([source[last:a],op['replacement']]);last=b
     if 'companion_ID' in op:assert op['raw']==companions[op['companion_ID']]['raw'] and op['replacement']==''
     source_operations.append(op)
    forward.append(source[last:u['source_char_span'][1]]);changed=''.join(forward)
    if u['operations_applied_to_provisional_markup']:
     assert not u['reference_holds'] and H(changed.encode())==u['transformed_markup_SHA256'];old=[];cursor=0;delta=0
     for op in ops:
      a,b=op['source_char_span'];at=a-u['source_char_span'][0]+delta;assert changed[at:at+len(op['replacement'])]==op['replacement'];old.extend([changed[cursor:at],op['raw']]);cursor=at+len(op['replacement']);delta+=len(op['replacement'])-(b-a)
     old.append(changed[cursor:]);assert ''.join(old)==u['raw'];stats['applied_markup_ops']+=len(ops)
    else:assert u['reference_holds'] and u['transformed_markup_SHA256'] is None
    stats['source_ops']+=len(ops);sections.append({'region':u['section_ordinal'],'prose_structural_holds':u['prose_structural_holds'],'semantic_companion_holds':u['semantic_companion_holds'],'operations_applied_to_markup':u['operations_applied_to_provisional_markup']})
   assert (pos,bp)==(len(source),len(raw));stats['metadata_companions']+=len(companions);stats['ref_tags_accounted_once']+=sum(observed.values());stats['direct_ref_occurrences']+=len(rr['ref_occurrences']);stats['opaque_reference_contexts']+=len(rr['opaque_reference_contexts']);pages.append({'row':row,'title':p['native_title'],'sections':sections,'opaque_contexts':len(rr['opaque_reference_contexts']),'source_UTF8_bytes':len(raw)})
  assert roles=={'redirect':9,'nonarticle':6,'pending':5} and stats['regions']==27 and stats['metadata_companions']==56 and stats['ref_tags_accounted_once']==192
  for p,h in pins.items():assert sha(Path(p))==h
  report={'status':'PASS_INDEPENDENT_ACTUAL_STORED_INTEGRATED_OUTPUT_VERIFICATION_NO_RERUN','roles':dict(roles),'stats':dict(stats),'pages':pages,'provisional_prose_previews':0,'preview_UTF8_bytes':0,'ref_citation_companions_resolved':0,'all27_structural_holds_retained':True,'explanation':'Zero previews reflects unresolvedstructuraldependencies and conservativeopaque-referencepageguard, NOT Englishqualityfailure. 56complete metadata/semantic/media/taxonomy companions retainallrawvalues;36operations appliedonlytoprovisionalmarkupinref-cleansections beforeotherholds;20plannedopsnotappliedduetorefholds. All192refTagrawoccurrencesaccountedonce acrossdirect/opaquecontexts.','all172_pins_unchanged':True,'worker_receipt_SHA256':sha(OUT/'result.json'),'supervisor_receipt_SHA256':sha(OUT/'supervisor.json'),'elapsed_seconds':time.monotonic()-started,'no_extractor_or_profile_rerun':True,'new_admitted_documents':0,'new_admitted_tokens':0};(HERE/'verification.json').write_text(json.dumps(report,indent=2)+'\n');(HERE/'manifest.json').write_text(json.dumps({'files':{q.name:sha(q) for q in sorted(HERE.iterdir()) if q.is_file() and q.name!='manifest.json'}},indent=2)+'\n');print('verify',sha(HERE/'verification.json'));print('manifest',sha(HERE/'manifest.json'))
 finally:signal.alarm(0)
if __name__=='__main__':main()
