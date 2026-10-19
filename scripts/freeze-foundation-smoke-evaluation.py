#!/usr/bin/env python3
"""Freeze validation prefixes before training; no model scoring or test-set use."""
# Creator: Navneet Prabhakar
from pathlib import Path
import json
from slm.common.tokenizer import BPE
from slm.data.review_stream import open_checked
from slm.data.schema import digest
from slm.data.tokenized import sha


def main():
    root=Path('data/context-research-pilot-v2');output=root/'evaluation-prefixes.json'
    if output.exists():raise FileExistsError(output)
    spec=json.loads((root/'pilot.json').read_text());release=Path(next(iter(spec['releases'].values())))
    bpe=BPE.load(spec['tokenizer']);groups={};seed='foundation-smoke-validation-20261019-v1'
    with open_checked(release) as checked:
        train_groups={g for g, in checked.db.execute('SELECT DISTINCT gid FROM approved WHERE split="train"')}
        for data,gid in checked.db.execute('SELECT data,gid FROM approved WHERE split="validation" ORDER BY eid'):
            row=json.loads(data);tokens=bpe.encode(row['messages'][0]['content'])
            if len(tokens)<129 or gid in groups:continue
            if gid in train_groups:raise ValueError('Validation group intersects training')
            groups[gid]=dict(example_id=row['example_id'],record_sha256=digest(row),group=gid,
                tokens=tokens[:129],prediction_positions=128)
    chosen=[groups[g] for g in sorted(groups,key=lambda g:(digest([seed,g]),g))[:32]]
    if len(chosen)!=32:raise ValueError('At least 32 eligible distinct validation groups required')
    protocol=dict(version=1,scope='local_foundation_smoke_only',selection_seed=seed,selection='SHA-ranked validation groups, one canonical row per group with at least 129 content tokens; first 128 next-token positions.',
        release_manifest_sha256=sha(release/'manifest.json'),tokenizer_manifest_sha256=sha(Path(spec['tokenizer'])/'manifest.json'),
        pilot_spec_sha256=sha(root/'pilot.json'),initialization_seed=spec['seed'],config=spec['config'],
        embedding_implementation=spec['recipe']['embedding_implementation'],loss_implementation=spec['recipe']['loss_implementation'],
        metric='Mean token NLL in nats on the same 32 fixed 128-target validation prefixes before and after the run.',
        comparison='Paired per-group baseline minus final NLL; percentile 95% CI, 10000 group bootstrap resamples, NumPy seed 20261019.',
        smoke_threshold='Finite losses, mean improvement at least 0.1 nats/token, and lower 95% bootstrap bound greater than zero.',
        limitations='Development prose prefixes only; not full-corpus perplexity, factual accuracy, conversation/tool capability or the MLX/CUDA resumed-quality gate.',
        test_records_used=0,groups=chosen,prediction_positions=4096)
    output.write_text(json.dumps(protocol,indent=2,sort_keys=True)+'\n')
    receipt={k:v for k,v in protocol.items() if k!='groups'}
    receipt.update(creator='Navneet Prabhakar',selected_groups=32,selected_rows_sha256=digest(chosen),
        protocol_file_sha256=sha(output),script_sha256=sha(__file__),model_updates=0,model_scores_observed=0)
    Path('reports/milestone-thirty-nine-evaluation-freeze.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(selected_groups=32,prediction_positions=4096,protocol_sha256=sha(output))))


if __name__=='__main__':main()
