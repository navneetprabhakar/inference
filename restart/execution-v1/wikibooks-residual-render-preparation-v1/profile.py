"""Parent-frozen NEW internal profile protocol; no default launchable profile."""
import hashlib,json,os,pathlib,sqlite3
HERE=pathlib.Path(__file__).resolve().parent
BASE=HERE.parent
ROOT=BASE/'m2-intake/wikibooks-residual-render-v1'
MAX_JOB_RECORDS=6078

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def checked_path(item):
 p=pathlib.Path(item['path']).resolve()
 if sha(p)!=item['sha256']:raise ValueError('effective_profile_input_hash_mismatch')
 return p
def validate_sets(old,expected,jobs,excluded=()):
 if set(excluded)!=old-expected:raise ValueError('old_rows_excluded_or_reidentified_need_separate_reconciliation')
 seen=set()
 for j in jobs:
  ids=j['ordinals']
  if not ids or len(ids)>MAX_JOB_RECORDS or len(ids)!=len(set(ids)) or ids!=sorted(ids):raise ValueError('job_size_or_order')
  if set(ids)&old:raise ValueError('old_ordinal_rerender_forbidden')
  if set(ids)&seen:raise ValueError('overlapping_residual_jobs')
  seen.update(ids)
 if seen!=expected-old:raise ValueError('missing_or_extra_residual_targets')
 return seen

def load():
 path=pathlib.Path(os.environ['WIKIBOOKS_EFFECTIVE_PROFILE']).resolve();pin=os.environ['WIKIBOOKS_EFFECTIVE_PROFILE_SHA256']
 if sha(path)!=pin:raise ValueError('profile_hash_mismatch')
 p=json.loads(path.read_text())
 if p.get('status')!='PARENT_FROZEN_EFFECTIVE_RESIDUAL_INPUTS_NO_ADMISSION' or p.get('oversize_identity_reconciliation_complete') is not True:raise ValueError('oversize_identity_reconciliation_not_complete')
 if p['archive_sha256']!='361fb441fe35d13be56c4eca22a09df6868a663e5d7f3b1ed2a665e332a4d263' or p['max_source_ordinal']!=89951:raise ValueError('source_frame_changed_requires_new_review')
 checked_path(p['identity_reconciliation_receipt']);delta=json.loads(checked_path(p['identity_delta']).read_text())
 if len(delta)!=29 or len({r['page_id'] for r in delta})!=29 or any(r['existing_selection_changes'] or r['shadowed_existing_maximum'] or not r['supplement_remains_render_held'] or r['existing_same_page_occurrences'] or r['same_page_or_title_URL_alias_candidates'] for r in delta):raise ValueError('supplement_not_zero_change_held29')
 for item in p.get('additional_identity_inputs',[]):checked_path(item)
 canonical=checked_path(p['canonical']);d=sqlite3.connect('file:'+str(canonical)+'?mode=ro',uri=True);expected={o for o, in d.execute('select source_ordinal from candidates')};d.close();old=set()
 if len(p['prior_shards'])!=4 or len(p['jobs'])!=8:raise ValueError('exact_four_prior_eight_new_jobs_required')
 for item in p['prior_shards']:
  db=checked_path(item);d=sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True)
  for o, in d.execute('select source_ordinal from rendered'):
   if o in old:raise ValueError('prior_duplicate_ordinal')
   old.add(o)
  d.close()
 if len(old)!=50457:raise ValueError('original_verified_union_count_changed')
 jobs=[]
 for i,j in enumerate(p['jobs'],1):
  if j['job']!=i or j['wave']!=(1 if i<=4 else 2):raise ValueError('fixed_two_wave_job_schedule')
  f=checked_path(j['manifest']);rows=[json.loads(x) for x in f.read_text().splitlines()];ordinals=[r['source_ordinal'] for r in rows]
  if j['end_source_ordinal']!=(89951 if i==8 else max(ordinals)):raise ValueError('fixed_job_end_mismatch')
  jobs.append(dict(j,ordinals=ordinals,rows=rows))
 validate_sets(old,expected,jobs,p.get('prior_excluded_ordinals',[]))
 return dict(p,canonical_path=canonical,canonical_sha256=p['canonical']['sha256'],profile_sha256=pin,jobs_loaded=jobs)
