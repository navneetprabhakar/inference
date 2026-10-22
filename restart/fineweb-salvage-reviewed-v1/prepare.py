import csv,json,sqlite3,pathlib,hashlib
p=pathlib.Path(__file__).resolve().parent;assert not (p/'sample.json').exists()
c=sqlite3.connect(f'file:{p.parent}/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
previous=json.load(open(p.parent/'fineweb-salvage-v1/sample.json'));reserved={x['family_id'] for x in previous}
keep=[]
for r in csv.DictReader(open(p.parent/'fineweb-salvage-v1/candidate-manifest.csv')):
 fs=json.loads(c.execute('select families from docs where id=?',(r['audit_id'],)).fetchone()[0]);host=next((f[5:] for f in fs if f.startswith('host:')),'')
 if host.endswith(('.edu','.gov','.ac.uk','.gov.uk')) and r['family_id'] not in reserved and r['split']=='train':keep.append(r)
keep.sort(key=lambda x:hashlib.sha256(('fineweb-complete-institutional-review-v1:'+x['audit_id']).encode()).hexdigest())
s=[dict(r,review_index=i+1) for i,r in enumerate(keep)];(p/'sample.json').write_text(json.dumps(s,indent=2)+'\n')
policy={'scope':'Census of all remaining training records in conservative short-prose slice with .edu/.gov/.ac.uk/.gov.uk host; all previous validation sample families reserved. Host is a retrieval scope only, never evidence of semantic correctness.','selected_documents':len(s),'review_requirement':'Read every selected text in full. Admit only pass label, exclude minor/fail/major conservatively. No sample extrapolation.','additional_recovery':'Previously reviewed FineWeb pass-without-issue records may be admitted individually, regardless of source-wide rejection; they are tuning/reviewed training material, never heldout validation evidence.','splits':'Recovered documents remain in original training split only. FineWeb development/test remain quarantined. TinyStories splits unchanged.','source_filter_sha256':hashlib.sha256((p.parent/'fineweb-salvage-v1/filter.py').read_bytes()).hexdigest(),'no_training':True}
(p/'policy.json').write_text(json.dumps(policy,indent=2)+'\n');print({'documents':len(s),'tokens':sum(int(x['content_tokens']) for x in s)})
