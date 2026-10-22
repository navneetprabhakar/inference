from pathlib import Path
import hashlib,sys
p=Path(__file__).resolve().parents[1]/'m2-intake/hansard-fixed30-draw-development-capture-v1/source-2-row-002848.text.utf8';raw=p.read_bytes();s=raw.decode();assert hashlib.sha256(raw).hexdigest()=='8a1ca30a6ba7c31f10360db786f9f5d8f1d3c37350707255b0c31a26f37e718f'
for a in map(int,sys.argv[1:]):
 z=min(a+10000,len(s));assert 0<=a<z;piece=s[a:z];print('VISIBLE UNTRUNCATED CHUNK',a,z,'UTF8',len(s[:a].encode()),len(s[:z].encode()),'SHA',hashlib.sha256(piece.encode()).hexdigest());print(piece);print('END CHUNK',a,z)
