import sys,pathlib,contextlib,io,json,tempfile,random,hashlib,subprocess,signal
HERE=pathlib.Path(__file__).resolve().parent
PREP=HERE.parent/'enwiki-retained-prefix-terminal-verifier-preparation-v1'
sys.path.insert(0,str(PREP))
with contextlib.redirect_stdout(io.StringIO()) as log:import checks as c
results=[]
for seed in range(100):
 r=random.Random(seed);n=r.randint(1,80);p=c.core.RevisionProof(n,1000);rows=[]
 for page in range(1,n+1):
  count=r.randint(0,8);ids=[r.randint(1,60) for _ in range(count)];p.page(page,count,ids[0] if ids else None)
  rows.extend((rid,page,i+1) for i,rid in enumerate(ids))
 p.seal()
 for row in sorted(rows):p.revision(*row)
 assert p.finish()['observed']==len(rows)
results.append('100 randomized independent occurrence-set cases including empty pages and repeated revision IDs')
mutations={
'page_identity':lambda d,i,r,b,p:d.execute('update pages set page_id=99 where row_ordinal=1'),
'raw_sha_length':lambda d,i,r,b,p:d.execute("update pages set raw_SHA256=x'01' where row_ordinal=1"),
'unknown_model':lambda d,i,r,b,p:d.execute('update pages set model_code=128 where row_ordinal=1'),
'no_revision_flag':lambda d,i,r,b,p:d.execute('update pages set flags=0 where row_ordinal=3'),
'decoded_gap':lambda d,i,r,b,p:r[1].update(decoded_global_start=9999),
'durable_revision_count':lambda d,i,r,b,p:r[1]['durable'].update(durable_revision_occurrences=999),
'receipt_pagecount':lambda d,i,r,b,p:r[0].update(native_pages=99),
'namespace_counter':lambda d,i,r,b,p:p['counts'].update(namespace_counts=[[0,2]]),
'exception_count':lambda d,i,r,b,p:p['exceptions'].update(events=1),
'compressed_receipt':lambda d,i,r,b,p:r[0].update(compressed_bytes=99),
}
for name,fn in mutations.items():
 with tempfile.TemporaryDirectory() as z:
  try:c.stored_fixture(z,fn)
  except Exception:results.append(name+' refused')
  else:raise AssertionError('accepted '+name)
pins=json.loads((PREP/'code-pins.json').read_text())['SHA256'];assert len(pins)==73
for f,h in pins.items():assert hashlib.file_digest(open(f,'rb'),'sha256').hexdigest()==h
ready=json.loads((PREP/'readiness.json').read_text());p=subprocess.run(ready['static_command'],capture_output=True,text=True,timeout=30,check=True)
assert p.stdout.strip()=='STATIC_ONLY_TERMINAL_BINDING_REQUIRED_NO_SQL_OR_NATIVE_READ'
report={'status':'PASS_SYNTHETIC_STATIC_ONLY','baseline_controls':len(c.checks),'independent_random_cases':100,'independent_mutations':10,'pins_verified':len(pins),'static_stdout':p.stdout.strip(),'checks':results,'retained_native_or_index_reads':0}
(HERE/'results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2));signal.setitimer(signal.ITIMER_REAL,0)
