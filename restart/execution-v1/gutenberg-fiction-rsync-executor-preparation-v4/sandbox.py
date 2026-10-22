"""Reuses reviewed macOS write-confinement rule, with one loopback destination."""
import json
from pathlib import Path
def policy(stage,filelist,port):
 stage=str(Path(stage).resolve(strict=True));filelist=str(Path(filelist).resolve(strict=True))
 if stage=='/' or not 1<=port<=65535:raise ValueError('sandbox_scope')
 roots=['/usr','/System','/Library/Apple',stage,filelist]
 exclusions=' '.join('(require-not (subpath '+json.dumps(p)+'))' for p in roots)
 return '\n'.join(['(version 1)','(allow default)','(deny network*)','(allow network-outbound (remote ip "localhost:'+str(port)+'"))','(deny file-read-data (require-all '+exclusions+'))','(allow file-read-data (literal "/") (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))','(deny file-write* (require-not (subpath '+json.dumps(stage)+')))','(allow file-write-data (literal "/dev/null"))'])+'\n'
def command(argv,stage,filelist,port):
 p=Path(filelist).parent/'native.sb';raw=policy(stage,filelist,port).encode()
 with p.open('xb') as f:f.write(raw)
 return ['/usr/bin/sandbox-exec','-f',str(p),*argv]
