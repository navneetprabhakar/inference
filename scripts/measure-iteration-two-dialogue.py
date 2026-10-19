#!/usr/bin/env python3
"""Count candidate train exposure with the old pilot tokenizer; never fit or train."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
import numpy as np
from slm.common.tokenizer import BPE
from slm.data.build import verify
from slm.data.tokenized import sha
from slm.data.schema import digest


def main():
    dataset=Path('data/iteration-two-dialogue-preparation-v1/staged')
    tokenizer=Path('data/context-research-tokenizers-v1/vocab-16384')
    output=Path('reports/milestone-forty-four-candidate-token-measurement.json')
    if output.exists():raise FileExistsError(output)
    verify(dataset);bpe=BPE.load(tokenizer);nodes={};totals=Counter();sizes=[]
    for path in sorted(dataset.glob('train-*.jsonl')):
        for line in path.open():
            row=json.loads(line)
            if not row['validation_results'].get('dialogue_candidate'):continue
            if row['split']!='train':raise AssertionError('Nontrain candidate in train shard')
            x,_,mask=bpe.serialize(row['messages'],objective='assistant')
            sizes.append(len(x));totals['candidate_paths']+=1
            totals['serialized_processed_positions']+=len(x);totals['assistant_supervised_positions']+=int(sum(mask))
            for key,message in zip(row['lineage'],row['messages'],strict=True):
                identity=digest(message);prior=nodes.get(key)
                if prior is not None and prior[0]!=identity:raise AssertionError('Shared raw node changed text or role')
                if prior is None:nodes[key]=(identity,len(bpe.encode(message['content'])))
                totals['path_content_token_occurrences']+=nodes[key][1]
    totals['shared_node_repeated_content_token_occurrences']=totals['path_content_token_occurrences']-sum(v[1] for v in nodes.values())
    result=dict(creator='Navneet Prabhakar',dataset_manifest_sha256=sha(dataset/'manifest.json'),
        tokenizer_manifest_sha256=sha(tokenizer/'manifest.json'),script_sha256=sha(__file__),
        counted_split='train',counts=dict(totals),distinct_raw_nodes=len(nodes),
        content_tokens_counted_once_per_raw_node=sum(v[1] for v in nodes.values()),
        full_path_positions_percentiles={str(q):float(np.percentile(sizes,q)) for q in (50,90,95,99)} if sizes else {},
        full_paths_over_1024=sum(n>1024 for n in sizes),full_paths_over_2048=sum(n>2048 for n in sizes),
        tokenizer_refitted=False,training_eligible=False,neural_updates=0,
        scope='Sizing only with the existing prose-pilot BPE. Raw-node uniqueness is not global semantic or substring uniqueness. Full-path counts include shared prefix repetition and structural positions; no truncation, admission or training occurred.')
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':main()
