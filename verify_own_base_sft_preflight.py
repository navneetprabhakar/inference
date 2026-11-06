"""Tiny CPU-only preflight tests; no production data, parent or GPU access."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import numpy as np
import torch
from gpt2 import Config,GPT2
from train import optimizer_for
import own_base_sft_preflight as p

torch.set_num_threads(1)
class Guard:
    def check(self):pass

class Data:
    def __init__(self):
        self.rows={};self.values={}
        for split in ('train','validation'):
            rows=[];values=[]
            for source in p.ROLES:
                for i in range(8):
                    n=3+i%4;x=np.array([j%15+1 for j in range(n)]);y=np.array([-100]*(n-2)+[3,4])
                    rows.append(dict(_source=source,doc_id=source+str(i),turn=2 if source==p.ROLES[2] else 0,length=n,target_count=2,split=split,family=source+str(i),offset=0));values.append((x,y))
            self.rows[split]=rows;self.values[split]=values
    def row(self,split,index):return self.values[split][index]

class Checks(unittest.TestCase):
    def setUp(self):
        self.disk=patch.object(p.shutil,'disk_usage',return_value=type('Disk',(),{'free':100*1024**3})());self.disk.start()
    def tearDown(self):self.disk.stop()
    def test_exact_three_source_allocation_and_repetition(self):
        d=Data();plan=p.selection(d)
        self.assertEqual(len(plan['updates']),40);self.assertEqual(len(plan['validation']),48)
        self.assertEqual(Counter(x['phase'] for x in plan['updates']),{'warmup':8,'measured':32})
        self.assertEqual(Counter(x['source'] for x in plan['updates']),dict(zip(p.ROLES,(15,15,10))))
        ext=[i for item in plan['updates'] if item['source']==p.ROLES[2] for i in item['indices']]
        self.assertEqual(len(ext),80);self.assertTrue(all(d.rows['train'][i]['turn']==2 for i in ext))
        self.assertEqual(plan['coverage'][p.ROLES[2]]['unique_evaluation_rows'],8)
        self.assertEqual(plan,p.selection(d))
        bare=deepcopy(plan);digest=bare.pop('sha256');self.assertEqual(digest,p.digest_value(bare))
    def test_no_missing_extension_substitution(self):
        d=Data()
        for split in d.rows:
            for row in d.rows[split]:
                if row['_source']==p.ROLES[2]:row['turn']=1
        with self.assertRaises(ValueError):p.selection(d)
    def test_durable_attempt_before_update_failure(self):
        with TemporaryDirectory() as directory:
            path=Path(directory);ledger=p.Ledger(path,{'fixture':True},Guard());data=Data();item=p.selection(data)['updates'][0]
            work=p.train.work_for(data,item['indices'],1);ledger.reserve_update(work,item,0)
            signed=json.loads((path/'preflight-ledger.json').read_text());digest=signed.pop('sha256')
            self.assertEqual(digest,p.digest_value(signed));self.assertEqual(signed['attempted'],work);self.assertEqual(signed['completed_updates'],0)
            ledger.finish(error=RuntimeError('partial update'));self.assertEqual(ledger.value['attempted'],work);self.assertEqual(ledger.value['state'],'FAILED_INCOMPLETE')
            with self.assertRaises(ValueError):p.Ledger(path,{'fixture':True},Guard())
    def test_incomplete_cannot_pass_and_no_evaluation_refund(self):
        with TemporaryDirectory() as directory:
            ledger=p.Ledger(Path(directory),{},Guard());data=Data();work=p.train.work_for(data,[0],1,'validation');ledger.reserve_evaluation(work,'chat')
            ledger.finish(error=ValueError('failed FP32 forward'));self.assertEqual(ledger.value['attempted']['evaluation_targets'],2);self.assertEqual(ledger.value['completed_evaluation_rows'],0)
        with TemporaryDirectory() as directory:
            ledger=p.Ledger(Path(directory),{},Guard())
            with self.assertRaises(ValueError):ledger.finish()
    def test_actual_tiny_training_validation_and_timing(self):
        torch.manual_seed(11);model=GPT2(Config(vocabulary=19,context=32,width=12,heads=3,depth=1));opt=optimizer_for(model);data=Data();plan=p.selection(data)
        with TemporaryDirectory() as directory:
            ledger=p.Ledger(Path(directory),{},Guard());p.workload(model,opt,data,plan,ledger,'cpu')
            self.assertEqual(ledger.value['state'],'PASS_CHILD_PENDING_WATCHDOG');self.assertEqual(ledger.value['completed_updates'],40);self.assertEqual(ledger.value['completed_evaluation_rows'],48)
            self.assertEqual(ledger.value['attempted']['assistant_targets'],640);self.assertEqual(ledger.value['attempted']['evaluation_targets'],96)
            self.assertEqual(sum(v['assistant_targets'] for v in ledger.value['by_source'].values()),640)
            summary=p.timing_summary(ledger);self.assertTrue(any(x['source']==p.ROLES[2] and x['phase']=='measured' for x in summary));self.assertTrue(all(x['seconds']>=0 for x in summary))
            self.assertEqual(ledger.value['validation']['sources']['primary_tool']['physical_split'],'exposed-development')
            self.assertFalse(list(Path(directory).glob('*.pt')))
    def test_existing_run_refused_before_receipt_io(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();run=root/'runs'/'preflight';run.mkdir(parents=True)
            with patch.object(p.train,'ROOT',root),patch.object(p.train,'pinned_json') as read:
                with self.assertRaises(ValueError):p.validate(dict(run=str(run)),run)
                read.assert_not_called()
    def test_foreground_watchdog_exit_and_hung_child(self):
        def ticket(seconds):return dict(watchdog_pid=os.getpid(),nonce='a'*32,wall_started=time.time(),monotonic_started=time.monotonic(),deadline=time.time()+seconds)
        result=p.watch_owned_child(lambda fd:[sys.executable,'-c','pass'],ticket(3),grace_seconds=.5,kill_margin=.2)
        self.assertEqual(result['returncode'],0);self.assertFalse(result['timed_out'])
        start=time.monotonic()
        result=p.watch_owned_child(lambda fd:[sys.executable,'-c','import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'],ticket(1.5),grace_seconds=.6,kill_margin=.2)
        self.assertTrue(result['timed_out']);self.assertLess(time.monotonic()-start,2.0);self.assertEqual(result['returncode'],-9)
        with self.assertRaises(ProcessLookupError):os.kill(result['child_pid'],0)
    def test_child_pass_then_hang_never_publishes_final_pass(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();(root/'runs').mkdir();run=root/'runs'/'preflight';spec=root/'spec.json';spec.write_text(json.dumps(dict(run=str(run))))
            code="import pathlib,json,time,signal; p=pathlib.Path("+repr(str(run))+");p.mkdir();(p/'hardware-candidate.json').write_text(json.dumps({'state':'PASS','disposable_weights_released':True}));signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)"
            real_watch=p.watch_owned_child
            def short_watch(factory,ticket):
                return real_watch(lambda fd:[sys.executable,'-c',code],ticket,grace_seconds=.6,kill_margin=.2)
            with patch.object(p.train,'ROOT',root),patch.object(p,'CALENDAR',1.5),patch.object(p,'watch_owned_child',side_effect=short_watch):
                result=p.foreground(spec,run)
            self.assertEqual(result['state'],'FAILED_INCOMPLETE');self.assertTrue((run/'hardware-candidate.json').exists());self.assertFalse((run/'hardware-receipt.json').exists())
            self.assertTrue(json.loads((run/'watchdog.json').read_text())['timed_out'])
    def test_active_limit_precedes_longer_calendar_for_hung_child(self):
        with TemporaryDirectory() as directory:
            root=Path(directory).resolve();(root/'runs').mkdir();run=root/'runs'/'preflight';spec=root/'spec.json';spec.write_text(json.dumps(dict(run=str(run))))
            real_watch=p.watch_owned_child
            code='import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)'
            def short_watch(factory,ticket):
                self.assertAlmostEqual(ticket['deadline']-ticket['wall_started'],1.2,places=5)
                return real_watch(lambda fd:[sys.executable,'-c',code],ticket,grace_seconds=.5,kill_margin=.2)
            started=time.monotonic()
            with patch.object(p.train,'ROOT',root),patch.object(p,'ACTIVE',1.2),patch.object(p,'CALENDAR',5),patch.object(p,'watch_owned_child',side_effect=short_watch):
                result=p.foreground(spec,run)
            self.assertEqual(result['state'],'FAILED_INCOMPLETE');self.assertTrue(result['watchdog']['timed_out'])
            self.assertLess(time.monotonic()-started,1.8);self.assertFalse((run/'hardware-receipt.json').exists())
            with self.assertRaises(ProcessLookupError):os.kill(result['watchdog']['child_pid'],0)
    def test_internal_worker_ticket_cannot_be_omitted(self):
        with self.assertRaises(ValueError):p.consume_ticket(0)
    def test_fixed_caps_and_time_stop(self):
        with TemporaryDirectory() as directory:
            ledger=p.Ledger(Path(directory),{},Guard());ledger.started-=1201
            with self.assertRaises(p.CampaignStop):ledger.check()
        with TemporaryDirectory() as directory:
            ledger=p.Ledger(Path(directory),{},Guard());work={k:0 for k in p.WORK};work.update(assistant_targets=p.LIMITS['assistant_targets']+1,input_tokens=1,padded_tokens=1,attention_cells=1)
            with self.assertRaises(p.CampaignStop):ledger.reserve_update(work,dict(source='chat',phase='warmup',stratum='fixture',indices=[0]*8),0)
            self.assertEqual(ledger.value['attempted_updates'],0)

if __name__=='__main__':
    os.nice(10);unittest.main(verbosity=2)
