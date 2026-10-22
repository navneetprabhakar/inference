import json,pathlib,tempfile,hashlib,os,sys
from unittest.mock import patch
import code_guard as g
import launch,supervisor,render_shard,reader_core
checks=[]
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def reject(name,fn):
 try:fn()
 except (ValueError,KeyError):checks.append(name)
 else:raise AssertionError(name)
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)
 for name in g.REQUIRED:(p/name).write_text('fixture '+name)
 def registry(data):
  (p/'code-pins.json').write_text(json.dumps({'sha256':data}));return h(p/'code-pins.json')
 valid={name:h(p/name) for name in g.REQUIRED};pin=registry(valid);g.verify(pin,p);checks.append('exact_externally_bound_registry_accepted')
 reject('missing_external_digest',lambda:g.verify(None,p))
 reject('wrong_external_digest',lambda:g.verify('0'*64,p))
 empty=registry({});reject('empty_registry_even_with_its_own_digest',lambda:g.verify(empty,p))
 partial=dict(valid);partial.pop('render_shard.py');pin=registry(partial);reject('missing_required_worker_inventory',lambda:g.verify(pin,p))
 excess=dict(valid,extra='0'*64);pin=registry(excess);reject('extra_inventory_path',lambda:g.verify(pin,p))
 pin=registry(valid);(p/'render_shard.py').write_text('changed');reject('worker_bytes_changed',lambda:g.verify(pin,p));(p/'render_shard.py').write_text('fixture render_shard.py')
 target=p/'external';target.write_text('fixture render_shard.py');(p/'render_shard.py').unlink();(p/'render_shard.py').symlink_to(target);reject('symlinked_worker',lambda:g.verify(pin,p))
with patch.dict(os.environ,{},clear=True):reject('worker_inherited_registry_digest_required',reader_core.check_pins)
with tempfile.TemporaryDirectory() as td,patch.object(launch,'ROOT',pathlib.Path(td)/'never-created'),patch.object(launch,'verify_pins',side_effect=ValueError('pin')) as v:
 reject('main_checks_code_before_profile_or_output',lambda:launch.run(pathlib.Path('absent'), '0'*64,'0'*64));assert not launch.ROOT.exists()
with patch.object(sys,'argv',['supervisor.py','--archive','x','--output','x','--shard','1','--code-pins-sha256','0'*64]),patch.object(supervisor,'check_pins',side_effect=ValueError('pin')),patch.object(supervisor,'supervise',side_effect=AssertionError('must not reserve')):
 reject('supervisor_guard_before_reservation',supervisor.main)
with patch.object(sys,'argv',['render_shard.py','--archive','x','--output','x','--shard','1','--supervisor-pid','1','--start-monotonic','1','--code-pins-sha256','0'*64]),patch.object(render_shard.rc,'check_pins',side_effect=ValueError('pin')),patch.object(render_shard,'render',side_effect=AssertionError('must not write')):
 reject('worker_guard_before_output',render_shard.main)
for name in ['launch.py','supervisor.py']:
 s=pathlib.Path(__file__).with_name(name).read_text();assert "'--code-pins-sha256',os.environ['WIKIBOOKS_CODE_PINS_SHA256']" in s;checks.append(name+'_explicit_digest_forwarding')
print(json.dumps({'passed':len(checks),'checks':checks},indent=2))
