import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from cloud_training import nano_pilot_window as window
from cloud_training.l4_recovery_check import upload_bundle
from cloud_training.nano_conversation_controller_v2 import validate_request
from cloud_training.nano_data import sha256_file
import verify_nano_checkpoint as checkpoint
import verify_nano_conversation_controller as original

class PilotTests(unittest.TestCase):
    def test_window_is_absolute(self):
        start=1800000000
        iso=lambda n:dt.datetime.fromtimestamp(n,dt.timezone.utc).isoformat()
        cfg={'lease_start_utc':iso(start),'provider_stop_utc':iso(start+window.LEASE)}
        end,service=window.qualification_window(cfg,start+1200)
        self.assertEqual(end,start+4800)
        self.assertEqual(service,3630)
        self.assertEqual(window.qualification_window(cfg,start+2400)[0],end)
        with self.assertRaises(ValueError):window.qualification_window(cfg,end-500)

    def test_forecast_rejects_missing_slow_and_nonfinite(self):
        samples=dict(startup=[35],update=[1],checkpoint=[35],evaluation=[4])
        self.assertEqual(window.forecast(samples,1200)['arm_seconds'],1245)
        for key,value in [('startup',[]),('update',[float('nan')]),('checkpoint',[301]),('evaluation',[400])]:
            with self.assertRaises(ValueError):window.forecast(dict(samples,**{key:value}),1200)

    def test_new_approval_and_forecast_binding(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            request,now=original.ControllerTests().fixture(root)
            self.assertTrue(validate_request(request,root,now=now))
            request.update(schema=2,experiment='ganesh-english-controlled-v2',backup_reserve_seconds=window.BACKUP,storage_network_recovery_reserve_usd=8)
            def bind(path,data):
                (root/path).write_text(json.dumps(data))
                request['files'][path]=sha256_file(root/path)
            approval=dict(approved=True,approved_usd=30,machine=request['machine'])
            approval.update({k:request[k] for k in ('instance','experiment','runtime_sha256','lease_start_utc','provider_stop_utc')})
            bind('auth.json',approval)
            samples=dict(startup=[35],update=[1],checkpoint=[35],evaluation=[4])
            bind('measure.json',dict(samples=samples,decode_seconds=1200,instance=request['instance'],runtime_sha256=request['runtime_sha256']))
            ref=request['receipts']['measured_forecast']
            forecast=json.loads((root/ref['path']).read_text())
            forecast.update(window.forecast(samples,1200),timing_evidence='measure.json')
            bind(ref['path'],forecast);ref['sha256']=request['files'][ref['path']]
            self.assertEqual(validate_request(request,root,now=now),[])
            forecast['arm_seconds']-=1
            bind(ref['path'],forecast);ref['sha256']=request['files'][ref['path']]
            self.assertTrue(validate_request(request,root,now=now))

    def test_hanging_descendant_cannot_write_after_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)
            grand="import signal,time,pathlib;signal.signal(signal.SIGTERM,signal.SIG_IGN);pathlib.Path('ready').touch();time.sleep(.6);pathlib.Path('unexpected').touch()"
            child=subprocess.Popen([sys.executable,'-c','import subprocess,time,sys;subprocess.Popen([sys.executable,"-c",sys.argv[1]]);time.sleep(10)',grand],cwd=dest,start_new_session=True)
            try:
                for _ in range(100):
                    if (dest/'ready').exists():break
                    time.sleep(.02)
                self.assertTrue((dest/'ready').exists())
            finally:window.stop_group(child,.1)
            time.sleep(.65)
            self.assertFalse((dest/'unexpected').exists())

    def test_partial_upload_and_slow_copy_preserve_only_local_bundle(self):
        fixture=checkpoint.CheckpointTests();fixture.setUp()
        try:
            fixture.save()
            root=fixture.path.parent
            shim=root/'gcloud'
            shim.write_text('#!'+sys.executable+'\nimport os,shutil,sys,time\nfrom pathlib import Path\nsrc=Path(sys.argv[3]);dst=Path(os.environ["STORE"])/src.name\nif src.name=="metadata.json":\n if os.environ["FAULT"]=="slow":time.sleep(5)\n sys.exit(3)\nshutil.copyfile(src,dst)\n')
            shim.chmod(0o700)
            for mode in ('slow','error'):
                store=root/mode;store.mkdir()
                with patch.dict(os.environ,PATH=str(root)+os.pathsep+os.environ['PATH'],STORE=str(store),FAULT=mode):
                    with self.assertRaises((subprocess.TimeoutExpired,subprocess.CalledProcessError)) as caught:
                        upload_bundle(fixture.path,remote_prefix='gs://local-fixture/test/checkpoints',timeout=2.0)
                self.assertTrue((store/'payload.pt').exists(),str(caught.exception)+str(caught.exception.stderr))
                self.assertFalse((store/'COMMITTED').exists())
                self.assertTrue((fixture.path/'COMMITTED').exists())
        finally:fixture.doCleanups()
