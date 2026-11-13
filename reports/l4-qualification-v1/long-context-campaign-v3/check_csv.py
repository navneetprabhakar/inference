"""Check displayed CSV tests, independent writer round trips and a long valid revision."""
import csv,hashlib,io,json,random,re,subprocess,sys
from pathlib import Path
r=Path(sys.argv[1]) if len(sys.argv)>1 else Path('runs/long-context-campaign-v3/cohort-05')
s=next(s for s in map(json.loads,(r/'candidates.jsonl').read_text().splitlines()) if s['id']=='v3-05-csv')
code=re.findall(r'```python\n(.*?)```',s['messages'][15]['content'],re.S)[0];p=r/'reviewed_csv.py';p.write_text(code);subprocess.run([sys.executable,str(p)],check=True)
ns={'__name__':'reviewed'};exec(compile(code,str(p),'exec'),ns);fn=ns['read_catalogue'];rng=random.Random(551);checks=0
for _ in range(200):
 stream=io.StringIO(newline='');writer=csv.writer(stream);header=['book_id','title','revision','extra'];rng.shuffle(header);writer.writerow(header);expected={}
 for _ in range(rng.randrange(20)):
  key=rng.choice(['A','B','C']);title=rng.choice(['','comma,title','line\nbreak','carriage\rreturn','double " quote','plain']);rev=rng.randrange(10);row={'book_id':key,'title':title,'revision':str(rev),'extra':'ignored'};writer.writerow([row[h] for h in header])
  if key not in expected or rev>expected[key][1]:expected[key]=(title,rev)
 assert fn(stream.getvalue())==(expected,[]);checks+=1
text='book_id,title,revision\r\n\r\nA,"line\r\nbreak",bad\r\nB,,bad\r\n'
assert fn(text)==(None,['Row 3: invalid revision','Row 5: invalid revision']);checks+=1
huge='9'*4500;long_probe={}
try:
 result,errors=fn('book_id,title,revision\nA,title,'+huge+'\n')
 long_probe={'passed':result is not None and result['A'][1]==10**4500-1 and errors==[]}
except Exception as ex:long_probe={'passed':False,'exception_type':type(ex).__name__,'message':str(ex)[:180]}
if long_probe['passed']:
 result,errors=fn('book_id,title,revision\nA,title,'+huge+'\nB,title,bad\n')
 assert result is None and errors==['Row 3: invalid revision'];checks+=1
report={'result':'pass' if long_probe['passed'] else 'reject_contract_failure','implementation_sha256':hashlib.sha256(code.encode()).hexdigest(),'displayed_test_process_passed':True,'independent_normal_checks':checks,'long_valid_revision_digits':4500,'long_valid_revision':long_probe}
(r/'csv-code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
