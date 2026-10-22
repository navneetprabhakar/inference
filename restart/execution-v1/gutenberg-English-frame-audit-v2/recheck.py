import pathlib,hashlib,json,runpy,sys
P=pathlib.Path(__file__).resolve().parent;D=P.parent/'gutenberg-English-frame-preparation-v2';expected={'ready.json':'31b29334c591f4ec7771a5584056220713224018e5349a4f1cb48343d94bacc9','manifest.json':'03acf1b9c14a58cea5b4d4420d6d2b9894e43a7744ec7c0da2aa725db7f14204','profile.json':'3e88f52e825afbb41c0a5b6ed29b1923ef37cdc62eebfb2a0f31924ede3f503b','frame.py':'3ef497af7fae7f30f08a877412890c07c4664d036322ff2dfad03756b1b2e8a8'}
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,d in expected.items():assert h(D/name)==d
before={str(p):h(p) for p in D.iterdir() if p.is_file()};old=pathlib.Path.write_text
checks=D/'checks.json'
def write(self,*args,**kwargs):return old(P/'reproduced-checks.json' if self.resolve()==checks.resolve() else self,*args,**kwargs)
pathlib.Path.write_text=write;sys.path.insert(0,str(D));runpy.run_path(str(D/'check.py'),run_name='__main__');pathlib.Path.write_text=old
assert all(h(pathlib.Path(n))==d for n,d in before.items());(P/'preparation-unchanged.json').write_text(json.dumps({'all_preparation_files_unchanged':True,'files_SHA256':before},indent=2)+'\n')
