"""Authorized metadata-only draw freeze. No compressed source/text body reads."""
import signal,time
START=time.monotonic()
def stop(*a):raise TimeoutError('metadata60sec')
signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,60)
from pathlib import Path
import sqlite3,json,hashlib,sys
from select_core import draws
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;DB=BASE/'m2-intake/pressbooks-full-two-shard-family-leads-v2/leads.sqlite'
def ident(p):
 s=p.stat(follow_symlinks=False);return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
prior=BASE/'pressbooks-full-family-lead-terminal-independent-verification-v2/verification.json';proof=json.loads(prior.read_text());producer=json.loads((DB.parent/'result.json').read_text());expected=producer['artifacts']['leads.sqlite']
assert DB.stat().st_size==expected['bytes']==41373696
before=ident(DB);c=sqlite3.connect(DB.as_uri()+'?mode=ro&immutable=1',uri=True);c.execute('PRAGMA query_only=ON');c.execute('PRAGMA cache_size=-4096');c.execute('PRAGMA mmap_size=0')
# Exact explicit sourceidentity/catalog holds propagate by textSHA across all aliases.
held={bytes(r[0]).hex() for r in c.execute('SELECT DISTINCT text_SHA256 FROM rows WHERE identity_holds<>0')};assert len(held)==13
cohort={};occ=0;excluded=0
for sid,ordinal,off,n,lf,line,text,nb,flags,identity,lead in c.execute('SELECT source_id,ordinal,line_offset,line_bytes,ends_LF,line_SHA256,text_SHA256,text_UTF8_bytes,existing_flags,identity_holds,lead_status FROM rows ORDER BY source_id,ordinal'):
 occ+=1;h=bytes(text).hex()
 if h in held:excluded+=1;continue
 if h not in cohort:cohort[h]={'text_SHA256':h,'text_UTF8_bytes':nb,'source_id':sid,'ordinal':ordinal,'line_offset':off,'line_bytes':n,'ends_LF':lf,'line_SHA256':bytes(line).hex(),'existing_flags':flags,'identity_holds':identity,'lead_status':lead,'copies':1}
 else:
  assert cohort[h]['text_UTF8_bytes']==nb;cohort[h]['copies']+=1
assert occ==106881 and len(cohort)==79861
selected=draws(list(cohort.values()));selected['selected_capture_occurrences']=[cohort[h] for h in sorted({r['text_SHA256'] for r in selected['draws']})]
selected.update(status='FROZEN_METADATA_ONLY_DEVELOPMENT_SELECTION_PRECONTENT',all_union_textSHA=79874,removed_explicit_hold_hashes=sorted(held),excluded_occurrences=excluded,total_native_occurrences=occ,canonical_rule='Earliest(source_id,ordinal) solely for capture occurrence, NOT preferred version/canonical corpus choice',family_uncertainty_retained=True,frame={'path':str(DB),'inherited_SHA256':expected['SHA256'],'stat':before,'producer_result_SHA256':sha(DB.parent/'result.json'),'independent_terminal_metadata_SHA256':sha(prior)},source_body_reads=0,elapsed_seconds=time.monotonic()-START)
assert ident(DB)==before;c.close()
(HERE/'selection.json').write_text(json.dumps(selected,indent=2)+'\n')
print(json.dumps({k:selected[k] for k in ['population_distinct_textSHA','population_UTF8_bytes','capture_distinct_textSHA','excluded_occurrences','source_body_reads','elapsed_seconds']}));signal.setitimer(signal.ITIMER_REAL,0)
