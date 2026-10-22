"""Reconcile immutable work records and publish the failed capability result."""
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3

ROOT=Path(__file__).resolve().parent
OLD=ROOT/'student-run-v1'
RUN=ROOT/'student-run-recovery-v1'

def read(p):return json.loads(p.read_text())
def rows(p):return [json.loads(l) for l in p.read_text().splitlines()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n')

def main():
    acceptance=read(ROOT/'acceptance.json');final=read(RUN/'final-test-responses.json');grade=read(RUN/'final-response-assessment.json')
    historical=rows(OLD/'work-ledger.jsonl');retained=rows(RUN/'work-ledger.jsonl')
    reserved=[r for r in historical+retained if r['status']=='RESERVED']
    completed=[r for r in historical+retained if r['status']=='COMPLETED']
    applied=[r for r in retained if r['status']=='COMPLETED']
    assert (len(reserved),len(completed),len(applied))==(636,635,616)
    base=sum(r['targets'] for r in reserved if r['phase']=='base');sft=sum(r['targets'] for r in reserved if r['phase']=='sft')
    assert base==2000000 and sft==32634
    assert sum(r['targets'] for r in applied if r['phase']=='base')==1909112
    boundaries=defaultdict(list);dialogue_views=Counter()
    for r in reserved:
        if r['phase']=='base':
            for doc,a,b in r['ids']:boundaries[doc].extend([(a,1),(b,-1)])
        else:
            for d in r['ids']:dialogue_views[d['id']]+=1
    maximum=0
    for events in boundaries.values():
        count=0
        for _,delta in sorted(events,key=lambda e:(e[0],e[1])):count+=delta;maximum=max(maximum,count)
    assert maximum==2 and len(dialogue_views)==382 and max(dialogue_views.values())==2
    charges=[];observations=[]
    for folder in (OLD,RUN):
        db=sqlite3.connect((folder/'time.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
        try:charges.append(db.execute('SELECT charged FROM budget WHERE id=1').fetchone()[0])
        finally:db.close()
        for name,h in read(folder/'source-pins.json').items():assert sha(Path(name))==h
        observations.extend((folder.name,r['measurement']) for r in rows(folder/'supervisor.json.resources.jsonl') if r['kind']=='resource')
    assert sum(charges)<=3600
    assert sha(RUN/'initial.safetensors')==sha(RUN/'restore.safetensors')==sha(OLD/'initial.safetensors')
    assert sha(RUN/'best.safetensors')==final['checkpoint_sha256']
    assert len(final['cases'])==50 and grade['conversation_passes']==0
    recovery_observed=[v for name,v in observations if name==RUN.name]
    phases={n:read(RUN/(n+'.json'))['development_nll'] for n in ('initial','after-base','after-sft-1','after-sft-2')}
    report=dict(status='TEACHER_PASS_STUDENT_CONVERSATION_FAIL_STOPPED',
      teacher=dict(model='gpt-6-luna',generated=500,usable=482,held=18,train=382,development=50,test=50,
        retained_task_families=49,retained_train_families=39,manual_sample_passes=97,manual_sample=100,
        detected_cross_split_near_matches=0,exact_full_heldout_initial_prompt_matches_in_base_training=0,
        counts=acceptance['counts']),
      student=dict(parameters=5114112,fresh_initializations=1,pretrained_weights_imported=False,
        checkpoint='student-run-recovery-v1/best.safetensors',checkpoint_sha256=final['checkpoint_sha256'],
        charged_updates=len(reserved),historical_completed_updates=len(completed),retained_updates=len(applied),
        discarded_completed_updates_at_swap_stop=19,interrupted_reservation_charged=1,
        charged_base_targets=base,base_targets_applied_to_retained_model=1909112,sft_targets=sft,sft_passes=2,
        optional_third_pass_skipped=True,max_base_target_exposures=maximum,max_dialogue_presentations=2,
        charged_active_seconds_including_evaluations=sum(charges)),
      results=dict(development_nll=phases,development_conversation_passes=0,development_conversations=20,
        development_repetition_failures=8,final_conversation_passes=0,final_conversations=50,
        correct_individual_final_replies=10,individual_final_replies=100,identical_no_replies=96,
        decoder_parity=read(RUN/'decoder-parity-check.json')),
      resources=dict(initial_resource_stop='Global swap grew562.12MiB, exceeding512MiB; original stop preserved.',
        original_swap_baseline_mib=203.38,recovery_swap_baseline_mib=765.5,
        recovery_max_observed_swap_growth_mib=max(v['swap_growth_mib'] for v in recovery_observed),
        recovery_max_observed_rss_gib=max(v['rss_gib'] for v in recovery_observed),
        recovery_gpu_peak_bytes=read(RUN/'progress.json')['mlx_peak_bytes'],cache_limit_bytes=134217728,
        disclosure='The one recovery records a fresh system-swap baseline after the stopped process was reaped. This does not erase the first guard breach or claim aggregate swap growth stayed below512MiB.'),
      interpretation=dict(working_conversational_model=False,
        supported_conclusion='This5.1M model / short foundation exposure /382-conversation SFT recipe failed the response gate. Lower loss did not produce correct conversations.',
        scope='Result applies to this bounded recipe. Feasibility of an own foundational conversational model below100M parameters is not determined.',
        hypotheses_not_proven='Insufficient foundation-language learning and narrative-heavy base data are plausible contributors; this experiment does not isolate parameter capacity, data quantity, objective weighting or optimization as the single cause.'),
      stop='Observed development response degeneration stopped updates. The final holdout was scored once for diagnosis, with no subsequent tuning. No scaling or training remains active.',
      next_experiment_proposal_only=dict(executed=False,teacher_scaling=False,architecture_change=False,
        objective='Establish a foundation-language competence gate before conversation SFT; a2M-target smoke run did not establish it.',
        steps=['Measure a complete eligible base-data pass under a separately frozen token/time plan and a language/coherence development gate.',
          'Retain the accepted teacher curriculum; do not expand conversation volume as a substitute for the base-language check.',
          'Use fresh final cases for any next experiment designed using the outcomes of the current holdout.']))
    save(ROOT/'assessment.json',report)
    save(ROOT/'work-accounting-verification.json',dict(status='PASS',all_source_pins_unchanged=True,one_initialization=True,
        restored_initial_identical=True,charged_updates=636,retained_updates=616,charged_base_targets=base,sft_targets=sft,
        max_base_target_exposure=maximum,max_dialogue_exposure=2,aggregate_active_seconds=sum(charges),within_work_time_caps=True,final_test_invocations=1))
    print(json.dumps(dict(status=report['status'],active_seconds=sum(charges),retained_updates=616,final='0/50')))

if __name__=='__main__':main()
