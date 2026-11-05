"""Count actual target volume by annotation level and report simple hypothesis-only cues."""
from collections import Counter,defaultdict
import json,re
from build import DEST,HERE,norm,load
def main():
    tok=load();groups={};cue=Counter();total=Counter()
    for split,name in [('train','train.jsonl'),('validation','internal-validation.jsonl')]:
        stats={}
        for line in (DEST/name).open():
            r=json.loads(line);tier=r['annotation_tier']
            d=stats.setdefault(tier,dict(pairs=0,raw_input_positions=0,p=set(),unique={}))
            d['pairs']+=1
            for i,t in enumerate([r['premise'],r['hypothesis']]):
                n=norm(t);count=len(tok.encode(t).ids);d['raw_input_positions']+=count
                d['unique'].setdefault(n,count)
                if i==0:d['p'].add(n)
            k=(split,tier,r['label']);total[k]+=1
            if re.search(r"\b(no|not|never|nobody|none|without|no one|isn't|aren't)\b",r['hypothesis'],re.I):cue[k]+=1
        groups[split]={k:dict(pairs=d['pairs'],raw_input_positions=d['raw_input_positions'],unique_inputs=len(d['unique']),
                               unique_premises=len(d['p']),unique_input_positions=sum(d['unique'].values()),
                               unique_premise_positions=sum(d['unique'][s] for s in d['p'])) for k,d in stats.items()}
    res=dict(annotation_volume=groups,negation_in_hypothesis={'/'.join(k):[cue[k],v] for k,v in total.items()})
    (HERE/'profile.json').write_text(json.dumps(res,indent=2)+'\n');print(json.dumps(groups))
if __name__=='__main__':main()
