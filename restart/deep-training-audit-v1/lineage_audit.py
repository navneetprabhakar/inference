"""Read checkpoint metadata without altering tensors or optimizer state."""
import torch,json
from pathlib import Path
R=Path(__file__).resolve().parent;P=R.parents[1];out={}
for label,rel in [('short_answer','restart/factual-binding-v1/binding/epoch-400.pt'),('broader_candidate','restart/broader-curriculum-v1/broad/epoch-100.pt')]:
 state=torch.load(P/rel,map_location='cpu',weights_only=False)
 fields=['schema','foundation_source_sha256','foundation_retained_targets','foundation_source_optimizer_step','parent_checkpoint_sha256','parent_sft_updates','parent_sft_targets','sft_updates','sft_supervised_targets','cumulative_sft_updates','cumulative_sft_targets','foundation_replay_targets','cumulative_foundation_replay_targets']
 out[label]={k:state[k] for k in fields if k in state};del state
(R/'lineage.json').write_text(json.dumps(dict(checkpoints=out,interpretation='Short-answer child starts from original foundation and deterministic factual drills; broader child adds deterministic curriculum. Earlier Sol SFT/transfer branches are not ancestors. Generated 1000-conversation teacher batch is not in current-child SFT lineage.'),indent=2)+'\n')
