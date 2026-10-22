import csv,hashlib,json,sqlite3,pathlib,collections
p=pathlib.Path(__file__).parent
if (p/'sample.json').exists() or (p/'policy.json').exists():
 raise SystemExit('Frozen sample already exists; use a new review directory for resampling.')
rows=list(csv.DictReader(open(p.parent/'corpus-audit-v1/accepted-manifest.csv')))
sample=[]
for source in ['TinyStories','FineWeb']:
 r=[x for x in rows if x['source']==source and x['split']=='train']
 r.sort(key=lambda x:hashlib.sha256(('semantic-review-v1-20261021:'+x['audit_id']).encode()).hexdigest())
 for i,x in enumerate(r[:200]):sample.append(dict(x,review_index=i+1))
json.dump(sample,open(p/'sample.json','w'),indent=2)
json.dump({'design':'Deterministic hash-ranked simple random sample of 200 training records per source; equal inclusion probability within source. Development and test texts are not inspected. Seed fixed before reading.','seed':'semantic-review-v1-20261021:','criteria':{'readable_complete_english_min':0.95,'major_corruption_or_offtopic_boilerplate_max':0.02},'labels':['pass','minor','fail'],'interpretation':'minor remains readable and usable with imperfections; fail is excluded. Sample compliance is not a population guarantee or factual verification. Only observed failures and defensibly linked families are excluded; no extrapolated counts.'},open(p/'policy.json','w'),indent=2)
print(collections.Counter(x['source'] for x in sample))
print({s:sum(int(x['content_tokens']) for x in sample if x['source']==s) for s in ['TinyStories','FineWeb']})
