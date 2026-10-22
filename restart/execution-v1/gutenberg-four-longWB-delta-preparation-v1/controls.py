"""Small synthetic identity/hold/matcher/deadline controls; no4source matching."""
import json,pathlib,sqlite3,hashlib,tempfile,types,time,signal
from unittest.mock import patch
import delta
p=json.loads((delta.HERE/'profile.json').read_text());core=delta.load_core(p);checks=[]
def check(name,yes):assert yes,name;checks.append(name)
def refuse(f):
 try:f()
 except (ValueError,TimeoutError):return
 raise AssertionError('refusal_expected')
w=['w'+str(i) for i in range(24)];idx=core.Index([' '.join(w)]);check('self_exact',idx.compare(' '.join(w))[0]['normalized_exact']);check('point8_inclusive',idx.compare(' '.join(w+['x'+str(i) for i in range(5)]))[0]['fivegram_Jaccard_gte_0p8']['jaccard']==.8);check('above_point8_cardinality_rejects','fivegram_Jaccard_gte_0p8' not in idx.compare(' '.join(w+['x'+str(i) for i in range(6)])).get(0,{}))
long=['z'+str(i) for i in range(64)];idx=core.Index([' '.join(long)]);check('entire_source_containment_after_early_bound_prefix',0 in idx.compare(' '.join(['q'+str(i) for i in range(300)]+long)))
obj={'page_id':8,'revision_id':9,'family_id':'family','text':'Complete synthetic English text without modification.','title':'Title','url':'https://en.wikibooks.org/wiki/Title'};data=json.dumps(obj);norm=core.normalized(obj['text']);digest=hashlib.sha256(obj['text'].encode()).hexdigest();role={'page_id':8,'revision_id':9,'family':'family','text_sha256':digest,'prior_holds':['prior'],'active':0,'global_final_holds':['prior','final']};r={'source_ordinal':7,'source_data_UTF8_bytes':len(data.encode()),'source_data_SHA256':hashlib.sha256(data.encode()).hexdigest(),'all_prior_current_role_and_global_holds':role,'source_outer_page_id':8,'source_outer_revision_id':9,'source_family':'family','title':'Title','url':obj['url'],'text_SHA256':digest,'text_UTF8_bytes':len(obj['text'].encode()),'normalized_SHA256':hashlib.sha256(norm.encode()).hexdigest(),'normalized_UTF8_bytes':len(norm.encode()),'normalized_words':len(norm.split())}
db=sqlite3.connect(':memory:');db.execute('create table rendered(source_ordinal integer primary key,page_id,revision_id,family,data)');db.execute('insert into rendered values(7,8,9,?,?)',('family',data));roles=sqlite3.connect(':memory:');roles.execute('create table pages(source_ordinal integer primary key,page_id,revision_id,family,text_sha256,holds,active)');roles.execute('create table final_pages(source_ordinal integer primary key,holds)');roles.execute('insert into pages values(7,8,9,?,?,?,0)',('family',digest,'["prior"]'));roles.execute('insert into final_pages values(7,?)',('["prior","final"]',));actual,held=delta.extract_bound(db,roles,r,core);check('exact_JSON_text_inverse_and_all_holds_active0_retained',actual==norm and held==role)
for field,bad in [('page_id',999),('revision_id',999)]:
 db.execute('update rendered set '+field+'=? where source_ordinal=7',(bad,));refuse(lambda:delta.extract_bound(db,roles,r,core));checks.append('outer_'+field+'_tamper_refused');db.execute('update rendered set '+field+'=? where source_ordinal=7',(8 if field=='page_id' else 9,))
roles.execute('update final_pages set holds=?',('["prior"]',));refuse(lambda:delta.extract_bound(db,roles,r,core));checks.append('globalhold_drop_refused');roles.execute('update final_pages set holds=?',('["prior","final"]',));refuse(lambda:delta.extract_bound(db,roles,dict(r,text_SHA256='0'*64),core));checks.append('text_hash_change_refused');refuse(lambda:delta.extract_bound(db,roles,dict(r,source_ordinal=99),core));checks.append('missing_required_row_refused');db.close();roles.close()
with tempfile.TemporaryDirectory() as td:
 out=pathlib.Path(td)/'out';real=signal.setitimer
 def timer(which,seconds):return real(which,min(.05,seconds) if seconds else 0)
 with patch.object(delta,'OUT',out),patch.object(delta,'verify',side_effect=lambda *a:time.sleep(.5)),patch.object(signal,'setitimer',side_effect=timer):refuse(lambda:delta.main(types.SimpleNamespace(code_pins_sha256='x',profile_sha256='y')))
 check('blocked_preflight_alarm_before_output',not out.exists());out.mkdir();f=out/'keep';f.write_bytes(b'frozen')
 with patch.object(delta,'OUT',out),patch.object(delta,'verify',side_effect=ValueError('pin')):refuse(lambda:delta.main(types.SimpleNamespace(code_pins_sha256='x',profile_sha256='y')))
 check('existing_output_untouched',list(out.iterdir())==[f] and f.read_bytes()==b'frozen');check('timer_restored',signal.getitimer(signal.ITIMER_REAL)[0]==0)
check('profileexact4_880003words_5470414bytes',p['source_ordinal_order']==[59666,26355,54103,76283] and sum(x['normalized_words'] for x in p['source_rows'])==880003 and sum(x['text_UTF8_bytes'] for x in p['source_rows'])==5470414)
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY_NO_REAL4SOURCE_MATCH','count':len(checks),'checks':checks}))
