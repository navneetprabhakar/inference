import copy,hashlib,json,tempfile,sqlite3
from pathlib import Path
import overlay
N=0
def ok(f):
 global N;f();N+=1
def refuses(f):
 global N
 try:f()
 except (ValueError,KeyError):N+=1;return
 raise AssertionError('expected refusal')
def h(n):return hashlib.sha256(str(n).encode()).digest()
rows=[(1,1,h(11),h(1),10,64,1,0),(1,2,h(12),h(2),20,0,0,1),(2,1,h(13),h(1),10,0,0,0),(2,2,h(14),h(3),30,0,0,1)]
reviews=[{'source_id':1,'ordinal':2,'text_SHA256':h(2).hex(),'text_UTF8_bytes':20,'semantic_hold':True,'verdict':'HOLD'}]
expected={'raw_rows':4,'distinct_textSHA':3,'prior_held_distinct_textSHA':1}
m=[(h(1),10,3,1,2,1,64,h(21),2),(h(2),20,5,1,1,0,0,h(21),2),(h(3),30,7,0,1,0,0,h(23),4)]
def run(rr=rows,rv=reviews,ex=expected,mm=m):
 out=[];result=overlay.aggregate(rr,rv,out.append,lambda:None,ex,mm);return result,out
r,o=run()
ok(lambda:overlay.require(r['union_held_distinct_textSHA']==2,'union'))
ok(lambda:overlay.require(r['raw_occurrences_union_exact_text_holds']==3,'all_copies'))
ok(lambda:overlay.require(r['not_exact_known_held_distinct_textSHA_NOT_usable']==1,'uncleared'))
ok(lambda:overlay.require(o[0]['prior_identity_hold_bits'] or o[1]['prior_identity_hold_bits'],'oldbits'))
ok(lambda:overlay.require(r['existing_M1_token_diagnostics']['language_pass_after_all_exact_known_holds_NOT_usable']['M1_content_tokens']==0 if 'language_pass_after_all_exact_known_holds_NOT_usable' in r['existing_M1_token_diagnostics'] else True,'noqualifying'))
refuses(lambda:run(rows[::-1]))
refuses(lambda:run(rows[:-1]))
refuses(lambda:run(rows+[rows[-1]]))
bad=copy.deepcopy(rows);bad[2]=(*bad[2][:4],11,*bad[2][5:]);refuses(lambda:run(bad))
bad=copy.deepcopy(reviews);bad[0]['text_SHA256']=h(9).hex();refuses(lambda:run(rv=bad))
refuses(lambda:run(mm=m[:-1]))
refuses(lambda:run(mm=m+[m[-1]]))
bad=copy.deepcopy(m);bad[0]=(*bad[0][:4],3,*bad[0][5:]);refuses(lambda:run(mm=bad))
# A PASS proxy cannot clear pre-existing exact-content holds.
rv=[{'source_id':1,'ordinal':1,'text_SHA256':h(1).hex(),'text_UTF8_bytes':10,'semantic_hold':False,'verdict':'PASS_RESEARCH_QUALITY_PROXY'}]
ok(lambda:overlay.require(run(rv=rv)[0]['union_held_distinct_textSHA']==1,'PASS_not_clearance'))
# Complete30 contract and status-gated review construction.
u={'status':'COMPLETE_20_WHOLE_UNIFORM_DEVELOPMENT_UNITS_READ','reviews':[]};b={'status':'COMPLETE_FINITE_TEN_UNIT_TEAM_WHOLE_REVIEW_NO_ADMISSION','units':[]}
for i in range(30):
 row={'source_id':1,'ordinal':i+1,'text_SHA256':h(i).hex(),'UTF8_bytes':1,'text_UTF8_bytes':1,'whole_text_read':True,'whole_review_completed_by_team':True,'development_verdict':'READABLE_COHERENT_PROSE_RESEARCH_PROXY','verdict':'PASS_RESEARCH_QUALITY_PROXY','uniform_draw':i+1,'byte_weighted_draws':[{'draw':i-19}]}
 (u['reviews'] if i<20 else b['units']).append(row)
ok(lambda:overlay.require(len(overlay.build_reviews(u,b))==30,'30roles'))
bad=copy.deepcopy(u);bad['status']='IN_PROGRESS';refuses(lambda:overlay.build_reviews(bad,b))
bad=copy.deepcopy(b);bad['units'][0]['whole_review_completed_by_team']=False;refuses(lambda:overlay.build_reviews(u,bad))
bad=copy.deepcopy(u);bad['reviews'][0]['tool_output_truncated']=True;refuses(lambda:overlay.build_reviews(bad,b))
bad=copy.deepcopy(u);bad['reviews'][0]['development_verdict']='maybe';refuses(lambda:overlay.build_reviews(bad,b))
bad=copy.deepcopy(b);bad['units'][0]['text_SHA256']=u['reviews'][0]['text_SHA256'];refuses(lambda:overlay.build_reviews(u,bad))
# Different raw texts with same lossy normalized hash remain distinct; report min/max without representative.
mm=[(v[0],v[1],v[2],1,*v[4:7],h(21),2) for v in m]
rn,on=run(rv=[],mm=mm)
g=rn['existing_M1_token_diagnostics']['normalized_exact_candidate_equivalence_NOT_selected']
ok(lambda:overlay.require(g['groups_with_multiple_raw_textSHA']==1 and g['raw_textSHA_excess']==1 and g['ambiguous_token_count_groups']==1 and g['hypothetical_one_per_group_content_tokens_min']==5 and g['hypothetical_one_per_group_content_tokens_max']==7,'normalized_diagnostics_not_selection'))
print(json.dumps({'status':'PASS_SYNTHETIC_ONLY','controls':N,'source_SQLite_or_body_reads':0}))
# Actual production SQLite read-only join + exact all-copy semantics on synthetic30+alias.
with tempfile.TemporaryDirectory() as tmp:
 d=Path(tmp);fp=d/'family.sqlite';tp=d/'tokens.sqlite';out=d/'out';out.mkdir()
 f=sqlite3.connect(fp);f.execute('CREATE TABLE rows(source_id INTEGER,ordinal INTEGER,line_SHA256 BLOB,text_SHA256 BLOB,text_UTF8_bytes INTEGER,existing_flags INTEGER,identity_holds INTEGER,lead_status INTEGER)')
 t=sqlite3.connect(tp);t.execute('CREATE TABLE docs(doc INTEGER,source INTEGER,source_ordinal INTEGER,text_SHA256 BLOB,line_SHA256 BLOB,UTF8_bytes INTEGER,source_flags INTEGER,explicit_hold_flags INTEGER)');t.execute('CREATE TABLE texts(text_SHA256 BLOB,UTF8_bytes INTEGER,content_tokens INTEGER,language_pass INTEGER,occurrences INTEGER,explicit_hold_flags INTEGER,source_flags INTEGER,normalized_SHA256 BLOB,normalized_words INTEGER)')
 uu=copy.deepcopy(u);bb=copy.deepcopy(b);uu['reviews'][0]['development_verdict']='HOLD_DEPENDENCY'
 for i in range(30):
  old=int(i<13);f.execute('INSERT INTO rows VALUES(?,?,?,?,?,?,?,?)',(1,i+1,h(100+i),h(i),1,0,old,1));t.execute('INSERT INTO docs VALUES(?,?,?,?,?,?,?,?)',(i+1,1,i+1,h(i),h(100+i),1,0,old));t.execute('INSERT INTO texts VALUES(?,?,?,?,?,?,?,?,?)',(h(i),1,i+2,1,2 if i==0 else 1,old,0,h(500+i),1))
 f.execute('INSERT INTO rows VALUES(?,?,?,?,?,?,?,?)',(2,1,h(200),h(0),1,0,0,1));t.execute('INSERT INTO docs VALUES(?,?,?,?,?,?,?,?)',(31,2,1,h(0),h(200),1,0,0));f.commit();t.commit();f.close();t.close()
 for name,value in [('u.json',uu),('b.json',bb)]:(d/name).write_text(json.dumps(value))
 def binding(p):
  s=p.stat();return {'path':str(p),'stat':[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]}
 profile={'family_frame':binding(fp),'token_frame':binding(tp),'uniform_review':str(d/'u.json'),'byte_review':str(d/'b.json'),'expected':{'raw_rows':31,'distinct_textSHA':30,'prior_held_distinct_textSHA':13},'limits':{'overlay_bytes':1000000}}
 result=overlay.run(profile,out,lambda extra=0:None)
 assert result['raw_rows']==31 and result['raw_occurrences_new_semantic_holds']==2 and result['new_semantic_hold_distinct_textSHA']==1 and result['union_held_distinct_textSHA']==13
 N+=1
 print(json.dumps({'status':'PASS_ACTUAL_PRODUCTION_SQLITE_SYNTHETIC','total_core_controls':N,'no_retained_source_reads':True}))
