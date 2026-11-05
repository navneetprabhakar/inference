"""Apply approved vote/label strata, conservative overlap removal and honest token accounting."""
from collections import Counter,defaultdict
from functools import lru_cache
from hashlib import sha256,file_digest
from pathlib import Path
import json,zlib,re
from policy import final_stratum
from build import DEST,HERE,norm,digest,load,SHA
def hashfile(p):
    with p.open('rb') as f:return file_digest(f,'sha256').hexdigest()
def near_words(p,h):
    w=p.split()+['|']+h.split()
    return set(zlib.crc32(' '.join(w[i:i+3]).encode()) for i in range(len(w)-2))
def main():
    policy=json.loads((HERE/'admission.json').read_text())
    tok=load();held_text=set();held_pairs=set();held_groups=set();held_images=set()
    checked=[];posting=defaultdict(list);counters=Counter();splits={}
    @lru_cache(maxsize=30000)
    def cost(s):return len(tok.encode(s).ids)
    for split,name in [('validation','internal-validation.jsonl'),('train','train.jsonl')]:
        seen={};p_ids=set();h_ids=set();groups=set();ims=set();counts=Counter();raw=0
        with (DEST/(split+'-candidate.jsonl')).open() as inp,(DEST/name).open('w') as output:
            for line in inp:
                r=json.loads(line);tier=r['annotation_tier']+'/'+r['label']
                if not accepted(r,policy) or r['pair_id'] in policy['held_ids']:continue
                p,h=norm(r['premise']),norm(r['hypothesis'])
                if split=='train' and (p in held_text or h in held_text):
                    counters['validation_sentence_overlap']+=1;continue
                sh=near_words(p,h);sig=sorted(sh)[:8]
                # Near-identical pair boilerplate may occur under different labels, images, or spellings.
                hits=Counter(j for z in sig for j in posting[z])
                if any(n>=4 and len(sh & checked[j])>=.82*max(len(sh),len(checked[j])) for j,n in hits.items()):
                    counters['near_duplicate_pair']+=1;continue
                j=len(checked);checked.append(sh)
                for z in sig:posting[z].append(j)
                if split=='validation':
                    held_text.update((p,h));held_pairs.add(r['pair_sha256']);held_groups.add(r['group']);held_images.add(r['image_id'])
                else:
                    assert r['pair_sha256'] not in held_pairs and r['group'] not in held_groups and r['image_id'] not in held_images
                if p not in seen:seen[p]=cost(r['premise'])
                if h not in seen:seen[h]=cost(r['hypothesis'])
                p_ids.add(p);h_ids.add(h);groups.add(r['group']);ims.add(r['image_id']);counts[tier]+=1
                raw+=cost(r['premise'])+cost(r['hypothesis'])
                output.write(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n')
        splits[split]=dict(pairs=sum(counts.values()),image_ids=len(ims),groups=len(groups),strata=counts,unique_premises=len(p_ids),unique_hypotheses=len(h_ids),
                raw_input_positions=raw,unique_input_texts=len(seen),unique_input_token_positions=sum(seen.values()),
                unique_premise_token_positions=sum(seen[p] for p in p_ids),sha256=hashfile(DEST/name))
    info=dict(published_complete_archive_sha256=SHA,verified_train_member_sha256=json.loads((HERE/'source-recovery.json').read_text())['member_sha256'],splits=splits,near_and_split_exclusions=counters,
              policy_sha256=hashfile(HERE/'admission.json'),status='source admission; protected overlap requires independent custodian')
    (HERE/'receipt.json').write_text(json.dumps(info,indent=2)+'\n'); print(json.dumps(info))
def accepted(r,policy):
    return final_stratum(r) in policy['accept']
if __name__=='__main__':main()
