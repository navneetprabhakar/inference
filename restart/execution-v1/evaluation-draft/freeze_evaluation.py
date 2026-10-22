"""Publish a hash-bound evaluation snapshot and test final-file custody; no model."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
from slm.restart.custody import profile,runtime_roots,command
O=Path(__file__).resolve().parent;R=O.parents[2];DEST=O.parent/'evaluation-frozen-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    if DEST.exists():raise FileExistsError('Never overwrite an evaluation freeze')
    audit=json.loads((O/'combined-audit.json').read_text());assert audit['status']=='SCOPED_COMBINED_AUDIT_PASS'
    for rel,digest in audit['files_sha256'].items():assert sha(O/rel)==digest
    for rel,digest in audit['evidence_sha256'].items():assert sha(O/rel)==digest
    assert sha(R/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv')==audit['source_manifest_sha256']
    DEST.mkdir();(DEST/'development').mkdir();(DEST/'final').mkdir();(DEST/'custody-output').mkdir()
    files={};source_map={}
    for rel,digest in audit['files_sha256'].items():
        src=O/rel;split='development' if src.name.startswith('development') else 'final'
        suite=next(x for x in ['grammar','grounded','narrative','copy'] if x in src.name)
        target=DEST/split/(suite+'.jsonl');shutil.copyfile(src,target);assert sha(target)==digest;target.chmod(0o444)
        files[str(target.relative_to(DEST))]=digest;source_map[str(target.relative_to(DEST))]=str(src)
    rows=[json.loads(x) for x in (DEST/'development/narrative.jsonl').read_text().splitlines()]
    smoke=[r['id'] for r in sorted(rows,key=lambda r:hashlib.sha256(('fixed-smoke-v1:'+r['id']).encode()).digest())[:20]]
    # Five instances per frame exist; freeze a broad smoke subset: one per frame.
    byframe={}
    for r in sorted(rows,key=lambda r:hashlib.sha256(('fixed-smoke-v1:'+r['id']).encode()).digest()):byframe.setdefault(r['template_family'],r['id'])
    smoke=list(byframe.values());assert len(smoke)==20
    code={str(p.relative_to(R)):sha(p) for p in [R/'src/slm/restart/choice_scoring.py',R/'src/slm/restart/research_gates.py',R/'src/slm/restart/generation_metrics.py']}
    receipt=dict(status='HASH_BOUND_SNAPSHOT_CUSTODY_TEST_PENDING',files_sha256=files,source_paths=source_map,combined_audit_sha256=sha(O/'combined-audit.json'),source_manifest_sha256=audit['source_manifest_sha256'],scoring_code_sha256=code,development_smoke_ids=smoke,smoke_policy='One deterministic hash-selected narrative instance per development frame; 20 total; no model outputs used.',limitations=['File permissions are not a security boundary against the owner; hashes must be verified on each launch.','Custody must be applied by the scoped launcher; creating this snapshot does not enable a trainer.','Source-family and lexical evidence remains bounded as documented in the combined audit.'])
    (DEST/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n')
    denied=[str(DEST/'final'/x) for x in ['grammar.jsonl','grounded.jsonl','narrative.jsonl','copy.jsonl']]
    denied += [str(O/rel) for rel in audit['files_sha256'] if Path(rel).name.startswith('final')]
    denied += [str(R/'restart/corpus-audit-v1/audit.sqlite'),str(O/'build_authored_narratives.py')]
    out=DEST/'custody-output';link=out/'final-link';link.symlink_to(DEST/'final/narrative.jsonl');denied.append(str(link))
    policy=DEST/'training-custody-test.sb';policy.write_text(profile(read_roots=runtime_roots(R)+[DEST/'development'],write_root=out))
    worker='''
import json,pathlib,sys
readable=pathlib.Path(sys.argv[1]);denied=json.loads(sys.argv[2])
assert readable.read_text()
results={}
for p in denied:
 try:
  with open(p,'rb') as f:f.read(1)
 except PermissionError:results[p]='denied'
 else:raise AssertionError('Final/source path readable: '+p)
print(json.dumps(results))
'''
    env=dict(PATH='/usr/bin:/bin',PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(R/'src'),TMPDIR=str(out))
    run=subprocess.run(command(policy,[sys.executable,'-c',worker,str(DEST/'development/narrative.jsonl'),json.dumps(denied)]),cwd=out,env=env,capture_output=True,text=True,timeout=30)
    assert run.returncode==0,run.stderr
    checks=json.loads(run.stdout);assert len(checks)==len(denied) and set(checks.values())=={'denied'}
    for rel,digest in files.items():assert sha(DEST/rel)==digest
    result=dict(status='ACTUAL_PATH_CUSTODY_PASS',denied_paths=checks,development_read='passed',profile_sha256=sha(policy),custody_code_sha256=sha(R/'src/slm/restart/custody.py'),model_initialized=False,training_started=False)
    (DEST/'custody-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    receipt['status']='HASH_BOUND_SNAPSHOT_ACTUAL_PATH_CUSTODY_TESTED';receipt['custody_verification_sha256']=sha(DEST/'custody-verification.json')
    (DEST/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n');(DEST/'manifest.json').chmod(0o444)
    print(json.dumps({'status':receipt['status'],'files':len(files),'denied_paths':len(checks),'smoke_cases':len(smoke),'manifest_sha256':sha(DEST/'manifest.json'),'launcher_integrated':False},indent=2))
if __name__=='__main__':main()
