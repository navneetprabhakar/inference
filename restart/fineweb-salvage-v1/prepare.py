import csv,json,sqlite3,pathlib,hashlib,collections
from filter import reasons,RULES
p=pathlib.Path(__file__).resolve().parent
assert not (p/'sample.json').exists(),'Freeze sample: use a new directory for a new policy.'
old=p.parent/'corpus-audit-v1/accepted-manifest.csv'
assert hashlib.sha256(old.read_bytes()).hexdigest()=='0f368e5a98a74f2f40e2f986e48b3021935b4995bc323546ac466c283f90c51e'
rs=[x for x in csv.DictReader(old.open()) if x['source']=='FineWeb']
previous=json.load(open(p.parent/'semantic-review-v1/sample.json'))
oldfamilies={x['family_id'] for x in previous if x['source']=='FineWeb'}
c=sqlite3.connect(f'file:{p.parent}/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
keep=[];drop=[];stats=collections.Counter()
for r in rs:
 t=c.execute('select text from docs where id=?',(r['audit_id'],)).fetchone()[0]
 why=reasons(t,int(r['content_tokens']))
 if r['family_id'] in oldfamilies:why.append('previous_review_sample_family_reserved')
 if why:drop.append(dict(r,reasons=json.dumps(why)));stats.update(why)
 else:keep.append(r)
for name,rows in [('candidate-manifest.csv',keep),('filter-exclusions.csv',drop)]:
 with (p/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
s=[r for r in keep if r['split']=='train'];s.sort(key=lambda x:hashlib.sha256(('fineweb-salvage-v1-fresh-20261021:'+x['audit_id']).encode()).hexdigest());s=[dict(r,review_index=i+1) for i,r in enumerate(s[:200])];assert len(s)==200
(p/'sample.json').write_text(json.dumps(s,indent=2)+'\n')
policy={'scope':'Conservative short standalone prose salvage from prior mechanically accepted FineWeb only. No text rewriting. Does not attempt to salvage all good long/list/medical/commercial documents.','rules':RULES,'length_tokens':[120,480],'paragraphs':[2,12],'minimum_words_each_paragraph':8,'require_terminal_sentence_punctuation_each_paragraph':True,'source_input_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'filter_code_sha256':hashlib.sha256((p/'filter.py').read_bytes()).hexdigest(),'previous_sample_families_reserved':len(oldfamilies),'sampling':'Fresh deterministic pseudorandom document sample of 200 train records after freezing filters; exclude every prior FineWeb sample family from salvage pool. Equal selection opportunity per eligible train document; not token-weighted.','seed':'fineweb-salvage-v1-fresh-20261021:','gate':{'usable_minimum':190,'major_maximum':4,'denominator':200},'early_rejection':'Reject once >10 total failures or >4 major failures. Never early accept. No tuning on validation sample without new holdout.','failure_action':'Reject source slice, retain only individually reviewed passing records as explicitly limited salvage; report separately.','pass_action':'Admit slice excluding observed failed families. Report sample uncertainty and exact manifest counts, not certified population quality.','training_approved':False}
(p/'policy.json').write_text(json.dumps(policy,indent=2)+'\n')
summary={'before_documents':len(rs),'before_tokens':sum(int(r['content_tokens']) for r in rs),'candidate_documents':len(keep),'candidate_tokens':sum(int(r['content_tokens']) for r in keep),'overlapping_rule_hits':stats,'sample_tokens':sum(int(r['content_tokens']) for r in s),'splits':dict(collections.Counter(r['split'] for r in keep))};(p/'filter-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
