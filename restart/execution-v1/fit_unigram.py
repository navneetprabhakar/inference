import hashlib,json,pathlib
import numpy as np
from slm.restart.baselines import Unigram
O=pathlib.Path(__file__).resolve().parent

def checked(name):
    folder=O/name;manifest=json.loads((folder/'manifest.json').read_text())
    for file,digest in manifest['files'].items():
        if hashlib.sha256((folder/file).read_bytes()).hexdigest()!=digest:raise ValueError('Changed data stream')
    ids=np.memmap(folder/'tokens.u16',dtype='<u2',mode='r')
    if len(ids)!=manifest['targets']:raise ValueError('Target count mismatch')
    return manifest,ids

def main():
    train,tokens=checked('data-train');dev,development=checked('data-dev')
    counts=np.bincount(tokens,minlength=8192).astype(np.uint64)
    if not np.array_equal(counts,np.load(O/'data-train/unigram-counts.npy',allow_pickle=False)):raise ValueError('Independent count mismatch')
    trials=[]
    for alpha in [.01,.1,1.]:
        model=Unigram(counts,alpha);nll=model.score(development)
        trials.append({'alpha':alpha,'development_nll':nll/len(development),'development_bits_per_byte':nll/np.log(2)/dev['scored_utf8_bytes']})
    chosen=min(trials,key=lambda x:x['development_nll'])
    receipt={'status':'PASS','scope':'M1 unigram baseline only; modified Kneser-Ney remains required','training_targets':int(counts.sum()),'development_targets':len(development),'trial_grid_frozen_in_script':[.01,.1,1.],'trials':trials,'selected':chosen,'selection':'lowest development NLL, grid order breaks ties','train_manifest_sha256':hashlib.sha256((O/'data-train/manifest.json').read_bytes()).hexdigest(),'dev_manifest_sha256':hashlib.sha256((O/'data-dev/manifest.json').read_bytes()).hexdigest(),'final_set_opened_or_scored':False,'neural_training':False}
    (O/'unigram-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
