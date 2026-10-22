"""One metadata-only DEVELOPMENT draw freeze. No original gzip or text body reads."""
import time,signal
START=time.monotonic()
def stop(*a):raise TimeoutError('metadata60seconds')
signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,60)
from pathlib import Path
import sqlite3,json,hashlib,collections
from select_core import draws
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;FOLDER=BASE/'m2-intake/hansard-two-complete-shard-inventory-v1';DB=FOLDER/'frame.sqlite';HELD='1ac03f93f6b77284ceb6e8ba36420e39f8d0157e2f6dd30515df6c3b7cb4a77d'
def ident(p):
 s=p.stat(follow_symlinks=False);return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
proof=BASE/'hansard-two-complete-shard-inventory-terminal-independent-verification-v1/verification.json';prior=json.loads(proof.read_text());producer=json.loads((FOLDER/'result.json').read_text());assert prior['status'].startswith('PASS_TWO_COMPLETE_SOURCE_') and prior['result_SHA256']==sha(FOLDER/'result.json');before=ident(DB);assert before[2]==producer['artifacts']['frame.sqlite']['bytes'];db=sqlite3.connect(DB.as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('pragma query_only=ON');db.execute('pragma cache_size=-4096');db.execute('pragma mmap_size=0')
cohort={};excluded=[];rawcategories=collections.Counter();hashcategories=collections.defaultdict(set);linehashes={1:hashlib.sha256(),2:hashlib.sha256()};rowscount=0
for sid,ordinal,off,n,lf,line,flags,ID,category,added,year,lang,license,text,nb,nc in db.execute('select * from records order by source_id,ordinal'):
 rowscount+=1;h=text.hex();rawcategories[category]+=1;linehashes[sid].update(json.dumps([sid,ordinal,off,n,lf,line.hex()],separators=(',',':')).encode()+b'\n');hashcategories[category].add(h)
 if h==HELD:excluded.append([sid,ordinal,ID,h]);continue
 if h not in cohort:cohort[h]={'text_SHA256':h,'text_UTF8_bytes':nb,'source_id':sid,'ordinal':ordinal,'line_offset':off,'line_bytes':n,'ends_LF':lf,'line_SHA256':line.hex(),'existing_flags':flags,'native_subsource':category,'all_alias_subsources':[category],'copies':1}
 else:
  assert cohort[h]['text_UTF8_bytes']==nb;cohort[h]['copies']+=1
  if category not in cohort[h]['all_alias_subsources']:cohort[h]['all_alias_subsources'].append(category)
assert rowscount==15820 and len(cohort)==15799 and len(excluded)==1
s=draws(list(cohort.values()));s['selected_capture_occurrences']=[cohort[h]for h in sorted({r['text_SHA256']for r in s['draws']})];chosen={r['text_SHA256']:r for r in s['selected_capture_occurrences']};drawcategories=collections.Counter(chosen[x['text_SHA256']]['native_subsource']for x in s['draws']);capturecategories=collections.Counter(x['native_subsource']for x in chosen.values());textbytes=sum(x['text_UTF8_bytes']for x in chosen.values());linebytes=sum(x['line_bytes']for x in chosen.values());assert textbytes<=30000000 and textbytes+linebytes+2097152<100000000 and ident(DB)==before;db.close()
s.update(status='FROZEN_METADATA_ONLY_HANSARD_DEVELOPMENT_SELECTION_PRECONTENT',all_union_textSHA=15800,removed_exact_semantic_hold_textSHA=[HELD],excluded_occurrences=excluded,total_native_occurrences=15820,canonical_rule='Earliest(source_id,ordinal) capture occurrence only, NOT preferred corpusversion or day/speech/family identity',frame={'path':str(DB),'inherited_SHA256':producer['artifacts']['frame.sqlite']['SHA256'],'stat':before,'producer_result_SHA256':sha(FOLDER/'result.json'),'independent_terminal_metadata_SHA256':sha(proof)},source_body_reads=0,elapsed_seconds=time.monotonic()-START,source_line_transcripts={str(k):v.hexdigest()for k,v in linehashes.items()},capacity={'selected_text_UTF8_bytes':textbytes,'selected_raw_JSON_line_bytes':linebytes,'selected_max_text_bytes':max(x['text_UTF8_bytes']for x in chosen.values()),'text_cap':30000000,'output_cap':100000000},subsource_coverage_diagnostic={'population_raw_rows':dict(rawcategories),'population_distinct_hash_membership':{k:len(v)for k,v in hashcategories.items()},'all30_draw_canonical_subsources_with_multiplicity':dict(drawcategories),'unique_capture_canonical_subsources':dict(capturecategories),'missing_raw_categories_not_forced_replaced':sorted(set(rawcategories)-set(capturecategories))},all_rights_status='UNCLEARED_REGARDLESS_SUBSOURCE',language_and_quality_clearance=False)
(HERE/'selection.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps({k:s[k]for k in ['population_distinct_textSHA','population_UTF8_bytes','capture_distinct_textSHA','capacity','subsource_coverage_diagnostic','source_body_reads']}));signal.setitimer(signal.ITIMER_REAL,0)
