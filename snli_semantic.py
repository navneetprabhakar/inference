"""Opt-in directed NLI pairs. No chat formatting and no default training hook."""
from functools import lru_cache
from hashlib import sha256,file_digest
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DEST=ROOT/'data/snli-semantic'
REPORT=ROOT/'reports/snli-semantic'
@lru_cache(maxsize=2)
def _checked(split):
    name={'train':'train.jsonl','validation':'internal-validation.jsonl'}[split]
    f=DEST/name
    with f.open('rb') as stream:
        if file_digest(stream,'sha256').hexdigest()!=json.loads((REPORT/'receipt.json').read_text())['splits'][split]['sha256']:
            raise ValueError('SNLI artifact digest mismatch')
    return f

def _pairs(split,seed,include_single,limit,balanced):
    """Return original relation records sorted by seeded deterministic digest."""
    if limit is not None and limit<0:raise ValueError('limit must be nonnegative')
    rows=[]
    with _checked(split).open() as stream:
        for line in stream:
            row=json.loads(line)
            if row['split']!=split or row['official_split']!='train':raise ValueError('Unexpected split')
            if include_single or row['annotation_tier']=='multi-unanimous': rows.append(row)
    rows.sort(key=lambda r:sha256((str(seed)+'/'+r['pair_id']).encode()).digest())
    if balanced:
        counts={label:sum(r['label']==label for r in rows) for label in ['entailment','neutral','contradiction']}
        quota=min(counts.values())
        if limit is not None:quota=min(quota,limit//3)
        taken=dict.fromkeys(counts,0)
        result=[]
        for r in rows:
            k=r['label']
            if taken[k]<quota:
                taken[k]+=1
                result.append(r)
        return result
    return rows if limit is None else rows[:limit]

def training_pairs(seed,*,include_single=False,limit=None,balanced=False):
    """By default supply independently unanimous original training pairs."""
    return _pairs('train',seed,include_single,limit,balanced)

def validation_pairs(seed,*,include_single=False,limit=None,balanced=False):
    """Separate internal evaluation on whole held-out premise/image families."""
    return _pairs('validation',seed,include_single,limit,balanced)
