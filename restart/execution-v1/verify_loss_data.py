"""Independent full index/byte/encoding checks for the materialized M1 streams."""
import csv,hashlib,json,pathlib,sqlite3
import numpy as np
from slm.common.tokenizer import BPE
O=pathlib.Path(__file__).resolve().parent;R=O.parents[1]
source={r['audit_id']:r for r in csv.DictReader((R/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv').open())}
con=sqlite3.connect(f'file:{R}/restart/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
tok=BPE.load(O/'tokenizer-8192');families={};seen=set();results={}
for name,split in [('data-train','train'),('data-dev','development'),('data-final','test')]:
    p=O/name;m=json.loads((p/'manifest.json').read_text());ids=np.memmap(p/'tokens.u16',dtype='<u2',mode='r');cursor=0;count=0;familyset=set();partial=0
    index=[json.loads(line) for line in (p/'index.jsonl').read_text().splitlines()]
    for j,r in enumerate(index):
        original=source[r['audit_id']]
        assert original['split']==split and r['split']==split
        assert r['offset']==cursor and r['targets']>0
        assert r['family_id']==original['family_id']
        assert r['audit_id'] not in seen;seen.add(r['audit_id'])
        text=con.execute('SELECT text FROM docs WHERE id=?',(int(r['audit_id']),)).fetchone()[0]
        assert hashlib.sha256(text.encode()).hexdigest()==r['original_text_sha256']==original['original_text_sha256']
        complete=tok.encode(text)+[1]
        assert r['full_document_targets']==len(complete)
        assert list(ids[cursor:cursor+r['targets']])==complete[:r['targets']]
        assert r['partial']==(r['targets']<len(complete))
        if r['partial']:assert split=='development' and j==len(index)-1;partial+=1
        families.setdefault(r['family_id'],set()).add(split);familyset.add(r['family_id'])
        count+=1;cursor+=r['targets']
    assert cursor==len(ids)==m['targets'] and count==m['documents'] and len(familyset)==m['families']
    if split!='development':assert {r['audit_id'] for r in index}=={i for i,r in source.items() if r['split']==split}
    for f,h in m['files'].items():assert hashlib.sha256((p/f).read_bytes()).hexdigest()==h
    results[name]={'documents':count,'families':len(familyset),'exact_targets':cursor,'partial_documents':partial}
assert all(len(s)==1 for s in families.values())
receipt={'status':'PASS','independently_checked_streams':results,'all_source_hashes_and_token_sequences_match':True,'no_cross_split_family_or_document_overlap':True,'scope':'existing admitted release loss streams; does not replace pending new evaluation leakage screening','final_set_scored':False}
(O/'loss-data-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
