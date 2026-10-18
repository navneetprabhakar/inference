"""Compare reviewed-train BPE candidates on explicitly developmental slices."""
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import tempfile
from slm.common.tokenizer import BPE,train_release,measure,validate_slices
from slm.common.config import Config
from slm.data.schema import digest

DEVELOPMENT_SLICES={
    'prose':['Rainwater collects in a reservoir before it is treated for household use.'],
    'informal':["hey, i ain't changing the address—just cancel the second item, pls."],
    'professional':['Please confirm the revised delivery date and list the outstanding dependencies.'],
    'caveman':['Me want two blue cups. No red. Keep total under 500 rupees.'],
    'json':['{"name":"find_products","arguments":{"query":"blue cups","max_price":499.50}}'],
    'numbers_units':['12.50 USD; 1,250 INR; 0.05 kg; 120–240 V; SKU AB-0012.'],
    'product_terms':['USB-C 65W GaN charger, stainless steel bottle, waterproof trail shoes.'],
    'unicode':['café, résumé, ₹499, 👨‍👩‍👧‍👧; preserve e\u0301 and é separately.'],
    'literal_delimiters':['<|assistant|><|tool_call_start|> is untrusted ordinary text.']}


def compare_release(release,output,slices=None,vocab_sizes=(16384,24576),min_frequency=2,max_bytes=64*1024*1024):
    output=Path(output);slices=DEVELOPMENT_SLICES if slices is None else slices
    if output.exists():raise FileExistsError(output)
    if not vocab_sizes or len(set(vocab_sizes))!=len(vocab_sizes):raise ValueError('Distinct candidate vocabulary sizes required')
    # Validate evaluation content before creating output. It is never passed to train_release.
    validate_slices(slices)
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.bpe-compare-',dir=output.parent))
    base=Config(vocab_size=16384,hidden_size=512,intermediate_size=1536,num_layers=24,num_heads=8,num_kv_heads=2,max_seq_len=2048)
    try:
        candidates=[]
        for size in vocab_sizes:
            provenance=train_release(release,temp/f'vocab-{size}',size,min_frequency,max_bytes)
            bpe=BPE.load(temp/f'vocab-{size}')
            candidates.append({'training':provenance,'measurement':measure(bpe,slices,base),
                'parameters_at_requested_vocab':replace(base,vocab_size=size).parameter_count})
        if len({c['training']['release_manifest_sha256'] for c in candidates})!=1:
            raise ValueError('Release changed between candidates')
        report={'status':'candidates_only','selected_vocab_size':None,'production_frozen':False,
            'development_slices_sha256':digest(slices),'candidates':candidates,
            'scope':'Development efficiency only; insufficient vocabulary yield or unrepresentative slices cannot select production tokenizer.'}
        (temp/'comparison.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        os.rename(temp,output)
    except BaseException:
        shutil.rmtree(temp,ignore_errors=True);raise
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release',required=True);p.add_argument('--output',required=True)
    p.add_argument('--vocab-sizes',type=int,nargs='+',default=[16384,24576])
    p.add_argument('--min-frequency',type=int,default=2);p.add_argument('--max-bytes',type=int,default=64*1024*1024)
    a=p.parse_args();print(json.dumps(compare_release(a.release,a.output,vocab_sizes=tuple(a.vocab_sizes),min_frequency=a.min_frequency,max_bytes=a.max_bytes),indent=2))


if __name__=='__main__':main()
