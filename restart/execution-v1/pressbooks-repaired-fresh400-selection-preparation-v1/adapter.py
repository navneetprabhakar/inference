"""Finite metadata-only adapter for COMPLETE fresh400 selection. No live SQLite use."""
import collections,hashlib,json

def require(v,msg):
 if not v:raise ValueError(msg)
def adapt(selection,lookup):
 require(selection['status']=='FROZEN_PRE_REVIEW_CANDIDATE_QUALITY_AUDIT_SELECTION_NOT_M2_ACCEPTANCE','selection_status')
 draws=selection['draws'];require(len(draws)==400,'exact400_draws')
 require(collections.Counter(d['mode'] for d in draws)=={'UNIFORM_DISTINCT_RAW_SHA_WITHOUT_REPLACEMENT':200,'TOKEN_WEIGHTED_WITH_REPLACEMENT_NOT_BYTES':200},'exact_draw_modes')
 byhash={};roles={};seen=set();uniform=set()
 for d in draws:
  mode,num=d['mode'],d['draw'];require(type(num)==int and 1<=num<=200 and (mode,num) not in seen,'unique_draw_role');seen.add((mode,num))
  h=d['text_SHA256'];require(len(h)==64 and bytes.fromhex(h).hex()==h,'raw_SHA_format')
  current=(d['capture_source_id'],d['capture_ordinal'],d['UTF8_bytes'],d['M1_content_tokens'])
  if h in byhash:require(byhash[h]==current,'repeated_raw_SHA_capture_context_mismatch')
  else:byhash[h]=current
  roles.setdefault(h,[]).append(d)
  if mode.startswith('UNIFORM'):require(h not in uniform,'uniform_withoutreplacement');uniform.add(h)
 require(len(uniform)==200 and len(byhash)==selection['unique_drawn_raw_SHA'],'distinct_draw_reconciliation')
 selected=[]
 for h,(sid,ordinal,n,t) in sorted(byhash.items(),key=lambda p:(p[1][0],p[1][1])):
  row=lookup(sid,ordinal)
  require(row['text_SHA256']==h and row['text_UTF8_bytes']==n,'source_frame_hash_bytes_lookup')
  require(row['source_id']==sid and row['ordinal']==ordinal and row['line_bytes']<=4000000 and n<=2196000,'source_locator_identity_caps')
  selected.append({**row,'M1_content_tokens':t,'draw_roles':[{'mode':d['mode'],'draw':d['draw'],'text_SHA256':h} for d in roles[h]]})
 stats={'unique_raw_SHA':len(selected),'draws':400,'text_UTF8_bytes':sum(r['text_UTF8_bytes'] for r in selected),'original_JSON_bytes':sum(r['line_bytes'] for r in selected),'max_text_UTF8_bytes':max(r['text_UTF8_bytes'] for r in selected),'max_original_JSON_bytes':max(r['line_bytes'] for r in selected),'M1_content_tokens':sum(r['M1_content_tokens'] for r in selected)}
 require(stats['text_UTF8_bytes']==selection['unique_capture_UTF8_bytes'] and stats['M1_content_tokens']==selection['unique_capture_M1_content_tokens'] and stats['max_text_UTF8_bytes']==selection['largest_selected_UTF8_bytes'],'producer_capture_cost_reconciliation')
 return {'status':'PREPARED_CAPTURE_SELECTION_FROM_TERMINAL_METADATA_ONLY','draws':draws,'selected_capture_occurrences':selected,'stats':stats,'capture_occurrence_not_version_choice':True,'all_draw_multiplicity_preserved':True,'no_source_body_reads':True}

def verify_derived(s):
 require(s['status']=='PREPARED_CAPTURE_SELECTION_FROM_TERMINAL_METADATA_ONLY','derived_status')
 draws=s['draws'];chosen=s['selected_capture_occurrences'];require(len(draws)==400,'derived400')
 full=collections.Counter((d['mode'],d['draw'],d['text_SHA256']) for d in draws);refs=collections.Counter((r['mode'],r['draw'],r['text_SHA256']) for c in chosen for r in c['draw_roles'])
 require(full==refs and all(v==1 for v in full.values()),'exact_all_draw_reference_partition')
 require(collections.Counter(d['mode'] for d in draws)=={'UNIFORM_DISTINCT_RAW_SHA_WITHOUT_REPLACEMENT':200,'TOKEN_WEIGHTED_WITH_REPLACEMENT_NOT_BYTES':200},'derived_modes')
 require(len({d['text_SHA256'] for d in draws if d['mode'].startswith('UNIFORM')})==200,'derived_uniform_WOR')
 require(len({c['text_SHA256'] for c in chosen})==len(chosen) and len({(c['source_id'],c['ordinal']) for c in chosen})==len(chosen),'derived_unique_capture')
 by={c['text_SHA256']:c for c in chosen}
 for d in draws:
  c=by[d['text_SHA256']]
  require((d['capture_source_id'],d['capture_ordinal'],d['UTF8_bytes'],d['M1_content_tokens'])==(c['source_id'],c['ordinal'],c['text_UTF8_bytes'],c['M1_content_tokens']),'derived_exact_role_capture_cost')
 for c in chosen:require(all(r['text_SHA256']==c['text_SHA256'] for r in c['draw_roles']),'role_attached_to_exact_capture')
 stats={'unique_raw_SHA':len(chosen),'draws':400,'text_UTF8_bytes':sum(c['text_UTF8_bytes'] for c in chosen),'original_JSON_bytes':sum(c['line_bytes'] for c in chosen),'max_text_UTF8_bytes':max(c['text_UTF8_bytes'] for c in chosen),'max_original_JSON_bytes':max(c['line_bytes'] for c in chosen),'M1_content_tokens':sum(c['M1_content_tokens'] for c in chosen)}
 require(stats==s['stats'],'derived_stats')
 return stats
