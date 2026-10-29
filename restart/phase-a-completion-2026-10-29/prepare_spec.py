"""Freeze selections without using student scores. Does not authorize execution."""
import json,random,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;OLD=P.parent/'phase-a-2026-10-28'
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
assert not (P/'freeze.json').exists()
rows=json.loads((OLD/'private/prepared-v2/matrix.json').read_text());rng=random.Random(291026)
sentinel=[]
for family in sorted({r['scenario']['family'] for r in rows}):
 for cell in 'ABCD':
  choices=[r['id'] for r in rows if r['scenario']['family']==family and r['cell']==cell];sentinel+=rng.sample(choices,4)
assert len(sentinel)==len(set(sentinel))==128
save('sentinel.json',{'seed':291026,'selection':'4 cases per task per A/B/C/D cell, no student scores consulted','source_sha256':sha(OLD/'private/prepared-v2/matrix.json'),'ids':sentinel})
spec={'status':'PROPOSED_NOT_EXECUTABLE','training_authorized':False,'seed':291026,'context':256,'generated_tokens_including_eos':32,'arms':[{'wording':w,'replay_coefficient':r} for r in [0.5,0.0] for w in ['canonical','diverse']],'main_updates_per_arm':1000,'batch_size':8,'endpoint_selection_only':True,'sentinel_updates':[250,500],'endpoint_update':1000,'data_manifest_sha256':sha(OLD/'prepared-v2-freeze.json'),'source_checkpoint_sha256':json.loads((OLD/'freeze.json').read_text())['sources']['foundation'],'optimizer_proposal':{'type':'AdamW','betas':[0.9,0.95],'epsilon':1e-8,'weight_decay':0,'bias_correction':True,'global_gradient_norm_clip':1.0,'schedule':'constant after training-only LR selection','learning_rate_candidates':[2e-5,1e-4,5e-4]},'ceilings':{'updates':4612,'input_positions':50000000,'assistant_eos_targets':1000000,'narrative_targets':10000000,'active_model_seconds':5400,'additional_artifact_gib':6,'memory_gib':12,'minimum_free_disk_gib':60},'thresholds':{'D_overall':0.9,'D_each_task':0.8,'D_complete_state_conversations':0.8,'counterfactual_both_correct_each_intervention':0.8,'max_preservation_decline_percentage_points':5},'remaining_launch_requirements':['Runnable grouped full-finetuning implementation and loss/gradient/resume checks','Exact replay stream and behavior-regression packet/source baseline','Model config, precision and runner hashes','Explicit training/calibration budget approval','Measured backward/evaluation feasibility before retained arms'],'natural_packet_role':'short-response development transfer diagnostic, no final acceptance claim','surface_diversity_claim':'20 strings per task; not 20 independently validated linguistic families'}
save('experiment-spec.json',spec)
print('Prepared 128 sentinel IDs and proposed four-arm specification; execution disabled.')
