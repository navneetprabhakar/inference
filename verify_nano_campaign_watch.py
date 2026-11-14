"""Offline durable watcher/CAS/quality decision tests. Never contacts GCP."""
import copy,json,tempfile,time,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
from cloud_training import nano_campaign_watch as W

class Cloud:
    def __init__(self):self.generation=7;self.raw=b'initial';self.writes=[];self.deadline=time.time()+14400
    def snapshot(self,source):return self.generation,self.raw
    def cas(self,path,source,generation):
        if generation!=self.generation:raise ValueError('CAS mismatch')
        self.raw=Path(path).read_bytes();self.generation+=1;self.writes.append(json.loads(self.raw)['command'])

class WatchTests(unittest.TestCase):
    def setUp(self):
        self.config={'run_id':'forge-ownbase-retained','campaign_sha256':'a'*64,'backup_prefix':'gs://forge-ownbase-a100-20261110/campaign/checkpoints','kernel_sha256':'b'*64,'retained':{'control_uri':'gs://forge-ownbase-a100-20261110/campaign/control.json'}}
        self.recipe={'comparison':{'quality_suite_sha256':'c'*64}}
    def watch(self,path,cloud,final=None):return W.Watcher(self.config,self.recipe,'d'*64,[],path,cloud,W.checksum(b'initial'),final)
    def command(self,id='3b-continue'):return {**W.command_base(self.config,5723,id),'action':'continue_base'}
    def test_cas_publish_no_duplicate_on_restart(self):
        with tempfile.TemporaryDirectory() as t:
            cloud=Cloud();watch=self.watch(t,cloud);watch.publish(self.command())
            self.assertEqual(len(cloud.writes),1)
            restored=self.watch(t,cloud);self.assertIn('3b-continue',restored.state['sent'])
            self.assertEqual(restored.state['control_generation'],8)
    def test_unexpected_root_writer_not_overwritten(self):
        with tempfile.TemporaryDirectory() as t:
            cloud=Cloud();watch=self.watch(t,cloud);cloud.raw=b'root changed control';cloud.generation=8
            with self.assertRaisesRegex(ValueError,'Unexpected'):watch.publish(self.command())
            self.assertEqual(cloud.writes,[])
    def test_crash_after_cas_recovers_without_second_write(self):
        with tempfile.TemporaryDirectory() as t:
            cloud=Cloud();watch=self.watch(t,cloud);command=self.command();envelope={'command':command,'sha256':W.checksum(W.canonical(command))}
            cloud.raw=(json.dumps(envelope,sort_keys=True,indent=2)+'\n').encode();cloud.generation=8
            watch.state['pending']={'watch_id':command['watch_id'],'raw_sha256':W.checksum(cloud.raw),'expected_generation':7};watch.save()
            restored=self.watch(t,cloud);restored.publish(command)
            self.assertEqual(cloud.writes,[]);self.assertIn(command['watch_id'],restored.state['sent'])
    def test_state_change_only_audit(self):
        with tempfile.TemporaryDirectory() as t:
            watch=self.watch(t,Cloud());status={'status':'running','step':64}
            watch.tick(status);watch.tick({**status,'updated_utc':'later'})
            self.assertEqual(len((Path(t)/'events.jsonl').read_text().splitlines()),1)
    def test_comparison_requires_gain_no_regression_same_provenance(self):
        base={'scores':{'a':True,'b':False},'suite_sha256':'c','recipe_sha256':'r','source_manifest_sha256':'s','runner_sha256':'x'}
        self.assertFalse(W.comparison(base,base)['continue_base'])
        self.assertTrue(W.comparison(base,{**base,'scores':{'a':True,'b':True}})['continue_base'])
        self.assertFalse(W.comparison(base,{**base,'scores':{'a':False,'b':True}})['continue_base'])
        with self.assertRaises(ValueError):W.comparison(base,{**base,'runner_sha256':'changed'})
    def test_quality_incomplete_or_wrong_dataset_rejected(self):
        with self.assertRaises(ValueError):W.quality_vector({'status':'incomplete_timeout'},self.recipe,'d'*64)
        report={'status':'development_checks_complete','diagnostic_base_mode':False,'suite_sha256':'c'*64,'repetition_penalty':1.0,'step':155,'runner_sha256':'e'*64,'identity':{'source_manifest_sha256':'d'*64,'batch_tokens':32768,'microbatch':8,'horizon_updates':155},'records':[{'session':'one','turn':0,'assessment':{'automated_pass':False,'manual_review_required':False}}],'automated_total':1,'automated_passed':0}
        self.assertEqual(W.quality_vector(report,self.recipe,'d'*64)['scores'],{'one:0':False})
        report['identity']['source_manifest_sha256']='other'
        with self.assertRaises(ValueError):W.quality_vector(report,self.recipe,'d'*64)
    def test_sft_incomplete_blocks_without_quality_or_continuation(self):
        with tempfile.TemporaryDirectory() as t:
            cloud=Cloud();watch=self.watch(t,cloud);watch.state['sent']['3b-sft']='hash'
            status={'status':'awaiting_review','reason':'milestone_quality_review','step':5723,'milestone_tokens':3000000000,'review_stages':[{'command':{'watch_id':'3b-sft'},'sft_assessment':{'finite_dataset_complete':False,'step':40}}]}
            watch.tick(status);self.assertIn('incomplete',watch.state['blocker']);self.assertEqual(cloud.writes,[])
    def test_final_chain_starts_general_bounded_and_serial(self):
        with tempfile.TemporaryDirectory() as t:
            cloud=Cloud();watch=self.watch(t,cloud,{'general':('a'*64,[{'path':'sft/general-admitted-v1/manifest.json','uri':'gs://forge-ownbase-a100-20261110/test/general','sha256':'a'*64,'bytes':1}]),'targeted':('b'*64,[{'path':'sft/targeted-teacher-admitted-v2/manifest.json','uri':'gs://forge-ownbase-a100-20261110/test/targeted','sha256':'b'*64,'bytes':1}])})
            watch.state['final_base']={'path':'/opt/ownbase-nano/results/stage-1/step','sha256':'a'*64}
            status={'status':'awaiting_review','reason':'protected_finish_boundary','step':17000,'review_stages':[]}
            watch.tick(status);self.assertEqual(len(cloud.writes),1)
            c=cloud.writes[0];self.assertEqual(c['watch_id'],'final-general');self.assertEqual(c['seconds'],9000);self.assertIn('524288',c['args'])
            watch.tick(status);self.assertEqual(len(cloud.writes),1)
    def test_finish_insufficient_provider_time_no_command(self):
        with tempfile.TemporaryDirectory() as t:
            cloud=Cloud();cloud.deadline=time.time()+1000;watch=self.watch(t,cloud,{'general':('a'*64,[{'path':'sft/general-admitted-v1/manifest.json','uri':'gs://forge-ownbase-a100-20261110/test/general','sha256':'a'*64,'bytes':1}]),'targeted':('b'*64,[{'path':'sft/targeted-teacher-admitted-v2/manifest.json','uri':'gs://forge-ownbase-a100-20261110/test/targeted','sha256':'b'*64,'bytes':1}])})
            watch.state['final_base']={'path':'/opt/ownbase-nano/results/stage/step','sha256':'a'*64}
            watch.tick({'status':'awaiting_review','reason':'protected_finish_boundary','step':17000,'review_stages':[]})
            self.assertIn('insufficient',watch.state['blocker']);self.assertEqual(cloud.writes,[])
    def test_quality_outer_watchdog_has_cleanup_headroom(self):
        command=W.quality_command(self.config,5723,3,'/opt/ownbase-nano/results/sft/step','a'*64)
        inner=int(command['args'][command['args'].index('--seconds')+1])
        self.assertEqual(inner,120);self.assertGreaterEqual(command['seconds']-inner,30)
    def test_complete_three_b_chain_serial_commands_and_baseline(self):
        with tempfile.TemporaryDirectory() as t:
            cloud=Cloud();watch=self.watch(t,cloud)
            watch.recipe=json.loads(Path('reports/l4-qualification-v1/diagnostic-recovery-recipe-v1.json').read_text())
            status={'status':'awaiting_review','reason':'milestone_quality_review','step':5723,'milestone_tokens':3000000000,'stages':[{'type':'base'}],'review_stages':[]}
            base={'marker':'a'*64};sft={'marker':'f'*64,'status':'complete','step':155,'identity':{'source_manifest_sha256':'d'*64,'parent_bundle_manifest_sha256':'a'*64}}
            quality={'status':'development_checks_complete','diagnostic_base_mode':False,'suite_sha256':watch.recipe['comparison']['quality_suite_sha256'],'repetition_penalty':1.0,'step':155,'runner_sha256':'e'*64,'identity':{'source_manifest_sha256':'d'*64,'batch_tokens':32768,'microbatch':8,'horizon_updates':155},'records':[{'session':'a','turn':0,'assessment':{'automated_pass':False,'manual_review_required':False}}],'automated_total':1,'automated_passed':0}
            def evidence(cloud,entry,suffix,path):return {'base':base,'sft':sft,'quality':quality}[entry['type']]
            with patch.object(W,'evidence_json',side_effect=evidence),patch.object(W,'checkpoint_from_result',side_effect=lambda cloud,r:('/opt/ownbase-nano/results/checkpoint',r['marker'])):
                watch.tick(status);self.assertEqual(cloud.writes[-1]['stage'],'sft');watch.tick(status);self.assertEqual(len(cloud.writes),1)
                status['review_stages'].append({'type':'sft','command':cloud.writes[0],'sft_assessment':{'finite_dataset_complete':True,'step':155}})
                watch.tick(status);self.assertEqual(cloud.writes[-1]['stage'],'quality');self.assertNotIn('--allow-base',cloud.writes[-1]['args'])
                status['review_stages'].append({'type':'quality','command':cloud.writes[1]})
                watch.tick(status);self.assertEqual(cloud.writes[-1]['action'],'continue_base');self.assertIn('baseline',watch.state)
                watch.tick(status);self.assertEqual(len(cloud.writes),3)
    def test_final_targeted_uses_general_parent_and_original_base_ancestor(self):
        with tempfile.TemporaryDirectory() as t:
            cloud=Cloud();watch=self.watch(t,cloud,{'general':('a'*64,[{'path':'sft/general-admitted-v1/manifest.json','uri':'gs://forge-ownbase-a100-20261110/test/general','sha256':'a'*64,'bytes':1}]),'targeted':('b'*64,[{'path':'sft/targeted-teacher-admitted-v2/manifest.json','uri':'gs://forge-ownbase-a100-20261110/test/targeted','sha256':'b'*64,'bytes':1}])})
            watch.state['final_base']={'path':'/opt/ownbase-nano/results/base/step','sha256':'a'*64}
            watch.state['final-general-checkpoint']={'path':'/opt/ownbase-nano/results/general/step','sha256':'b'*64}
            done=('final-general','final-general-quality');watch.state['sent'].update({k:'done' for k in done});watch.state['final_completed']={k:{} for k in done}
            status={'status':'awaiting_review','reason':'protected_finish_boundary','step':17000,'review_stages':[{'command':{'watch_id':k}} for k in done]}
            watch.tick(status);c=cloud.writes[-1];args=c['args']
            self.assertEqual(c['watch_id'],'final-targeted');self.assertEqual(c['seconds'],1800)
            self.assertEqual(args[args.index('--manifest')+1],'/opt/ownbase-nano/sft/targeted-teacher-admitted-v2/manifest.json')
            self.assertEqual(args[args.index('--base')+1],watch.state['final-general-checkpoint']['path'])
            self.assertEqual(args[args.index('--ancestor')+1],watch.state['final_base']['path'])
    def test_absent_initial_control_created_with_generation_zero(self):
        class Missing(Cloud):
            def __init__(self):super().__init__();self.generation=0;self.exists=False
            def snapshot(self,source):
                if not self.exists:raise subprocess.CalledProcessError(1,['gcloud'],output=b'404 Not found')
                return super().snapshot(source)
            def cas(self,path,source,generation):
                self.assert_generation=generation;super().cas(path,source,generation);self.exists=True
        with tempfile.TemporaryDirectory() as t:
            cloud=Missing();watch=W.Watcher(self.config,self.recipe,'d'*64,[],t,cloud,'0'*64)
            watch.publish(self.command());self.assertEqual(cloud.assert_generation,0);self.assertEqual(len(cloud.writes),1)
            cloud.exists=False
            with self.assertRaises(subprocess.CalledProcessError):watch.publish(self.command('6b-continue'))
    def test_absent_mode_never_overwrites_existing_root_object(self):
        with tempfile.TemporaryDirectory() as t:
            cloud=Cloud();watch=W.Watcher(self.config,self.recipe,'d'*64,[],t,cloud,'0'*64)
            with self.assertRaisesRegex(ValueError,'Unexpected'):watch.publish(self.command())
            self.assertEqual(cloud.writes,[])
    def test_cloud_snapshot_retries_only_changed_generation_404(self):
        cloud=W.Cloud(time.time()+100);source=self.config['retained']['control_uri']
        missing=subprocess.CalledProcessError(1,['gcloud'],output=b'HTTP404 old generation unavailable')
        with patch.object(cloud,'run',side_effect=[b'{"generation":"7"}',missing,b'{"generation":"8"}',b'new']) as run:
            self.assertEqual(cloud.snapshot(source),(8,b'new'));self.assertEqual(run.call_count,4)
        with patch.object(cloud,'run',side_effect=[b'{"generation":"7"}',missing,b'{"generation":"7"}']) as run:
            with self.assertRaises(subprocess.CalledProcessError):cloud.snapshot(source)
            self.assertEqual(run.call_count,3)
        denied=subprocess.CalledProcessError(1,['gcloud'],output=b'HTTP403 permission denied')
        with patch.object(cloud,'run',side_effect=[b'{"generation":"7"}',denied]) as run:
            with self.assertRaises(subprocess.CalledProcessError):cloud.snapshot(source)
            self.assertEqual(run.call_count,2)
        with patch.object(cloud,'run',side_effect=[missing]) as run:
            with self.assertRaises(subprocess.CalledProcessError):cloud.snapshot(source)
            self.assertEqual(run.call_count,1)
    def test_actual_gcloud_missing_generation_wording_requires_changed_generation(self):
        cloud=W.Cloud(time.time()+100);source=self.config['retained']['control_uri']
        missing=subprocess.CalledProcessError(1,['gcloud'],output=b'ERROR: (gcloud.storage.cat) The following URLs matched no objects or files:')
        with patch.object(cloud,'run',side_effect=[b'{"generation":"7"}',missing,b'{"generation":"8"}',b'new']):
            self.assertEqual(cloud.snapshot(source),(8,b'new'))
        with patch.object(cloud,'run',side_effect=[b'{"generation":"7"}',missing,b'{"generation":"7"}']):
            with self.assertRaises(subprocess.CalledProcessError):cloud.snapshot(source)

    def test_cloud_snapshot_max_three_generation_attempts(self):
        cloud=W.Cloud(time.time()+100);source=self.config['retained']['control_uri']
        missing=subprocess.CalledProcessError(1,['gcloud'],output=b'HTTP404')
        with patch.object(cloud,'run',side_effect=[b'{"generation":"1"}',missing,b'{"generation":"2"}',missing,b'{"generation":"3"}',missing,b'{"generation":"4"}']) as run:
            with self.assertRaises(subprocess.CalledProcessError):cloud.snapshot(source)
            self.assertEqual(sum(call.args[0][0]=='cat' for call in run.call_args_list),3)
    def test_reviewed_recipe_with_self_contained_admission_no_cloud(self):
        # Retired large corpus files must not be required for a controller unit test.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);hashes=[]
            manifest={'training_admitted':True,'tokenizer_sha256':W.TOKENIZER_SHA}
            for split in ('train','validation'):
                path=root/(split+'.jsonl');path.write_text(json.dumps({'fixture':split})+'\n')
                hashes.append(W.sha(path));manifest[split]={'file':path.name,'sha256':hashes[-1]}
            receipt=root/'admission.json';receipt.write_text(json.dumps({'training_admitted':True,'jsonl_sha256':hashes}))
            manifest['admission']={'sha256':W.sha(receipt)}
            (root/'manifest.json').write_text(json.dumps(manifest))
            recipe,msha,files=W.reviewed_inputs('reports/l4-qualification-v1/diagnostic-recovery-recipe-v1.json',root)
            self.assertEqual(len(files),4);self.assertEqual(recipe['subset']['planned_updates'],155)
            command=W.sft_command(self.config,recipe,files,5723,3,'/opt/ownbase-nano/results/base/step','a'*64)
            self.assertNotIn('--output',command['args']);self.assertNotIn('--deadline-utc',command['args']);self.assertEqual(command['seconds'],900)
            self.assertEqual(command['args'][command['args'].index('--microbatch')+1],'8')
            (root/'train.jsonl').write_text('tampered')
            with self.assertRaisesRegex(ValueError,'Changed diagnostic split'):
                W.reviewed_inputs('reports/l4-qualification-v1/diagnostic-recovery-recipe-v1.json',root)

if __name__=='__main__':unittest.main()
