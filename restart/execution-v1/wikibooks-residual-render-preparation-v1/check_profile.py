import tempfile,pathlib,json,os
from unittest.mock import patch
import profile as p
import aggregate as a
import reader_core as rc
checks=[]
def good(old,ex,jobs,excluded=()):p.validate_sets(old,ex,[{'ordinals':x} for x in jobs],excluded)
def bad(name,*args):
 try:good(*args)
 except ValueError:checks.append(name)
 else:raise AssertionError(name)
good({1,2},{1,2,3,4},[[3],[4]]);checks.append('exact_residual_difference')
good({1,2},{2,3},[[3]],[1]);checks.append('explicit_prior_exclusion_mapping')
bad('old_rerender_forbidden',{1},{1,2},[[1,2]])
bad('overlap_forbidden',{1},{1,2},[[2],[2]])
bad('missing_forbidden',{1},{1,2,3},[[2]])
bad('extra_forbidden',{1},{1,2},[[2,3]])
bad('unsorted_forbidden',{1},{1,2,3},[[3,2]])
bad('empty_forbidden',{1},{1,2},[[]])
bad('job_record_cap',set(),set(range(6079)),[list(range(6079))])
bad('unmapped_prior_exclusion',{1,2},{2,3},[[3]])
bad('false_prior_exclusion',{1,2},{1,2,3},[[3]],[1])
with patch.dict(os.environ,{},clear=True):
 try:p.load()
 except KeyError:checks.append('missing_effective_profile_failclosed')
 else:raise AssertionError('profile_required')
with tempfile.TemporaryDirectory() as t:
 root=pathlib.Path(t);fake={'canonical_sha256':'canonical','profile_sha256':'profile','jobs_loaded':[{'ordinals':[i+1],'end_source_ordinal':i+1,'manifest':{'sha256':str(i)}} for i in range(8)]}
 with patch.object(a.effective_profile,'load',return_value=fake),patch.object(rc,'INTAKE_ROOT',root),patch.object(rc,'output_size',return_value=0),patch.object(a.shutil,'disk_usage',return_value=type('D',(),{'free':10**12})()):
  for i in range(1,9):a.reserve(i,root/('shard-'+str(i)),1,root=root)
  state=json.loads((root/'aggregate-ledger.json').read_text());assert sum(x['reserved_seconds'] for x in state['attempts'].values())==7200;checks.append('eight_durable_reservations7200')
  try:a.reserve(1,root/'shard-1',1,root=root)
  except ValueError:checks.append('reserved_job_never_retried')
  else:raise AssertionError('retry')
  a.finish(1,900,'PARTIAL',root=root);state=json.loads((root/'aggregate-ledger.json').read_text());assert state['attempts']['1']['reserved_seconds']==900;checks.append('partial_no_refund')
  target=root/'durable.json'
  with patch.object(a.os,'fsync',wraps=a.os.fsync) as fsync:a.durable_write(target,{'ok':True});assert fsync.call_count==2;checks.append('file_and_directory_fsync')
print(json.dumps({'passed':len(checks),'checks':checks},indent=2))
