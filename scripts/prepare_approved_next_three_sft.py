"""Build the immutable, auditable Stage-2 SFT mixture; never trains or decodes."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from tokenizers import Tokenizer
from sft_common import ROOT, encode_episode

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p): return [json.loads(x) for x in Path(p).read_text().splitlines() if x]

def main(a):
    cfg=ROOT/'configs/approved_next_three_sft_v1.json'; c=json.loads(cfg.read_text())
    candidate=ROOT/c['candidate']; replay=ROOT/c['tool_replay_source']; out=ROOT/a.output
    if out.exists(): raise RuntimeError('refusing to overwrite frozen mixture: '+str(out))
    cand=rows(candidate)
    if len(cand)!=2345 or len({x.get('id') for x in cand})!=2345: raise RuntimeError('candidate is not validated v2 2345-record projection')
    validation=json.loads((ROOT/'reports/author-review-v2/derived-candidate-validation.json').read_text())
    gates=[not validation['role_structure_failures'],not validation['tokenizer']['failures'],not validation['tokenizer']['role_mask_failures'],not validation['heldout_exact_user_turns'],not validation['heldout_near_user_turns'],validation['normalized_full_duplicate_groups']==0]
    if not all(gates): raise RuntimeError('candidate validation gates failed')
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json')); selected=[]
    for r in rows(replay):
        if r.get('split')!='train' or r.get('source')!='tool': continue
        if encode_episode(tok,r['episode']) is not None: selected.append(r)
        if len(selected)==c['tool_replay_records']: break
    if len(selected)!=c['tool_replay_records']: raise RuntimeError('insufficient permitted train-only tool replay')
    examples=[]
    for p in range(c['max_novel_candidate_passes']): examples += [(r['id'],'candidate',p+1,r['messages']) for r in cand]
    examples += [(r['id'],'tool_replay',0,r['episode']) for r in selected]
    encoded=[]
    for ident,source,pass_no,messages in examples:
        value=encode_episode(tok,messages)
        if value is None: raise RuntimeError('encoding failure '+ident)
        ids,mask,n=value; encoded.append((ids,mask,n,ident,source,pass_no))
    encoded=[encoded[i] for i in np.random.default_rng(c['seed']).permutation(len(encoded))]
    out.mkdir(parents=True)
    np.savez_compressed(out/'episodes.npz',ids=np.stack([x[0] for x in encoded]),mask=np.stack([x[1] for x in encoded]),length=np.array([x[2] for x in encoded],np.int32))
    meta=[{'id':x[3],'source':x[4],'candidate_pass':x[5]} for x in encoded]; (out/'order.json').write_text(json.dumps(meta,separators=(',',':'))+'\n')
    manifest={'kind':'frozen_authorized_stage2_mixture','records':len(meta),'candidate_records':2345,'candidate_exposures':4690,'candidate_passes':2,'tool_replay_records':len(selected),'tool_replay_source':'data/sft-v3/train.jsonl','selection_data_excluded':['data/author-review-v3/development-cases.jsonl','data/author-review-v3/confirmation-cases.jsonl'],'hashes':{'config':sha(cfg),'candidate':sha(candidate),'candidate_validation':sha(ROOT/'reports/author-review-v2/derived-candidate-validation.json'),'tool_replay_source':sha(replay),'tokenizer':sha(ROOT/'data/sft-v3/tokenizer.json'),'episodes':sha(out/'episodes.npz'),'order':sha(out/'order.json')},'license':'source attribution retained; per-row output rights/license unknown and no redistribution claim is made','novel_data':'only candidate rows; maximum two enumerated passes'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n'); print(json.dumps(manifest,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='data/approved-next-three-sft-v1');main(p.parse_args())
