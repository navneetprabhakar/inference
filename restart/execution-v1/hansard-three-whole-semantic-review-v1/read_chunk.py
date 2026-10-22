from pathlib import Path
import sys,hashlib,json
p=Path('restart/execution-v1/m2-intake/hansard-fixed30-draw-development-capture-v1')/sys.argv[1];b=p.read_bytes();t=b.decode();s=int(sys.argv[2]);e=min(s+10000,len(t));a=len(t[:s].encode());z=len(t[:e].encode());print(json.dumps({'file':p.name,'char_span':[s,e],'UTF8_span':[a,z],'chunk_SHA256':hashlib.sha256(t[s:e].encode()).hexdigest(),'whole_SHA256':hashlib.sha256(b).hexdigest(),'whole_chars':len(t)}));print(t[s:e])
