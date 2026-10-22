"""Fixed30 development runner only; no original gzip/full source access."""
import collections,hashlib,json,os,stat
from pathlib import Path
import policy

def run(profile,out,check):
 out=Path(out);metrics=collections.Counter();language_metrics=collections.Counter();summaries=[];bytesread=0;maxevents=0;maxreceipt=0;known=profile['development_labels']
 with (out/'units.metadata.jsonl').open('xb') as receipt:
  for item in profile['inputs']:
   check();p=Path(item['text_path'])
   def ident(v):return [v.st_dev,v.st_ino,v.st_size,v.st_mtime_ns,v.st_ctime_ns]
   policy.require(not p.is_symlink() and ident(p.stat())==item['stat'],'source_stat_before')
   fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
   try:
    policy.require(stat.S_ISREG(os.fstat(fd).st_mode) and ident(os.fstat(fd))==item['stat'],'source_FD_identity')
    with os.fdopen(fd,'rb',closefd=False) as f:raw=f.read(min(item['bytes'],policy.MAX_BYTES)+1)
    policy.require(ident(os.fstat(fd))==item['stat'] and ident(p.stat())==item['stat'],'source_unchanged')
   finally:os.close(fd)
   bytesread+=len(raw)
   policy.require(len(raw)==item['bytes'] and policy.sha(raw)==item['SHA256'],'selected_source_text_hash_bytes')
   text=raw.decode('utf8');r=policy.filter_raw(text);maxevents=max(maxevents,len(r['reasons'])+len(r['context_only_diagnostics']));components=policy.separate_components(text,None)
   label=known[item['SHA256']];knownhold=label['verdict'].startswith('HOLD');automatic=bool(r['reasons'])
   cell='known_HOLD_generic_flag' if knownhold and automatic else 'known_HOLD_generic_not_flagged' if knownhold else 'research_proxy_generic_flag' if automatic else 'research_proxy_generic_not_flagged'
   metrics[cell]+=1
   language_pass=item['existing_language_pass']
   policy.require(type(language_pass)==bool,'frozen_language_bool')
   if language_pass:language_metrics[cell]+=1;language_metrics['whole_units']+=1
   metrics['generic_rule_held_whole_units']+=automatic;metrics['known_exact_review_holds']+=knownhold
   finalhold=knownhold or automatic or not language_pass
   decision='HOLD_CURRENT_RAW_REPRESENTATION_REVIEW' if finalhold else 'UNCHANGED_RAW_CANDIDATE_PENDING_FRESH_ACCEPTANCE_RIGHTS_FAMILY_LEAKAGE'
   candidate=None
   if not finalhold:
    name=f"source-{item['source_id']}-row-{item['ordinal']:06d}.candidate.utf8";check(len(raw))
    with (out/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    candidate={'path':name,'bytes':len(raw),'SHA256':policy.sha(raw),'source_bytes_changed':0,'admitted':False}
   record={'source_id':item['source_id'],'ordinal':item['ordinal'],'source_path':str(p),'source_SHA256':item['SHA256'],'source_bytes':len(raw),'raw_JSON_ancestry':item['raw_JSON'],'selection_draw_roles':item['draws'],'generic_raw_rule':r,'existing_known_whole_review':label,'existing_language_pass':language_pass,'current_disposition_holds':(["EXACT_KNOWN_REVIEW"] if knownhold else [])+(["GENERIC_RAW_REPRESENTATION_RULE"] if automatic else [])+([] if language_pass else ["EXISTING_FROZEN_LANGUAGE_POLICY"]),'current_decision':decision,'whole_raw_candidate':candidate,'component_transform':components,'source_original_retained':True,'all_other_gates_uncleared':True,'new_admitted_documents':0}
   b=(json.dumps(record,ensure_ascii=False,separators=(',',':'))+'\n').encode();check(len(b));policy.require(len(b)<=1000000,'per_unit_receipt_cap');receipt.write(b);maxreceipt=max(maxreceipt,len(b))
   summaries.append({'source_id':item['source_id'],'ordinal':item['ordinal'],'SHA256':item['SHA256'],'generic_reason_codes':[v['reason'] for v in r['reasons']],'review_verdict':label['verdict'],'decision':decision,'candidate_bytes':len(raw) if candidate else 0});metrics['unchanged_raw_candidate_units']+=bool(candidate);metrics['unchanged_raw_candidate_bytes']+=len(raw) if candidate else 0
  receipt.flush();os.fsync(receipt.fileno())
 policy.require(bytesread==profile['expected_input_text_bytes'] and len(summaries)==30,'fixed30_complete_capture_reconciliation')
 tp=metrics['known_HOLD_generic_flag'];fp=metrics['research_proxy_generic_flag'];fn=metrics['known_HOLD_generic_not_flagged']
 lp=language_metrics['known_HOLD_generic_flag'];lfp=language_metrics['research_proxy_generic_flag'];lfn=language_metrics['known_HOLD_generic_not_flagged']
 return {'status':'COMPLETE_FIXED30_GENERIC_RAW_FILTER_DEVELOPMENT_NO_ADMISSION','whole_units':30,'max_diagnostic_events_per_unit':maxevents,'max_unit_receipt_bytes':maxreceipt,'text_bytes_read':bytesread,'diagnostics':dict(metrics),'existing_language_pass_conditioned_diagnostics':dict(language_metrics),'existing_language_pass_conditioned_label_comparison':{'precision':lp/(lp+lfp) if lp+lfp else None,'recall':lp/(lp+lfn) if lp+lfn else None,'not_population_or_acceptance':True,'known_hold_label_scope_is_broader_than_raw_rules':True},'development_label_comparison':{'generic_flag_precision_against_any_known_review_HOLD':tp/(tp+fp) if tp+fp else None,'generic_flag_recall_against_any_known_review_HOLD':tp/(tp+fn) if tp+fn else None,'not_acceptance_or_population_estimate':True,'scope_limit':'Review HOLDs include factual/rights/dependency/verse issues beyond these representation/role rules. Generic nonflag is not semantic quality pass. Exact prior known HOLD always preserved.'},'units':summaries,'component_transformations_performed':0,'native_structure_needed':'For removing attribution/glossary/catalog tails: exact source-native HTML/DOM roles and full text projection proof, authored section boundaries, math/figure/notes/dependency inventory and rights/sourceversion binding. Not needed merely to preserve untouched whole raw candidate.','new_admitted_documents':0,'new_admitted_tokens':0,'retokenization_or_network':False}
