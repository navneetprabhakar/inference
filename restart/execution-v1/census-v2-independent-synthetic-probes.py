import importlib.util,tempfile,pathlib,os,stat,json
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parent/'enwiki-retained-prefix-frame-preparation-v2/tree_size.py'
spec=importlib.util.spec_from_file_location('census_review',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]
with tempfile.TemporaryDirectory() as z:
 root=pathlib.Path(z);big=root/'part.partial'
 with big.open('wb') as f:f.seek(300000000-1);f.write(b'x')
 (root/'little').write_bytes(b'abc');original=pathlib.Path.stat;trigger=[False]
 def renamed(p,*a,**kw):
  if p==big and not trigger[0]:trigger[0]=True;big.rename(root/'part.final')
  return original(p,*a,**kw)
 with patch.object(pathlib.Path,'stat',renamed):assert m.census(root)==300000003
 assert trigger[0];checks.append('rename300MB_wholecensus_restart_preserves_all_bytes')
 counts={}
 def once(p,*a,**kw):counts[str(p)]=counts.get(str(p),0)+1;return original(p,*a,**kw)
 with patch.object(pathlib.Path,'stat',once):assert m.census(root)==300000003
 assert all(n==1 for n in counts.values());checks.append('exact_one_lstat_per_visited_path_fixedtree')
 attempts=[0]
 def churn(p,*a,**kw):attempts[0]+=1;raise FileNotFoundError('synthetic')
 with patch.object(pathlib.Path,'stat',churn):
  try:m.census(root)
  except ValueError as e:assert 'after8' in str(e)
  else:raise AssertionError('churn accepted')
 assert attempts[0]==8;checks.append('persistent_ENOENT_exact8_attempts_failclosed')
 attempts=[0]
 def denied(p,*a,**kw):attempts[0]+=1;raise PermissionError('synthetic')
 with patch.object(pathlib.Path,'stat',denied):
  try:m.census(root)
  except PermissionError:pass
  else:raise AssertionError('permissions skipped')
 assert attempts[0]==1;checks.append('nonENOENT_IO_errors_propagate_no_skip')
 (root/'link').symlink_to(root/'part.final')
 try:m.census(root)
 except ValueError:pass
 else:raise AssertionError('symlink accepted')
 checks.append('symlink_refused_not_followed_or_ignored')
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','checks':checks,'count':len(checks),'retained_source_reads':0},indent=2))
