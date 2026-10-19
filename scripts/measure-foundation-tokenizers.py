#!/usr/bin/env python3
"""Measure full admitted splits, with no heldout text entering BPE fitting."""
# Creator: Navneet Prabhakar
from collections import Counter,defaultdict
import json
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.data.build import verify
from slm.data.schema import digest
from slm.data.tokenized import sha,stamp


def main():
    root=Path('data/iteration-two-foundation-research-v1');candidates=Path('data/iteration-two-foundation-tokenizers-v1')
    output=Path('reports/milestone-forty-seven-tokenizer-comparison.json')
    if output.exists():raise FileExistsError(output)
    verify(root);comparison=json.loads((candidates/'comparison.json').read_text())
    if any(c['training']['release_manifest_sha256']!=sha(root/'manifest.json') for c in comparison['candidates']):raise ValueError('Fitted release differs')
    guards={p:stamp(p) for p in [*root.iterdir(),candidates/'comparison.json',Path(__file__)]}
    bpes={size:BPE.load(candidates/f'vocab-{size}') for size in (16384,24576)}
    for size in bpes:
        for p in (candidates/f'vocab-{size}').iterdir():guards[p]=stamp(p)
    result={size:defaultdict(Counter) for size in bpes};unique={size:defaultdict(dict) for size in bpes}
    sources={size:defaultdict(Counter) for size in bpes}
    for split in ('train','validation','test'):
        for path in sorted(root.glob(split+'-*.jsonl')):
            for line in path.open():
                row=json.loads(line)
                if row['split']!=split:raise ValueError('Split differs')
                for size,bpe in bpes.items():
                    counts=result[size][split];tokens,_,mask=bpe.serialize(row['messages']);n=len(tokens)
                    counts.update(paths=1,serialized_positions=n,assistant_supervised_positions=sum(mask),
                                  full_paths_over_1024=int(n>1024),full_paths_over_2048=int(n>2048))
                    if split=='train':sources[size][row['source']]['paths']+=1
                    for message in row['messages']:
                        text=message['content'];key=digest(text)
                        if key not in unique[size][split]:
                            encoded=bpe.encode(text)
                            if bpe.decode(encoded)!=text:raise ValueError('Text round-trip differs')
                            unique[size][split][key]=len(encoded)
                            counts['distinct_exact_message_texts']+=1;counts['exact_message_utf8_bytes']+=len(text.encode())
                        length=unique[size][split][key];counts['path_content_token_occurrences']+=length
                        if split=='train':sources[size][row['source']]['path_content_token_occurrences']+=length
    for size in bpes:
        for split,counts in result[size].items():
            counts['content_tokens_once_per_exact_message_text']=sum(unique[size][split].values())
            counts['exact_message_tokens_per_utf8_byte']=counts['content_tokens_once_per_exact_message_text']/counts['exact_message_utf8_bytes']
    if any(stamp(p)!=s for p,s in guards.items()):raise ValueError('Measurement inputs changed')
    report=dict(creator='Navneet Prabhakar',release_manifest_sha256=sha(root/'manifest.json'),
        comparison_file_sha256=sha(candidates/'comparison.json'),script_sha256=sha(__file__),
        candidates=[dict(**candidate,full_split_measurement={k:dict(v) for k,v in result[candidate['training']['actual_vocab_size']].items()},
                         train_sources={k:dict(v) for k,v in sources[candidate['training']['actual_vocab_size']].items()}) for candidate in comparison['candidates']],
        neural_updates=0,production_frozen=False,
        scope='Full admitted train/validation/test token efficiency and exact byte round-trip. Fitting uses checked train records only. Split messages are deduplicated by exact complete text for token counts, not substring/semantic deduplication. Heldout measurements do not certify conversation quality, factual correctness or independently human-reviewed content. Handcrafted styles/JSON/product slices are development checks only.')
    with output.open('x') as f:f.write(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({size:{k:dict(v) for k,v in splits.items()} for size,splits in result.items()},indent=2),flush=True)


if __name__=='__main__':main()
