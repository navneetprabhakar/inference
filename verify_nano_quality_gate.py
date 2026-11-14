"""Adversarial checks: missing evidence and failed quality must never become acceptance."""
import copy
import unittest
from cloud_training.nano_quality_gate import ValidationGuard, contract_errors, evaluation_candidates, release_decision, protected_errors, campaign_decision

H='a'*64
class GateTests(unittest.TestCase):
    def test_regression_survives_resume_and_cannot_restart(self):
        g=ValidationGuard({'relative_tolerance':.05,'patience':2})
        for step,ce in [(0,3.12),(50,2.31),(100,2.8)]:self.assertFalse(g.observe(step,ce))
        restored=ValidationGuard(g.policy,g.state)
        self.assertFalse(restored.observe(100,2.8))
        self.assertEqual(restored.state['strikes'],1)
        self.assertTrue(restored.observe(150,3.1))
        self.assertTrue(ValidationGuard(g.policy,restored.state).observe(194,2.0))
        self.assertEqual(restored.state['best_step'],50)
    def test_invalid_observations_fail(self):
        for ce in [0,-1,True,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):ValidationGuard({'relative_tolerance':.05,'patience':2}).observe(0,ce)
        g=ValidationGuard({'relative_tolerance':0,'patience':1});g.observe(5,2)
        for step,ce in [(4,2),(5,3)]:
            with self.assertRaises(ValueError):g.observe(step,ce)
        for policy in [{},{'relative_tolerance':True,'patience':2},{'relative_tolerance':.5,'patience':2},{'relative_tolerance':0,'patience':False}]:
            with self.assertRaises(ValueError):ValidationGuard(policy)
    def test_best_and_last_must_both_be_durable(self):
        entries=[{'state':'committed','pins':['best'] if s==50 else [],'receipt':{'step':s,'remote_prefix':f'gs://bucket/{s}','manifest':{'step':s}}} for s in [50,194]]
        result=evaluation_candidates({'entries':entries},50,194)
        self.assertEqual([r['step'] for r in result],[50,194]);self.assertTrue(all(r['requires_generation_review'] for r in result))
        for broken in [entries[:1],entries[1:],entries+[entries[0]]]:
            with self.assertRaises(ValueError):evaluation_candidates({'entries':broken},50,194)
        entries[0]['pins']=[]
        with self.assertRaises(ValueError):evaluation_candidates({'entries':entries},50,194)
    def test_protected_totals_cannot_override_raw_workflow(self):
        suite={'sessions':[{'id':'p','turns':[{'exact_answers':['40'],'expected_calls':[]}]}]}
        raw={'status':'development_checks_complete','suite_sha256':H,'checkpoint_manifest_sha256':H,'automated_passed':999,'records':[{'session':'p','turn':0,'result':{'status':'complete','assistant_text':'41','events':[]}}]}
        kwargs=dict(suite_sha256=H,expected_suite_sha256=H,checkpoint_sha256=H)
        self.assertTrue(protected_errors(raw,suite,**kwargs))
        raw['records'][0]['result']['assistant_text']='40'
        self.assertEqual(protected_errors(raw,suite,**kwargs),[])
        raw['checkpoint_manifest_sha256']='b'*64
        self.assertTrue(protected_errors(raw,suite,**kwargs))

    def test_hands_off_holds_for_missing_evidence_budget_or_repeated_failure(self):
        self.assertEqual(campaign_decision({})['action'],'hold_vm_off')
        names=('data_review','group_split_audit','policy_coverage','source_intent','token_mask_audit','release_suite_frozen','protected_suite_frozen','cpu_tests','gpu_recovery_qualification','stop_backup_drill','generation_sentinels','local_qualification_plan')
        state={'schema':1,'phase':'ready_for_bounded_pilot','failed_pilots':0,'active_training_vms':0,'budget':{'authorized_usd':10,'spent_upper_bound_usd':0,'reserve_usd':2,'pilot_upper_bound_usd':3},'checks':{n:{'status':'pass','sha256':H} for n in names}}
        self.assertTrue(campaign_decision(state)['action'].startswith('eligible'))
        for key,value in [('failed_pilots',2),('active_training_vms',1),('phase','quality_hold')]:
            bad=copy.deepcopy(state);bad[key]=value;self.assertEqual(campaign_decision(bad)['action'],'hold_vm_off')
        state['budget']['spent_upper_bound_usd']=6;self.assertEqual(campaign_decision(state)['action'],'hold_vm_off')

    def test_suite_rejects_invalid_host_policy_before_model_loading(self):
        from cloud_training.nano_quality import validate_suite
        suite={'purpose':'development_only_never_train','sessions':[{'id':'p','turns':[{'user':'hello','policy':{'permit_calls':False,'allowed_tools':[]}}]}]}
        with self.assertRaises(ValueError):validate_suite(suite)
        suite['sessions'][0]['turns'][0]['policy']={'permit_calls':False,'allowed_names':[]};validate_suite(suite)
        with self.assertRaises(ValueError):validate_suite(suite,release=True)
        suite['sessions']*=2
        with self.assertRaises(ValueError):validate_suite(suite)

    def fixture(self):
        suite={'purpose':'heldout_release_never_train','sessions':[{'id':'s','category':'tool','turns':[{}]}]}
        raw={'status':'complete','suite_sha256':H,'checkpoint_manifest_sha256':H,'records':[{'session':'s','turn':0,'result':{'status':'complete'}}]}
        review={'raw_sha256':H,'checkpoint_manifest_sha256':H,'reviewer':'human-or-agent','reviewed_utc':'2026-11-14','records':[{'session':'s','turn':0,'strict_pass':True,'tool_workflow_pass':True,'reason':'Verified actual operation, operands, result and final text'}]}
        contract={'_sha256':H,'release_suite_sha256':H,'protected_suite_sha256':H,'release':{'minimum_turns_by_category':{'tool':1},'minimum_category_pass_rate':1,'minimum_complete_session_rate':1}}
        return dict(raw=raw,raw_sha256=H,suite=suite,suite_sha256=H,review=review,contract=contract,checkpoint_identity={'quality_contract_sha256':H},protected_suite_sha256=H,protected_suite={'sessions':[{'id':'p','turns':[{'exact_answers':['40'],'expected_calls':[]}]}]},protected={'status':'development_checks_complete','suite_sha256':H,'checkpoint_manifest_sha256':H,'records':[{'session':'p','turn':0,'result':{'status':'complete','assistant_text':'40','events':[]}}]})
    def test_release_cli_validates_real_bundle_and_bound_review(self):
        import contextlib,io,json,tempfile,sys,hashlib
        from unittest.mock import patch
        from pathlib import Path
        import torch
        from cloud_training.nano_checkpoint import save_bundle
        from cloud_training.nano_quality_gate import main
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);a=self.fixture()
            def write(name,value):
                p=root/name;p.write_text(json.dumps(value));return hashlib.sha256(p.read_bytes()).hexdigest()
            suite_sha=write('suite.json',a['suite']);protected_sha=write('protected-suite.json',a['protected_suite'])
            a['contract'].pop('_sha256');a['contract'].update(release_suite_sha256=suite_sha,protected_suite_sha256=protected_sha)
            contract_sha=write('contract.json',a['contract'])
            model=torch.nn.Linear(1,1);optimizer=torch.optim.AdamW(model.parameters())
            save_bundle(root/'checkpoint',model=model,optimizer=optimizer,metadata={'step':1,'identity':{'quality_contract_sha256':contract_sha}},data_state={'exact':True,'next_batch':1})
            checkpoint_sha=hashlib.sha256((root/'checkpoint/manifest.json').read_bytes()).hexdigest()
            a['raw'].update(checkpoint_manifest_sha256=checkpoint_sha,suite_sha256=suite_sha)
            raw_sha=write('raw.json',a['raw']);a['review'].update(raw_sha256=raw_sha,checkpoint_manifest_sha256=checkpoint_sha);write('review.json',a['review'])
            a['protected'].update(checkpoint_manifest_sha256=checkpoint_sha,suite_sha256=protected_sha);write('protected.json',a['protected'])
            argv=['quality-gate']
            for name in ['contract','raw','suite','review','protected','protected-suite']:argv.extend(['--'+name,str(root/(name+'.json'))])
            argv.extend(['--checkpoint',str(root/'checkpoint'),'--output',str(root/'decision.json')])
            with patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(),0)
            self.assertTrue(json.loads((root/'decision.json').read_text())['quality_accepted'])
            a['review']['raw_sha256']='b'*64;write('review.json',a['review']);argv[-1]=str(root/'blocked.json')
            with patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(),2)
            self.assertFalse(json.loads((root/'blocked.json').read_text())['quality_accepted'])

    def test_new_contract_requires_matching_one_shot_release_claim(self):
        a=self.fixture();a['contract']['require_one_shot_release']=True
        self.assertFalse(release_decision(**a)['quality_accepted'])
        a['raw']['release_claim']={'checkpoint_manifest_sha256':H,'suite_sha256':H,'utc':'2026-11-14'}
        self.assertTrue(release_decision(**a)['quality_accepted'])
        a['raw']['release_claim']['suite_sha256']='b'*64
        self.assertFalse(release_decision(**a)['quality_accepted'])

    def test_complete_bound_evidence_passes(self):self.assertTrue(release_decision(**self.fixture())['quality_accepted'])
    def test_forged_aggregate_and_coincidental_answer_fail(self):
        a=self.fixture();a['review']['records'][0]['tool_workflow_pass']=False;a['raw']['automated_passed']=1000
        self.assertFalse(release_decision(**a)['quality_accepted'])
    def test_missing_changed_or_partial_evidence_fails(self):
        mutations=[lambda a:a.update(protected=None),lambda a:a['review'].update(raw_sha256='b'*64),lambda a:a['raw'].update(status='incomplete_timeout'),lambda a:a['review'].update(records=[]),lambda a:a['suite'].update(purpose='development_only_never_train'),lambda a:a.update(checkpoint_identity={}),lambda a:a['raw']['records'][0]['result'].update(status='error'),lambda a:a['review']['records'][0].update(strict_pass=1),lambda a:a['review']['records'][0].update(reason=''),lambda a:a['contract']['release']['minimum_turns_by_category'].update(natural=20)]
        for mutate in mutations:
            a=self.fixture();mutate(a);self.assertFalse(release_decision(**a)['quality_accepted'])
    def test_duplicate_turns_fail(self):
        a=self.fixture();a['raw']['records']*=2;a['review']['records']*=2
        self.assertFalse(release_decision(**a)['quality_accepted'])
    def test_current_missing_abstention_and_wrong_revision_block(self):
        modes={'disabled_no_call':190,'enabled_call':321}
        cov={'assistant_targets':43183,'turn_modes':modes,'families':{'natural':{'sessions':80}}}
        contract={'schema':1,'objective':'conversation_and_tools','dataset_manifest_sha256':H,'tokenizer_sha256':H,'context_tokens':2048,'required_parent_manifest_sha256':'b'*64,'release_suite_sha256':H,'coverage':{'minimum_training_turns':{'disabled_no_call':1,'enabled_no_call':1,'enabled_call':1},'minimum_unique_assistant_targets':1,'minimum_family_sessions':{'natural':1}},'recipe_limits':{'max_epochs':2,'max_lr_multiplier':.125,'max_eval_interval':10},'regression':{'relative_tolerance':.05,'patience':2}}
        errors=contract_errors(contract,manifest={'_sha256':H,'tokenizer_sha256':H,'context_tokens':2048},admission={'parent_manifest_sha256':H},train=cov,dev=cov,epochs=8,lr_multiplier=1,eval_interval=50)
        self.assertTrue(any('enabled_no_call' in e for e in errors));self.assertTrue(any('corpus revision' in e for e in errors));self.assertEqual(sum('Recipe' in e for e in errors),3)

if __name__=='__main__':unittest.main()
