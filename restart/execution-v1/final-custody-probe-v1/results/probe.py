import json,os,pathlib,socket,sqlite3,sys
from slm.restart.final_state import readonly
project,state,output=map(pathlib.Path,sys.argv[1:]);checks=[]
assert (state/'sentinel.txt').read_text()=='immutable fixture\n'
db=readonly(state/'fixture.sqlite',immutable=True)
assert db.execute('SELECT value FROM fixture').fetchone()[0]==42
try:db.execute('UPDATE fixture SET value=0')
except sqlite3.OperationalError:checks.append('SQLite mutation denied')
else:raise RuntimeError('SQLite write allowed')
db.close()
for path in [state/'sentinel.txt',project/'restart/approval-v1/policy.json']:
 try:fd=os.open(path,os.O_WRONLY)
 except PermissionError:checks.append('write denied: '+str(path))
 else:os.close(fd);raise RuntimeError('Outside-results write allowed')
for suite in ('grammar','grounded','narrative','copy'):
 path=project/'restart/execution-v1/evaluation-frozen-v1/final'/f'{suite}.jsonl'
 fd=os.open(path,os.O_RDONLY);os.close(fd)
 checks.append('read permission only verified: '+suite)
for path in [project/'restart/corpus-audit-v1/audit.sqlite',project/'restart/execution-v1/fit_unigram.py']:
 try:fd=os.open(path,os.O_RDONLY)
 except PermissionError:checks.append('source read denied: '+str(path))
 else:os.close(fd);raise RuntimeError('Source content access allowed')
s=socket.socket()
try:s.bind(('127.0.0.1',0))
except PermissionError:checks.append('network denied')
else:raise RuntimeError('network allowed')
finally:s.close()
(output/'allowed-output.txt').write_text('isolated result fixture\n')
print(json.dumps({'status':'PASS','checks':checks,'holdout_content_read':False,'model_loaded':False}))
