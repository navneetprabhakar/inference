"""Expected-COMPLETE verifier, guarded before any source output or ledger read."""
import hashlib,json,os,re,subprocess
from pathlib import Path
import core,artifacts

def ps_absent(pid):
 r=subprocess.run(['/bin/ps','-p',str(pid),'-o','pid='],capture_output=True,text=True,timeout=1)
 if r.returncode not in [0,1]:raise ValueError('ps_query_failed')
 return not r.stdout.strip()
def gate(profile,path,digest):
 raw=artifacts.readsmall(path,16000);core.require(hashlib.sha256(raw).hexdigest()==digest,'external_parent_binding_SHA')
 binding=json.loads(raw);core.gate(profile,binding,ps_absent);return binding

def run(profile,out,check):
 binding=gate(profile,profile['terminal_binding_path'],profile['terminal_binding_SHA256']);root=Path(profile['source_output']);check()
 terminal={}
 for n in ['result.json','controller.json','inventory.json','ownership.json']:
  raw=artifacts.readsmall(root/n,1600000);core.require(hashlib.sha256(raw).hexdigest()==binding['terminal_SHA256'][n],'parent_bound_terminal_metadata');terminal[n]=json.loads(raw)
 result=terminal['result.json'];control=terminal['controller.json'];inventory=terminal['inventory.json'];ownership=terminal['ownership.json']
 core.require(control['result_SHA256']==binding['terminal_SHA256']['result.json'] and control['inventory_SHA256']==binding['terminal_SHA256']['inventory.json'],'controller_result_inventory_links')
 core.require(result['profile_SHA256']==profile['producer_profile_SHA256'] and result['codepins_SHA256']==profile['producer_codepins_SHA256'],'producer_policy_pins')
 core.require(ownership['controller_PID']==binding['controller_PID'] and ownership['profile_SHA256']==profile['producer_profile_SHA256'] and ownership['codepins_SHA256']==profile['producer_codepins_SHA256'],'ownership_source_identity')
 core.require(control['elapsed_seconds']<=21600 and control['peak_observed_owned_RSS_bytes']<=1000000000,'producer_reported_resource_bounds')
 planned=json.loads(artifacts.readsmall(root/'planned-files.json',1000000));core.require(planned['records']==profile['records'],'saved_planned300_manifest')
 receipts=[];successes={}
 for i,r in enumerate(profile['records']):
  check();p=root/f'attempt-{i:03}';receipt=json.loads(artifacts.readsmall(p/'receipt.json',160000));receipts.append(receipt)
  core.require(artifacts.readsmall(p/'file.declaration',1000)==(r['source_relative_path']+'\0').encode(),'literal_file_declaration')
  if receipt['result']['status']==core.COMPLETE:
   rr=receipt['result'];core.require(rr['file']==f"pg{r['ebook_ID']}.txt",'complete_exact_file')
   successes[f"attempt-{i:03}/raw/{rr['file']}"]={**rr,'ebook_ID':r['ebook_ID']}
 # Finite statuses/counters/processes are checked before scanning source files.
 attempt_result=core.attempts(profile,result,control,ownership,receipts,ps_absent)
 artifact_result=artifacts.verify(root,inventory,successes,check)
 # Independent native stats/outcome schema check; no current file/catalog size equivalence.
 for i,r in enumerate(receipts):
  check();native=r['native_transport'];status=r['result']['status'];rawdir=root/f'attempt-{i:03}/raw';entries=list(rawdir.iterdir())
  def number(label):
   hits=re.findall(r'^'+re.escape(label)+r': ([0-9]+)(?: B)?$',native['stdout'],re.M);core.require(len(hits)==1,'native_stats_schema');return int(hits[0])
  if status==core.COMPLETE:
   eid=profile['records'][i]['ebook_ID'];core.require(native['exit_code']==0 and not native['stderr'] and len(entries)==1 and entries[0].name==f'pg{eid}.txt' and number('Number of files')==1 and number('Number of files transferred')==1 and number('Total transferred file size')==r['result']['bytes']==number('Total file size'),'complete_native_stats')
  elif status=='INDEPENDENT_SOURCE_OVERSIZE_SKIPPED_NO_RETRY':core.require(not entries and native['exit_code']==0 and not native['stderr'] and 'skipping' not in native['stdout'] and number('Number of files')==1 and number('Number of files transferred')==0 and number('Total file size')>2400000 and number('Total transferred file size')==0,'recognized_oversize')
  elif status=='INDEPENDENT_SOURCE_MISSING_NO_RETRY':
   eid=profile['records'][i]['ebook_ID'];wanted=re.escape(f'{eid}/pg{eid}.txt');missing=r"rsync\([0-9]+\): error: '"+wanted+r"': \(l\)stat: No such file or directory";harmless=r'rsync\([0-9]+\): warning: receiver has empty file list: exiting';lines=native['stderr'].splitlines();core.require(not entries and native['exit_code']==23 and any(re.fullmatch(missing,x) for x in lines) and all(re.fullmatch(missing,x) or re.fullmatch(harmless,x) for x in lines),'recognized_missing')
  else:core.require(status=='INDEPENDENT_SOURCE_TIMEOUT_NO_RETRY','recognized_timeout_only')
 ledger=core.ledger(profile,receipts,check)
 for n,h in binding['terminal_SHA256'].items():core.require(hashlib.sha256(artifacts.readsmall(root/n,1600000)).hexdigest()==h,'terminal_input_unchanged')
 core.require(ps_absent(binding['controller_PID']),'controller_still_absent')
 return {'status':'PASS_COMPLETE_FINITE_PG300_RAW_DISCOVERY_TERMINAL_VERIFICATION_NO_ADMISSION','attempt_accounting':attempt_result,'artifact_verification':artifact_result,'ledger_readonly_reconciliation':ledger,'source_trust':'Unencrypted native rsync mirror, localfile hashes and protocol receipts. No TLS/publisher checksum/currentcatalog-version or edition/rights/language/quality clearance.','new_admitted_documents':0,'new_admitted_tokens':0}
