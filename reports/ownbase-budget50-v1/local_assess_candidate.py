"""Complete MPS assessment in whole-session chunks, then protected tool regression."""
import argparse,datetime,hashlib,json,os,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('name',choices=['new-base-2k-8epochs','retained605-2k-4epochs']);a=p.parse_args()
repo=Path('.').resolve();reports=repo/'reports/ownbase-budget50-v1';runtime=repo/'runs/ownbase-budget50-v1';checkpoint=runtime/'local-candidates'/a.name
receipt=json.loads((runtime/'local-candidates'/(a.name+'-download.json')).read_text());assert receipt['local_bundle_verified']
sha=lambda path:hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
assert sha(checkpoint/'manifest.json')==receipt['manifest_sha256']
suite_path=reports/'assessment.json';suite=json.loads(suite_path.read_text());assert sha(suite_path)=='d7acf5e46deab0fe2644489557a4743522c5dec65035931d39472b11bd0f3c48'
root=runtime/'local-evaluations'/a.name;root.mkdir(parents=True,exist_ok=False)
parts=[];records=[];env=dict(os.environ,PYTHONPATH=str(repo));status=root/'progress.json'
def publish(phase,**kw):status.write_text(json.dumps({'phase':phase,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'name':a.name,'completed_turns':len(records),'parts':parts,**kw},indent=2)+'\n')
for i,start in enumerate(range(0,len(suite['sessions']),10)):
 subset=dict(suite,sessions=suite['sessions'][start:start+10],parent_frozen_suite_sha256=sha(suite_path),partition_session_range=[start,min(start+10,len(suite['sessions']))]);subpath=root/f'suite-{i:02d}.json';subpath.write_text(json.dumps(subset,indent=2)+'\n');output=root/f'assessment-{i:02d}.json'
 publish('assessing',partition=i)
 args=[sys.executable,str(reports/'assess_model.py'),'--checkpoint',str(checkpoint),'--tokenizer',str(repo/'runs/ownbase-v2-data/tokenizer'),'--repo',str(repo/'runs/nanochat-source'),'--suite',str(subpath),'--output',str(output),'--device','mps','--seconds','1800']
 with (root/f'assessment-{i:02d}.log').open('w') as log:rc=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=1860).returncode
 report=json.loads(output.read_text());parts.append({'file':str(output.relative_to(repo)),'sha256':sha(output),'suite_sha256':sha(subpath),'status':report['status'],'exit_code':rc})
 if rc or report['status']!='complete_requires_full_review':publish('incomplete_requires_recovery');raise RuntimeError('Incomplete local assessment; preserve raw evidence and recover explicitly')
 assert report['checkpoint_manifest_sha256']==receipt['manifest_sha256'];records+=report['records']
expected=[(s['id'],i) for s in suite['sessions'] for i,_ in enumerate(s['turns'])];assert [(r['session'],r['turn']) for r in records]==expected
merged={'status':'complete_requires_full_review','name':a.name,'checkpoint_manifest_sha256':receipt['manifest_sha256'],'parent_frozen_suite_sha256':sha(suite_path),'device':'mps','repetition_penalty':1.0,'reply_budget':192,'parts':parts,'records':records,'scope':'Whole-session partitions preserve all frozen prompts, policies and within-session histories; no automatic semantic acceptance.','usable_model_claim':False}
mergedpath=runtime/(a.name+'-local-assessment.json');assert not mergedpath.exists();mergedpath.write_text(json.dumps(merged,indent=2)+'\n')
publish('protected_tool_regression')
protected=root/'protected.json';args=[sys.executable,'-m','cloud_training.nano_quality','--repo',str(repo/'runs/nanochat-source'),'--checkpoint',str(checkpoint),'--checkpoint-manifest-sha256',receipt['manifest_sha256'],'--tokenizer',str(repo/'runs/ownbase-v2-data/tokenizer'),'--tokenizer-sha256','ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5','--suite',str(reports/'protected-tools.json'),'--output',str(protected),'--device','mps','--seconds','600','--reply-budget','128']
with (root/'protected.log').open('w') as log:rc=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=660).returncode
protected_rc=rc
retention_rc=None
if protected_rc==0:
 retention_suite=reports/'historical-retention.json';assert sha(retention_suite)=='c8ae7d38f0ce2a84cd3b7437eb818c6b881b2fca6111540e556162cd3442b16f'
 publish('historical_retention')
 args[args.index('--suite')+1]=str(retention_suite);args[args.index('--output')+1]=str(root/'historical-retention.json')
 with (root/'historical-retention.log').open('w') as log:retention_rc=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=660).returncode
 rc=retention_rc
publish('complete_pending_full_root_review' if rc==0 else 'retention_or_protected_incomplete',merged_file=str(mergedpath.relative_to(repo)),merged_sha256=sha(mergedpath),protected_exit_code=protected_rc,historical_retention_exit_code=retention_rc,automatically_promoted=False)
print(status.read_text());sys.exit(rc)
