import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parent;ROOT=P.parents[2]
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def save(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
src=ROOT/'restart/conversation-improvement-v1/private/replay.npy';original=ROOT/'restart/short-answer-transfer-v1/private/replay.npy';val=ROOT/'restart/foundation-stage3-v1/validation.npy'
a=np.load(src).reshape(-1,257);b=np.load(original).reshape(-1,257);v=np.load(val).reshape(-1,257)
assert a.dtype==np.uint16 and b.dtype==np.uint16
unique={hashlib.sha256(r.tobytes()).hexdigest():r for r in a};base={hashlib.sha256(r.tobytes()).hexdigest() for r in b};validation={hashlib.sha256(r.tobytes()).hexdigest() for r in v}
assert set(unique)==base and not(set(unique)&validation)
keys=sorted(unique);bank=np.stack([unique[k] for k in keys]);assert len(bank)==1600;np.save(P/'private/replay.npy',bank)
for seed in [291102,291103]:
 rng=np.random.default_rng(seed);order=np.concatenate([rng.permutation(len(bank)) for _ in range(5)]).reshape(1000,8)
 assert sorted(np.bincount(order.ravel()).tolist())==[5]*len(bank)
 np.save(P/f'private/order-{seed}.npy',order)
source_proof=ROOT/'restart/short-answer-transfer-v1/prepare.py'
result=dict(status='BLOCK_INTEGRITY_PASS_PROVENANCE_LIMITATION_RECORDED',source=str(src.relative_to(ROOT)),source_sha256=sha(src),original_training_replay=str(original.relative_to(ROOT)),original_sha256=sha(original),source_preparer=str(source_proof.relative_to(ROOT)),source_preparer_sha256=sha(source_proof),historical_rows=len(a),distinct_rows=len(bank),validation_rows=len(v),exact_validation_overlap=0,updates_per_schedule=1000,blocks_per_update=8,exposures_per_distinct_block=5,replay_targets_per_run=1000*8*256,training_origin='Original preparer uses Stream(train,skip_sequences=1610240) and checks excluded validation-bin identity; current bank exactly equals original bank after deduplication.',provenance_limitation='No per-document/source-family reconstruction; exact block separation does not prove semantic independence. Native NLL remains limited; fresh readiness behavior is principal preservation test.',student_calls=0,files={str(f.relative_to(P)):sha(f) for f in sorted((P/'private').glob('*'))})
save('manifest.json',result);print(json.dumps({k:result[k] for k in ['status','distinct_rows','exact_validation_overlap','exposures_per_distinct_block']},indent=2))
