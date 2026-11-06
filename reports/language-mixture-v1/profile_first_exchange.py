"""Count-only prospective first-complete-exchange opportunity; no extraction/admission."""
import os
os.environ['TOKENIZERS_PARALLELISM']='false'
os.environ['OMP_NUM_THREADS']='1'
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fixed_mixture_filters',HERE/'build.py')
source=importlib.util.module_from_spec(spec);spec.loader.exec_module(source)


def main():
    start=time.monotonic()
    data=source.DATA
    policy_path=data/'first-exchange-profile-v1-policy.json'
    result_path=data/'first-exchange-profile-v1.json'
    if policy_path.exists() or result_path.exists():raise FileExistsError('profile already exists')
    snapshot=source.ROOT.parent/'inference-snapshot-20261105-c5b911b/data'
    paths=[snapshot/'sft-v1/raw/smol-smoltalk.parquet',snapshot/'sft-v3/raw/smol-smoltalk-1.parquet']
    files=[]
    for path in paths:
        receipt=json.loads((path.parent/'receipt.json').read_text())
        if source.base.checksum(path)!=receipt['sha256']:raise ValueError('source hash mismatch')
        files.append(dict(path=str(path),sha256=receipt['sha256'],revision=receipt['revision']))
    policy=dict(version='first-complete-exchange-profile-v1',scope='Counts only. No candidate rows, token streams, source excerpts or admission decisions are written.',
                source_files=files,source_constituent='smol-magpie-ultra-short',
                parent_policy='Complete2..8 alternating user/assistant turns; apply unchanged v1 privacy/scope/encoding and external-action filters to FULL parent conversation.',
                pair_policy='Count the first complete user message and assistant message, verbatim with role labels. Do not truncate either utterance. 48..511GPT2tokens plus EOT, assistant<=128GPT2tokens.',
                group_policy='Same source-family hash split as v1; stable full-parent identity is pinned rawfileSHA plus rowindex. Only count each exact normalized first exchange once; no near-dedup, historical/root custody or new quality admission claimed.',
                budgets=dict(cpu_threads=1,seconds=600,additional_bytes=1048576),
                builder_sha256=source.base.checksum(HERE/'build.py'),profiler_sha256=source.base.checksum(Path(__file__)))
    source.write(policy_path,policy)
    tok=source.load();counts=Counter();seen=set();families=set();byfile=[]
    for file in files:
        scanned=0;eligible=0
        for batch in pq.ParquetFile(file['path']).iter_batches(batch_size=128,use_threads=False):
            if time.monotonic()-start>600:raise RuntimeError('10minute count-only profile cap')
            if (source.ROOT/'runs/STOP').exists() or (data/'STOP').exists():raise RuntimeError('explicit STOP')
            for row in batch.to_pylist():
                scanned+=1;counts['scanned_parent_conversations']+=1
                messages=row['messages']
                if row['source']!='smol-magpie-ultra-short' or not 2<=len(messages)<=8 or len(messages)%2:
                    counts['reject_source_or_parent_turn_count']+=1;continue
                if any(m.get('role')!=('user' if i%2==0 else 'assistant') or not isinstance(m.get('content'),str) or not m['content'].strip() for i,m in enumerate(messages)):
                    counts['reject_parent_roles']+=1;continue
                full='\n'.join(m['role'].capitalize()+': '+m['content'].strip() for m in messages)
                if source.CONTACT.search(full) or source.CHAT_BAD.search(full) or source.base.CONTROL.search(full) or any(source.EXTERNAL.search(m['content']) for m in messages if m['role']=='assistant'):
                    counts['reject_full_parent_scope']+=1;continue
                pair='\n'.join(m['role'].capitalize()+': '+m['content'].strip() for m in messages[:2])
                n=len(tok.encode(pair).ids)+1
                if not 49<=n<=512 or len(tok.encode(messages[1]['content']).ids)>128:
                    counts['reject_first_exchange_length']+=1;continue
                key=source.sha(source.base.normalized(pair))
                if key in seen:counts['reject_exact_pair_duplicate']+=1;continue
                seen.add(key)
                opening=source.base.normalized(messages[0]['content'])
                opening=source.re.sub(r'\b\d+(?:\.\d+)?\b','<number>',opening)
                opening=source.re.sub(r'"[^"\n]*"','<quoted>',opening)
                group=source.sha(opening)
                split='validation' if int(source.sha(source.SALT+'dialogue'+group)[:12],16)%50==0 else 'train'
                counts[split+'_conversations']+=1;counts[split+'_tokens']+=n
                families.add((split,group));eligible+=1
        byfile.append(dict(path=file['path'],scanned=scanned,eligible_unique_pairs=eligible))
    result=dict(state='profile_only_not_admitted',policy_sha256=source.base.checksum(policy_path),counts=dict(counts),
                families=dict(Counter(split for split,group in families)),byfile=byfile,
                training_target=20000000,pre_custody_train_shortfall=max(0,20000000-counts['train_tokens']),
                limitations='Counts are an upper bound on admissible text: no prior-near-duplicate/custody or independent quality screening. Entire parent identity and family must govern any future extraction split. No data extracted.',
                seconds=time.monotonic()-start)
    source.write(result_path,result)
    print(json.dumps(result))


if __name__=='__main__':main()
