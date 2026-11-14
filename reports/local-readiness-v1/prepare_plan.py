"""Prepare a proposal only. No GCP writes, reservations, or VM operations."""
import datetime,json,hashlib
from pathlib import Path
P=Path('reports/local-readiness-v1');C=Path('reports/corrective-corpus-v1')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
plan={
 'schema':1,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'status':'awaiting_explicit_user_cap_keep_all_vms_off','authorized_usd':None,
 'recommended':{'machine':'a2-highgpu-1g','gpu':'1x A100 40GB','region':'us-central1','provisioning':'FLEX_START','price_usd_per_hour':2.0,'proposed_cap_usd':15,'maximum_billable_hours':4,'compute_list_price_usd':8,'compute_with_25_percent_margin_usd':10,'ancillary_and_recovery_reserve_usd':5},
 'qualification_only':{'proposed_cap_usd':5,'maximum_billable_hours':1,'backup_reserve_minutes':15,'compute_with_25_percent_margin_usd':2.5,'reserve_usd':2.5,'pilots_included':False},
 'cheaper_unqualified_alternative':{'machine':'g2-standard-8','gpu':'1x L4 24GB','region':'us-central1','provisioning':'STANDARD','price_usd_per_hour':0.853624312,'proposed_cap_usd':10,'maximum_billable_hours':6,'compute_with_25_percent_margin_usd':6.40218234,'reserve_usd':3.59781766,'caveats':['4K fit/throughput not measured on L4.','Prior L4 capacity attempts failed.','Needs L4-compatible bootstrap; existing A100-only bootstrap must not be reused unchanged.','This is a lower-cost option, not a proven equivalent or automatic fallback.']},
 'budget_scope':'Caps and billable-hour ceilings are cumulative across all qualification/pilot leases, not per VM or per retry. Reconcile actual stopped-VM elapsed time before releasing unused reservations. Never start a second writer or reset the ledger on restart.',
 'prices_checked_on':'2026-11-14','price_sources':['https://cloud.google.com/products/dws/pricing','https://cloud.google.com/products/compute/pricing/accelerator-optimized'],
 'price_conditions':['Recheck at allocation. DWS page flags November2026 changes.','No automatic fallback to on-demand A100 ($3.673385/hour), larger GPU, Spot, or extra time.','No guarantee that qualification or pilots finish within the proposed lease; stop on deadline and report incomplete work.','Reserve covers bounded disk/GCS/network/price/tax uncertainty, not an invoice guarantee. Recompute before allocation if account charges differ.','Existing retained storage continues billing while VMs are off; this proposal covers the bounded new run, not indefinite storage.'],
 'stages_minutes':{'setup_and_gpu_qualification':60,'pilot_1_and_generated_checks':60,'optional_pilot_2_and_generated_checks':75,'backup_readback_and_closeout':45},
 'image':json.loads((P/'replacement-image-status.json').read_text()),
 'image_decision':'Prior pinned20261029image is deprecated. Proposed20261111replacement is READY and not deprecated; verify exacttorch2.9.1/CUDA12.9 at boot and HOLD on mismatch. No image was launched.',
 'parent':{'path':'runs/local-readiness-v1/base10b','manifest_sha256':'7d803e32928ca9ecc1fe38bf7d47c54bca80c0996d6bb006b718cfd851975e53','reason':'Restart SFT from immutable10B base to isolate the corrective recipe; do not stack it on regressed194.'},
 'recipe':json.loads((P/'actual-packet-checks.json').read_text())['recipe'],
 'bindings':{'dataset_manifest_sha256':sha(C/'candidate-4k/manifest.json'),'quality_contract_sha256':sha(C/'quality-contract.json'),'freeze_sha256':sha(C/'freeze.json'),'validation_command_sha256':sha(P/'validate-only.sh'),'full_development_suite_sha256':sha(P/'full-development-suite.json'),'development_shards_sha256':sha(P/'development-checks.json')},
 'qualification_protocol':[
 'Use a new unique output/lease, one writer, fresh bounded provider STOP deadline and autoDelete=false persistent disk. Never resume old controllers or use their DELETE-on-timeout launcher.',
 'Record torch2.9.1/CUDA12.9, GPU, kernel hashes, deterministic settings and full context configuration. Microbatch1 at4096; no silent context reduction.',
 'Run actual SFT adapters on frozen training data: uninterrupted2updates versus1update, verified GCS checkpoint download, fresh-process restore, then1update. Keep identical parent, data/order, schedule, runtime, seed and recipe.',
 'Use nano_restart_compare to compare full model, optimizer, RNG, packing cursor and quality-guard state at step2. Any drift is HOLD; old numerical exceptions do not carry forward.',
 'Exercise signal mid-accumulation, failed upload before COMMITTED, and writer contention. Verify rollback/no second writer/no false committed receipt. Reconcile disk and GCS after fault.',
 'Prove provider STOP deadline independently of worker/backup success. Preserve the persistent disk on failed backup; never let a failed upload authorize a disk delete.',
 'Qualification consumes separate disposable outputs and is not counted as a quality pilot. Training starts only after reviewed receipts pass.'
 ],
 'pilot_protocol':[
 'At most two pilots, each <=10updates. Pilot1 starts from base; second is allowed only after an explicit evidence-based decision recorded in the handoff, without raising LR/epochs or silently changing data.',
 'Evaluate complete61-session development loss overall and by family at start,5,10. Fail closed on partial evaluation, nonfinite state, or persisted regression stop.',
 'Generate all61development sessions/232turns using the13frozen shards plus18protected tool turns for best AND last. Preserve system messages and fixed per-turn reply budgets; no partial shard aggregate pass. Review every raw answer and actual broker call; blocked followups remain failures.',
 'The full development suite includes all retained long dialogues. Its21reference answers above512tokens receive adequate budgets, bounded at1342tokens/action. Review code and semantics; no exact-wording requirement for open-ended responses. Do not borrow frozen release questions.',
 'Select best/last by development evidence; reject a candidate with new policy violation, tool error, factual contradiction, looping, or category regression. Small gains do not establish release acceptance.',
 'Two failed pilots force HOLD and diagnosis. Stop early on failure; do not spend the remaining cap merely to finish a schedule.',
 'Independent189-turn release remains sealed during pilots. Full release and matched localMPS acceptance are a later gate, not guaranteed within this qualification/pilot allowance.'
 ],
 'shutdown_and_storage':[
 'Worker stops useful work45minutes before provider deadline. Stop and join all writers, save required best/last and restart state, upload required artifacts, independently download/hash every required bundle, then stop VM.',
 'Backup failure does not extend compute. Provider STOP still applies; retain non-auto-delete disk and mark recovery pending. Never report full backup without readback evidence.',
 'No idle GPU while doing lengthy local semantic review. Healthy-run updates roughly30minutes, immediate fault/budget alerts.',
 'Retain source, selected checkpoints, raw evaluation and receipts only. Do not recreate obsolete corpus archives.'
 ],
 'local_4k_plan':'MPS full-size4096forward smoke passed; repeat selected trained4K candidate through matched real conversation/tool suites before any default promotion.',
 'not_authorized':['VM start/create','compute reservation','paid training','release exposure','model promotion']}
(P/'gpu-proposal.json').write_text(json.dumps(plan,indent=2)+'\n')
print('Wrote proposal; authorized_usd remains null.')
