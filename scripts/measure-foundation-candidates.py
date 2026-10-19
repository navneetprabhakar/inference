#!/usr/bin/env python3
"""Size the broader candidate pool without fitting a tokenizer or training."""
# Creator: Navneet Prabhakar
from collections import Counter,defaultdict
import json
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.data.build import verify
from slm.data.schema import digest
from slm.data.tokenized import sha,stamp


def main():
    root=Path('data/iteration-two-foundation-candidates-v1/staged')
    tokenizer=Path('data/context-research-tokenizers-v1/vocab-16384')
    output=Path('reports/milestone-forty-six-foundation-measurement.json')
    if output.exists():raise FileExistsError(output)
    verify(root);bpe=BPE.load(tokenizer)
    guards={p:stamp(p) for p in [*root.iterdir(),*tokenizer.iterdir(),Path(__file__)]}
    totals=Counter();sources=defaultdict(Counter);content={};nodes={};node_exposures=Counter();lengths=[];groups=set()
    for path in sorted(root.glob('train-*.jsonl')):
        for line in path.open():
            row=json.loads(line)
            if row['split']!='train':raise AssertionError('Nontrain row in train shard')
            proof=row['validation_results']
            if not (proof.get('dialogue_candidate') or proof.get('foundation_dialogue_candidate')):raise AssertionError('Unmarked train reference')
            x,_,mask=bpe.serialize(row['messages'],objective='assistant');lengths.append(len(x));source=row['source']
            groups.add(proof['split_group'])
            for counts in (totals,sources[source]):
                counts['paths']+=1;counts['processed_positions']+=len(x);counts['assistant_supervised_positions']+=int(sum(mask))
            if proof.get('foundation_dialogue_candidate'):
                prior=proof['foundation_dialogue_candidate'].get('prior_review')
                if prior is not None:totals['prior_review_approved_paths' if prior['approved'] else 'prior_review_not_approved_paths']+=1
            for i,message in enumerate(row['messages']):
                text=message['content'];key=digest(text)
                if key not in content:content[key]=len(bpe.encode(text))
                node=(source,row['lineage'][i] if row['lineage'] else row['example_id']+':message:'+str(i))
                if node in nodes and nodes[node]!=(key,message['role']):raise AssertionError('Shared node text/role changed')
                if node not in nodes:
                    nodes[node]=(key,message['role']);totals['content_tokens_once_per_raw_message_identity']+=content[key]
                    sources[source]['content_tokens_once_per_raw_message_identity']+=content[key]
                node_exposures[node]+=1
                for counts in (totals,sources[source]):counts['path_content_token_occurrences']+=content[key]
    totals['content_tokens_once_per_exact_message_text']=sum(content.values())
    totals['shared_node_repeated_content_occurrences']=totals['path_content_token_occurrences']-totals['content_tokens_once_per_raw_message_identity']
    if any(stamp(p)!=v for p,v in guards.items()):raise ValueError('Measurement inputs changed')
    report=dict(creator='Navneet Prabhakar',dataset_manifest_sha256=sha(root/'manifest.json'),tokenizer_manifest_sha256=sha(tokenizer/'manifest.json'),
        script_sha256=sha(__file__),counted_split='train',counts=dict(totals),sources={k:dict(v) for k,v in sources.items()},
        split_groups=len(groups),distinct_raw_message_identities=len(nodes),distinct_exact_message_texts=len(content),
        max_shared_raw_message_occurrences=max(node_exposures.values(),default=0),full_paths_over_1024=sum(n>1024 for n in lengths),
        full_paths_over_2048=sum(n>2048 for n in lengths),training_eligible=False,tokenizer_refitted=False,new_neural_updates=0,
        scope='Unadmitted train-candidate sizing with the old pilot BPE only. Exact message dedup does not remove shared substrings, Wikipedia passages inside different prompts or semantic duplicates. A raw message identity is a node ID for OASST and a parent example/message index for Dolly. Full serialized positions include shared prefixes and structure; no truncation, corpus admission or prepared training schedule.')
    with output.open('x') as f:f.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:report[k] for k in ('counts','sources','full_paths_over_1024','full_paths_over_2048')},indent=2),flush=True)


if __name__=='__main__':main()
