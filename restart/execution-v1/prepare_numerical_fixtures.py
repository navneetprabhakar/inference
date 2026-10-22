"""Materialize deterministic token fixtures and recipe; never allocate weights."""
import hashlib,json
from pathlib import Path
import numpy as np
from slm.common.config import Config
from slm.restart.segments import segments,collate
O=Path(__file__).resolve().parent

def main():
    dest=O/'numerical-fixtures-v1'
    if dest.exists():raise FileExistsError('Preserve pre-execution fixtures')
    design=json.loads((O/'numerical-suite-design-v1.json').read_text())
    assert len(design['cases'])==len({c['id'] for c in design['cases']})==40
    config=Config(vocab_size=16,hidden_size=32,intermediate_size=64,num_layers=2,num_heads=4,num_kv_heads=4,max_seq_len=64)
    # Config shape arithmetic is not a parameter allocation.
    batches={}
    definitions={'single':[[10]],'unpadded':[[10,11,12,13,14,15,10],[15,14,13,12,11,10,15]],
                 'padded':[[10,11,12,13,14,15,10],[12,13]],
                 'fit':[[10]*7 for _ in range(4)],
                 'unequal':[[10,11],[12,13,14,15]]}
    for name,docs in definitions.items():
        parts=[next(segments(f'{name}:{i}',doc,64)) for i,doc in enumerate(docs)]
        x,y,mask,spans=collate(parts,64)
        batches[name]={'inputs':x.tolist(),'targets':y.tolist(),'loss_mask':mask.tolist(),
                       'padding_mask':(mask>0).tolist(),'supervised_targets':int(mask.sum()),'spans':spans}
    perturb=np.asarray(batches['unpadded']['inputs'],dtype=np.int32).copy();perturb[:,4:]=15
    batches['causal_perturbation']={'inputs':perturb.tolist(),'unchanged_logit_positions':[0,1,2,3]}
    long_documents={str(n):[10+i%6 for i in range(n)] for n in (0,1,511,512,513,1023,1024,1025)}
    cases=[]
    for case in design['cases']:
        cases.append({k:v for k,v in case.items() if k!='status'}|{'required':True})
    contract={'status':'INPUTS_AND_RECIPE_PREPARED_RUNNER_NOT_FROZEN','case_count':40,'cases':cases,
      'fixture_config':config.to_dict(),'fixture_parameter_count_shape_only':config.parameter_count,
      'weight_seed':42,'candidate_model_unchanged':True,
      'precision':'FP32 MLX and FP32 PyTorch CPU; optional FP64 finite-difference oracle only',
      'loss_implementation':'max-centered-target-tail-softplus-v1','embedding_implementation':'native-gather-v1',
      'toy_recipe':{'lr':.02,'beta1':.9,'beta2':.95,'eps':1e-8,'matrix_decay':.1,'global_gradient_clip':1.,
                    'updates_per_backend':8,'fit_batch':'fit'},
      'trajectory_plan':{'mlx_updates':8,'torch_updates':8,'mlx_replay_updates':1,'torch_replay_updates':1,
                         'replay_checkpoint_step':7,'replay_expected_step':8,'total_optimizer_updates':18,
                         'total_update_supervised_targets':576,
                         'remaining_update_capacity_not_for_rescue':2},
      'limits':design['aggregate_limits'],'acceptance':{'absolute_error':1e-5,'relative_error':0.,'minimum_toy_loss_decrease':.5,'all_cases_required':True},
      'fit_measurement':'Mean stable loss on the fixed fit batch before updates and after update 8 for each backend. Reuse the same trajectory for optimizer and resume checks.',
      'gradient_checks':'Compare every parameter gradient; unequal target microbatches weighted by exact supervision. No optimizer update needed for isolated gradient checks.',
      'reference_checks':'Cache/full decode and causal perturbation compare valid positions only; no padded-cache decoding. Tied embedding gradient checks include input and output contributions.',
      'budget_accounting':'Every forward/backward token evaluation, replay and finite-difference probe must be charged by the runner against the 100k token-work ceiling, conservatively including evaluation-only work. Shared 30-minute wall-clock budget.',
      'remaining':['Bind each of 40 IDs to executable checks','Freeze runner and exact check-to-fixture mapping before execution','Scoped initialization and full supervisor/ledger/custody binding'],
      'no_rescue':'Failure does not authorize extra toy updates, altered tolerance, retuned recipe or a new seed.',
      'neural_weights_initialized':False,'training_started':False}
    dest.mkdir()
    for name,value in [('contract.json',contract),('batches.json',batches),('long-documents.json',long_documents)]:
        (dest/name).write_text(json.dumps(value,indent=2)+'\n')
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir()}
    (dest/'receipt.json').write_text(json.dumps({'status':'FIXTURE_INPUTS_ONLY','files_sha256':hashes,'model_allocation':False,'source':'Locally authored integer sequences; no corpus or evaluation holdout used.'},indent=2)+'\n')
    print(json.dumps({'files_sha256':hashes,'fixture_parameter_count_shape_only':config.parameter_count,'optimizer_updates_planned':18,'optimizer_target_presentations_planned':576,'status':contract['status']},indent=2))
if __name__=='__main__':main()
