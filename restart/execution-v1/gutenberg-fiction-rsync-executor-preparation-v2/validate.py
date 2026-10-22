import hashlib,os,re,stat
from pathlib import Path
from transport import ProtocolError
CAP=2400000
def result(stage,eid,receipt):
 stage=Path(stage);expected='pg'+str(eid)+'.txt';entries=list(stage.iterdir())
 if any(p.name!=expected or not stat.S_ISREG(p.stat(follow_symlinks=False).st_mode) for p in entries):raise ProtocolError('unexpected_path_symlink_directory_or_special')
 stdout=receipt['stdout'];stderr=receipt['stderr'];code=receipt['exit_code']
 def integer(label):
  hits=re.findall(r'^'+re.escape(label)+r': ([0-9]+)(?: B)?$',stdout,re.M)
  if len(hits)!=1:raise ProtocolError('native_stats_schema')
  return int(hits[0])
 if not entries:
  # Only a narrowly identified source absence/size skip may continue; never infer from exit0 alone.
  wanted=re.escape(str(eid)+'/pg'+str(eid)+'.txt')
  missing=r"rsync\([0-9]+\): error: '"+wanted+r"': \(l\)stat: No such file or directory"
  harmless=r'rsync\([0-9]+\): warning: receiver has empty file list: exiting'
  lines=stderr.splitlines()
  if code==23 and any(re.fullmatch(missing,x) for x in lines) and all(re.fullmatch(missing,x) or re.fullmatch(harmless,x) for x in lines):return {'status':'INDEPENDENT_SOURCE_MISSING_NO_RETRY','can_continue':True}
  if code==0 and not stderr and 'skipping' not in stdout and integer('Number of files')==1 and integer('Number of files transferred')==0 and integer('Total file size')>CAP and integer('Total transferred file size')==0:return {'status':'INDEPENDENT_SOURCE_OVERSIZE_SKIPPED_NO_RETRY','can_continue':True}
  raise ProtocolError('empty_result_unrecognized_not_success')
 p=entries[0];before=p.stat(follow_symlinks=False)
 if code!=0 or stderr or not 0<before.st_size<=CAP or integer('Number of files')!=1 or integer('Number of files transferred')!=1 or integer('Total transferred file size')!=before.st_size or integer('Total file size')!=before.st_size:raise ProtocolError('raw_completion_stats_size_or_status')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  ident=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
  if ident(os.fstat(fd))!=ident(before):raise ProtocolError('completed_raw_FD_custody')
  digest=hashlib.sha256();n=0
  while True:
   raw=os.read(fd,min(1048576,CAP-n+1))
   if not raw:break
   n+=len(raw)
   if n>CAP:raise ProtocolError('raw_cap')
   digest.update(raw)
  if n!=before.st_size or ident(os.fstat(fd))!=ident(before) or ident(p.stat(follow_symlinks=False))!=ident(before):raise ProtocolError('raw_changed')
 finally:os.close(fd)
 return {'status':'COMPLETE_RAW_DISCOVERY_NOT_ADMITTED','file':p.name,'bytes':n,'SHA256':digest.hexdigest(),'can_continue':True,'source_version_matches_catalog':False,'publisher_checksum_claimed':False}
def next_state(consecutive,result):
 if result['status']=='COMPLETE_RAW_DISCOVERY_NOT_ADMITTED':return 0,True
 if result['status'] in {'INDEPENDENT_SOURCE_MISSING_NO_RETRY','INDEPENDENT_SOURCE_OVERSIZE_SKIPPED_NO_RETRY','INDEPENDENT_SOURCE_TIMEOUT_NO_RETRY'}:return consecutive+1,consecutive+1<3
 raise ProtocolError('unrecognized_error_is_fatal')
