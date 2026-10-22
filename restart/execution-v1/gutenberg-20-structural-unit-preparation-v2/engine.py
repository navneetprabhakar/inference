"""Exact20 finite structural candidate metadata; never source/quality admission."""
from pathlib import Path
import hashlib,json,os,collections
import custody,segment
need=segment.need

def preflight(p):
 s=json.loads(Path(p['selection_path']).read_text());popraw=Path(s['population_profile']).read_bytes();need(hashlib.sha256(popraw).hexdigest()==s['population_profile_SHA256'],'frozen_population_profile_SHA');pop=json.loads(popraw);seed=s['seed'];need(seed=='PG20-structural-development-v1-precontent-20261021' and s['population_frozen_rows']==300,'fixed_seed_population');rank=[]
 need(len(pop['records'])==len(pop['source_files'])==len(pop['envelopes'])==300,'frozen300_population')
 for r,src,e in zip(pop['records'],pop['source_files'],pop['envelopes']):
  pre=(seed+'\0'+str(r['ordinal'])+'\0'+str(r['ebook_ID'])+'\0'+src['SHA256']).encode('utf8');rank.append({'priority_SHA256':hashlib.sha256(pre).hexdigest(),'record':r,'source_file':src,'envelope':e})
 chosen=sorted(rank,key=lambda r:r['priority_SHA256'])[:20]
 need(s['records']==chosen and p['records']==[x['record'] for x in chosen] and p['source_files']==[x['source_file'] for x in chosen] and p['envelopes']==[x['envelope'] for x in chosen],'exact20_precontent_priority_selection')
 need(p['expected_selected_raw_bytes']==sum(x['source_file']['bytes'] for x in chosen)==11988436 and p['expected_selected_envelope_bytes']==sum(x['envelope']['bytes'] for x in chosen)==11590570,'exact_selected_byte_denominators')
 return True

def run(p,out,check):
 stats=collections.Counter();sha=hashlib.sha256();written=0;out=Path(out)
 with (out/'records.jsonl').open('xb') as f:
  for r,src,e in zip(p['records'],p['source_files'],p['envelopes']):
   check();raw=custody.read_source(p['source_output'],src,check);stats['raw_source_bytes']+=len(raw);need(stats['raw_source_bytes']<=48000000,'aggregate_raw_cap')
   x=segment.discover(raw,e,r['ebook_ID']);x['prior_v1_ancestry']={'original_all20_outcomes_retained':True,'original13_fallbacks_not_relabelled_as_pass':True,'known_unit_holds_preserved':p.get('prior_development_holds',[])};stats['role_events']+=len(x['lexical_role_reconciliation']);need(stats['role_events']<=30000,'aggregate_role_events_no_truncation');stats['books']+=1;stats['whole_envelope_fallbacks']+=x['whole_envelope_fallback'];stats['chapter_candidate_units']+=sum(u['structural_status'].startswith('ORDERED') for u in x['units']);stats['envelope_bytes']+=e['bytes'];stats['units_including_fallbacks']+=len(x['units']);stats['events']+=sum(len(x[k]) for k in ['chapter_heading_candidates','unsupported_chapter_like_lines','structure_heading_hints','literal_ending_hints','note_dependency_hints']);need(stats['units_including_fallbacks']<=10000 and stats['events']<=30000,'aggregate_units_event_cap_no_truncation')
   record={'ordinal':r['ordinal'],'ebook_ID':r['ebook_ID'],'catalog_record_all_roles_preserved':r,'source_file':src,'catalog_current_edition_equivalence':'UNVERIFIED','family_custody':'Whole frozen conservative family; all editions and print aggregates require separate custody review','known_related_work_overlay':p.get('related_work_overlay'), 'prior_v1_output':p.get('prior_v1_output'),'structural_discovery':x,'semantic_or_rights_usable':False,'new_admitted_documents':0}
   b=(json.dumps(record,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode();need(len(b)<=1048576 and written+len(b)<=12000000,'metadata_record_stream_cap');check(len(b));f.write(b);f.flush();os.fsync(f.fileno());sha.update(b);written+=len(b)
 need(stats['books']==20 and stats['raw_source_bytes']==p['expected_selected_raw_bytes'] and stats['envelope_bytes']==p['expected_selected_envelope_bytes'],'complete_fixed20_denominators')
 for src in p['source_files']:check();need(custody.identity((Path(p['source_output'])/src['path']).stat(follow_symlinks=False))==src['dev_ino_size_mtime_ns_ctime_ns'],'all_selected_sources_final_stat')
 return {'status':'COMPLETE_PG20_STRUCTURAL_UNIT_DISCOVERY_NO_ADMISSION','stats':dict(stats),'records_file':'records.jsonl','records_bytes':written,'records_SHA256':sha.hexdigest(),'all20_outcomes_retained_no_replacements':True,'full_raw_source_inverse_all20':True,'source_originals_unchanged':True,'raw_text_copies_written':0,'unit_semantic_completeness_clearance':False,'new_admitted_documents':0,'new_admitted_tokens':0}
