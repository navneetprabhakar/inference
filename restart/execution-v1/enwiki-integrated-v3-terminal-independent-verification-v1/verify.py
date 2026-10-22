from pathlib import Path
from collections import Counter
import json,hashlib
O=Path(__file__).resolve().parent;B=O.parent;P=B/'enwiki-integrated-companion-preparation-v3';D=B/'m2-intake/enwiki-native20-integrated-companions-development-v3';S=B/'m2-intake/enwiki-native-20row-capture-v1';H=lambda b:hashlib.sha256(b).hexdigest();HP=lambda p:H(p.read_bytes())
ready=json.loads((P/'readiness.json').read_text());assert HP(P/'code-pins.json')==ready['code_pins_SHA256'] and HP(P/'profile.json')==ready['profile_SHA256']
pins=json.loads((P/'code-pins.json').read_text())['files']
for p,h in pins.items():assert HP(Path(p))==h,p
result=json.loads((D/'result.json').read_text());supervisor=json.loads((D/'supervisor.json').read_text());assert result['status']=='COMPLETE_NATIVE20_INTEGRATED_COMPANIONS_DEVELOPMENT_ONLY' and supervisor['status']=='COMPLETE_DEVELOPMENT_ONLY' and supervisor['worker_exit_code']==0 and supervisor['worker_receipt_SHA256']==HP(D/'result.json')
assert result['records_count']==20 and len(result['records'])==20
native=json.loads((S/'all20-native-decisions.json').read_text());source={x['selected_index_row']['row_ordinal']:x for x in native};roles=Counter();count=Counter();observed=Counter();per=[];preview_records=[]
def binding(x,raw):
 a,b=x['source_char_span'];ba,bb=x['source_byte_span'];assert raw[a:b]==x['raw'] and raw.encode()[ba:bb]==x['raw'].encode() and H(x['raw'].encode())==x.get('raw_SHA256',x.get('SHA256'))
for entry in result['records']:
 p=D/entry['file'];assert HP(p)==entry['SHA256'];x=json.loads(p.read_text());row=x['row_ordinal'];n=source[row];roles[x['preserved_role']]+=1
 assert x['native_page_ID']==n['native_page_id'] and x['native_revision_ID']==n['native_revision']['id'] and x['prior_holds']==n['holds'] and x['no_admission']
 raw=(S/n['source_text_file']).read_bytes();assert H(raw)==x['source_text_SHA256']==n['source_text']['local_SHA256'];raw=raw.decode()
 if x['preserved_role']!='pending':assert 'frame' not in x;continue
 f=x['frame'];r=f['reference_resolution'];assert ''.join(s['raw'] for s in f['sections'])==raw and ''.join(s['raw'] for s in f['all_original_top_nodes'])==raw and r['source_SHA256']==H(raw.encode());assert r['complete_section_partition']==f['complete_section_partition']
 saved=json.loads((B/f'm2-intake/enwiki-native20-generic-AST-development-v4/row-{row}.json').read_text());assert [s['source_char_span'] for s in saved['frame']['sections']]==f['complete_section_partition']
 for s in f['sections']+f['all_original_top_nodes']+r['ref_occurrences']+r['opaque_reference_contexts']:binding(s,raw)
 count['ordinary_ref_occurrences']+=len(r['ref_occurrences']);count['sections']+=len(f['sections']);count['citation_companions']+=len(r['citation_companions']);count['metadata_companions']+=len(f['exact_raw_metadata_companions'])
 for q in r['ref_occurrences']:observed[(row,q['section_ordinal'],q['raw_SHA256'])]+=1
 for q in r['opaque_reference_contexts']:
  vals=list(q['ref_raws_and_hashes']);count['opaque_ref_entries']+=len(vals)
  # Invalid top-level ref is both an ordinary occurrence and an opaque shadow
  # context. Remove only its identical outer occurrence; retain nested refs.
  if q['unknown_parent_type']=='unbound_or_invalid_ref_occurrence':
   matches=[v for v in vals if v['raw']==q['raw'] and v['SHA256']==q['raw_SHA256']];assert len(matches)==1;vals.remove(matches[0]);count['duplicate_outer_shadow_entries']+=1
  for v in vals:assert H(v['raw'].encode())==v['SHA256'];observed[(row,q['section_ordinal'],v['SHA256'])]+=1
 for c in r['citation_companions']:
  for definition in c['definitions']:
   binding(definition['full_ref'],raw);binding(definition['content'],raw)
   for field in definition['content']['raw_citation_fields']:
    assert H(field['raw_template'].encode())==field['raw_SHA256']
    for param in field['raw_parameters']:assert H(param['raw_parameter'].encode())==param['raw_SHA256']
 for m in f['exact_raw_metadata_companions']:binding(m,raw)
 for k,s in enumerate(f['sections']):
  assert s['reference_holds']==r['source_partition'][k]['holds'] and set(s['reference_holds'])<=set(s['prose_structural_holds'])
  refholds=set(r['source_partition'][k]['semantic_companion_holds'])
  for c in r['citation_companions']:
   if any(r['ref_occurrences'][i]['section_ordinal']==k for i in c['occurrence_indices']):refholds.update(c['component_holds'])
  metadataholds={h for m in f['exact_raw_metadata_companions'] if m['section_ordinal']==k for h in m['component_holds']}
  assert set(s['reference_semantic_companion_holds'])==refholds and set(s['semantic_companion_holds'])==refholds|metadataholds
  for op in s['source_operations']:binding(op,raw)
  if s['operations_applied_to_provisional_markup']:
   a,b=s['source_char_span'];cursor=a;pieces=[]
   for op in sorted(s['source_operations'],key=lambda v:v['source_char_span']):
    oa,ob=op['source_char_span'];assert cursor<=oa<=ob<=b;pieces.extend([raw[cursor:oa],op['replacement']]);cursor=ob
   pieces.append(raw[cursor:b]);transformed=''.join(pieces);assert H(transformed.encode())==s['transformed_markup_SHA256']
   cursor=0;delta=0;back=[]
   for op in sorted(s['source_operations'],key=lambda v:v['source_char_span']):
    oa,ob=op['source_char_span'];position=oa-a+delta;rep=op['replacement'];assert transformed[position:position+len(rep)]==rep;back.extend([transformed[cursor:position],op['raw']]);cursor=position+len(rep);delta+=len(rep)-(ob-oa)
   back.append(transformed[cursor:]);assert ''.join(back)==s['raw'];count['operation_inverse_verified_sections']+=1
  else:assert s['transformed_markup_SHA256'] is None
  preview=s['provisional_prose_preview']
  if preview is None:assert s['preview_SHA256'] is None and s['prose_structural_holds']
  else:
   assert not s['prose_structural_holds'] and H(preview.encode())==s['preview_SHA256'];count['previews']+=1;preview_records.append({'row':row,'section':k,'UTF8_bytes':len(preview.encode()),'SHA256':s['preview_SHA256'],'semantic_companion_holds':s['semantic_companion_holds'],'full_output_file':str(p)})
 per.append({'row':row,'sections':len(f['sections']),'ordinary_refs':len(r['ref_occurrences']),'citation_companions':len(r['citation_companions']),'previews':sum(s['provisional_prose_preview'] is not None for s in f['sections'])})
invp=B/'m2-intake/enwiki-native20-dependency-inventory-v1/inventory.json';inventory=json.loads(invp.read_text());expected=Counter((q['row'],q['section'],q['node_literal_SHA256']) for q in inventory['dependency_occurrences'] if q['kind']=='Tag' and q['name_literal']=='ref');assert sum(expected.values())==192 and observed==expected
assert roles=={'redirect':9,'nonarticle':6,'pending':5} and count['sections']==27 and count['previews']==1
out={'status':'PASS_COMPLETE_NATIVE20_V3_TERMINAL_AND_EXACT_INVERSE_VERIFICATION_NO_RERUN','input_pins':{str(p):HP(p) for p in [P/'readiness.json',P/'code-pins.json',P/'profile.json',D/'result.json',D/'supervisor.json',invp]},'all_registry_pins_verified':len(pins),'preserved_roles':dict(roles),'counts':dict(count),'all192refs':{'ordinary':count['ordinary_ref_occurrences'],'opaque_entries':count['opaque_ref_entries'],'outer_already_counted_shadow_entries':count['duplicate_outer_shadow_entries'],'exact_inventory_row_section_rawSHA_multiplicity_match':True,'unique_occurrences':sum(observed.values())},'per_page':per,'diagnostic_previews':preview_records,'all_companion_holds_and_reference_holds_preserved':True,'all_raw_sections_operations_and_definition_inverses_verified':True,'no_render_reference_resolver_parser_or_tokenizer_invocation':True,'new_admitted_documents':0}
(O/'verification.json').write_text(json.dumps(out,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'files':{p.name:HP(p) for p in O.iterdir() if p.is_file() and p.name!='manifest.json'}},indent=2)+'\n');print(json.dumps(out['counts']));print('verification',HP(O/'verification.json'));print('manifest',HP(O/'manifest.json'))
