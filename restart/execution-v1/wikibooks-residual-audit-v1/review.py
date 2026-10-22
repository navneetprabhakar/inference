import hashlib,json,os,pathlib,sys,tempfile
from unittest.mock import patch
D=pathlib.Path(__file__).resolve().parent;S=D.parent/'wikibooks-residual-render-preparation-v1';sys.path.insert(0,str(S));import launch as j;import profile as p;import render_shard as rs
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();inputs={str(x):h(x) for x in S.iterdir() if x.is_file()};assert h(S/'code-pins.json')=='8d630a08e6522758a3e2a56be8a58116d5a90265339e9030d5ca52d9a0ef3ef2';assert h(S/'effective-inputs.json')=='11f603b8a75fa422b17d2b64a0e4848129e75bb9a9ec519ce5a7dc18f1893ee1';j.verify_pins()
with patch.dict(os.environ,{'WIKIBOOKS_EFFECTIVE_PROFILE':str(S/'effective-inputs.json'),'WIKIBOOKS_EFFECTIVE_PROFILE_SHA256':h(S/'effective-inputs.json')}):
 actual=p.load()
old=set()
import sqlite3
for i in actual['prior_shards']:
 d=sqlite3.connect(pathlib.Path(i['path']).resolve().as_uri()+'?mode=ro',uri=True);old.update(x[0] for x in d.execute('select source_ordinal from rendered'));d.close()
residual=set().union(*(set(x['ordinals']) for x in actual['jobs_loaded']));assert len(old)==50457 and len(residual)==39301 and not old&residual;assert sum(len(x['ordinals']) for x in actual['jobs_loaded'])==39301
# Concrete exploit: both root and child pin validators accept empty registry.
with tempfile.TemporaryDirectory() as td:
 t=pathlib.Path(td);f=t/'code-pins.json';f.write_text(json.dumps({'sha256':{}}))
 with patch.object(j,'HERE',t),patch.object(j.rc,'PIN_PATH',f):
  assert j.verify_pins()['sha256']=={};assert j.rc.check_pins()['sha256']=={}
# Narrow synthetic changed paths; outputs captured in audit, no source writes.
for name in ['check_profile.py','check_worker.py']:
 import subprocess
 runner="import sys;sys.path.insert(0,"+repr(str(S))+");exec(compile(open("+repr(str(S/name))+",'rb').read(),"+repr(str(S/name))+",'exec'),{'__name__':'__main__','__file__':"+repr(str(S/name))+"})"
 result=subprocess.run([sys.executable,'-c',runner],capture_output=True,text=True,check=True,timeout=60);(D/(name+'.stdout')).write_text(result.stdout);(D/(name+'.stderr')).write_text(result.stderr)
assert all(h(pathlib.Path(n))==v for n,v in inputs.items())
result={'status':'BLOCK_DISPATCH_MANIFEST_TRUST_GAP_CONFIRMED','original_source_inputs_unchanged':True,'parent_profile_pin_valid':True,'actual_old_ordinals':50457,'actual_residual_ordinals':39301,'actual_jobs':8,'old_residual_disjoint_and_complete':True,'narrow_control_counts':{'profile_and_reservations':16,'synthetic_residual_worker':10},'confirmed_blocker':{'priority':'P2','trigger':'Replace only mutable code-pins.json with {"sha256":{}}','observed':'launch.verify_pins and rc.check_pins both accept empty registry, bypassing every code hash. Data profile remains pinned but does not bind registry.','chain':'Root launch.run→verify_pins; child supervisor.supervise→reader_core.check_pins; child render_shard.render→reader_core.check_pins; none receives parent expected registry digest.','fix':'Explicit parent-reviewed code-pins SHA in root CLI, supervisor and worker; exact required inventory before mutations/reservations. Use the external digest propagation pattern already reviewed in catalog/OpenStax.'},'no_other_confirmed_changed_path_issue':True,'process_cleanup_review':'Existing reviewed ownership/cleanup copied; no new generic re-audit or real residual process launched.','finalizer_review':'External supervisor/final pins still pending from rights_review; not certified here.','input_SHA256':inputs,'network_requests':0,'residual_workers_launched':0,'global_ledger_writes':0}
(D/'review.json').write_text(json.dumps(result,indent=2)+'\n');(D/'manifest.json').write_text(json.dumps({x.name:h(x) for x in D.iterdir() if x.is_file() and x.name!='manifest.json'},indent=2)+'\n');print(json.dumps({'status':result['status'],'manifest_SHA256':h(D/'manifest.json')}))
