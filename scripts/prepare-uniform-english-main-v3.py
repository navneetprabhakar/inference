"""Keep both finite main sources present through cooldown without adding exposure."""
# Creator: Navneet Prabhakar
import json
from math import gcd
from pathlib import Path
from collections import Counter
import numpy as np
from slm.common.training import Recipe
from slm.data.english_foundation_adapter import build_mixture, build_curriculum
from slm.data.mixture import SCHEDULE
from slm.data.english_corpus import save
from slm.data.stream_hash import sha


def main():
    out=Path('data/english-uniform-language-v3')
    if out.exists():raise FileExistsError('Retain prior uniform-main preparation')
    corpus=Path('data/english-recovery-corpus-v1');tok=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    previous=json.loads(Path('data/english-balanced-experiment-v2/plan.json').read_text())
    prep=json.loads((corpus/'preparation.json').read_text())
    amounts={s:prep['preparation'][s]['processed_positions'] for s in ['general','narrative']}
    divisor=gcd(*amounts.values());weights={s:n//divisor for s,n in amounts.items()}
    out.mkdir();parts={s:str(corpus/s) for s in amounts}
    components=[dict(id=s,path=parts[s],dataset_hash=sha(corpus/s/'manifest.json'),weight=weights[s],
                     max_passes=2,max_positions=2*amounts[s]) for s in amounts]
    budget=2*sum(amounts.values())
    result=build_mixture(components,tok,out/'mixture',objective='foundation',budget=budget,minimum=budget,
                         group_cap=100000,seed='english-recovery-language-v1',allowed_categories=('unreviewed',))
    # Same component/batch/pass multiset and per-component order as the old stream.
    old=np.fromfile(corpus/'language-mixture/schedule.bin',dtype=SCHEDULE)
    new=np.fromfile(out/'mixture/schedule.bin',dtype=SCHEDULE)
    for ci in range(2):
        a=old[old['component']==ci];b=new[new['component']==ci]
        if not np.array_equal(a[['batch','pass','length','supervised']],b[['batch','pass','length','supervised']]):
            raise ValueError('Uniform correction changed source batches/order/exposure')
    spent=Counter();error=0;denominator=sum(weights.values())
    for i,row in enumerate(new):
        source=list(amounts)[int(row['component'])];spent[source]+=int(row['length'])
        if (i+1)%8==0 or i+1==len(new):
            delta=abs(spent['general']*denominator-sum(spent.values())*weights['general'])
            error=max(error,delta)
    if error>1024*denominator:raise ValueError('Uniform source balance exceeds one context at update boundaries')
    schedule=json.loads((Path('data/english-recovery-experiment-v1/curriculum/report.json')).read_text())['stages'][0]['schedule']
    curriculum=build_curriculum([dict(id='language',path=str(out/'mixture'),components=parts,
                                     dataset_hash=sha(out/'mixture/manifest.json'),schedule=schedule)],
                                tok,out/'curriculum',recipe=Recipe(**previous['recipe']),family_processed_cap=100000)
    report=dict(creator='Navneet Prabhakar',complete=True,weights=weights,source_positions=dict(spent),
                processed_positions=budget,optimizer_updates=curriculum['optimizer_updates'],
                maximum_source_position_imbalance_at_update_boundary=error/denominator,
                source_batches_passes_and_each_source_order_unchanged=True,source_passes=2,
                maximum_family_processed_positions=result['max_family_metric_positions'],
                scope='New main source-interleaving metadata only, same complete batches, two passes, exposure, source protection and numerical schedule. Not new gradients or permission to bypass CUDA/local quality gates.',
                requires_separate_main_extension_contract=True,cloud_ready=False,
                mixture_sha256=sha(out/'mixture/manifest.json'),curriculum_sha256=sha(out/'curriculum/manifest.json'),
                bindings=dict(language=dict(path=str(out/'mixture'),components=parts)),
                inputs={str(p):sha(p) for p in [__file__,corpus/'preparation.json',corpus/'language-mixture/manifest.json',
                                              Path('data/english-balanced-experiment-v2/plan.json')]})
    save(out/'report.json',report);save('reports/english-uniform-language-v3.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
