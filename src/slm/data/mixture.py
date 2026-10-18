"""Finite, hash-bound token mixture schedules with explicit exposure limits."""
from bisect import bisect_right
from collections import Counter,defaultdict
from fractions import Fraction
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from threading import RLock
import numpy as np
from slm.data.schema import digest
from slm.data.tokenized import ShardBatches,sha,stamp
from slm.data.review import CATEGORIES

SCHEDULE=np.dtype([('component','<u4'),('batch','<u8'),('pass','<u4'),('length','<u4'),
                   ('supervised','<u4'),('prefix_tokens','<u8'),('prefix_supervised','<u8')])


def integer(v,minimum=1,maximum=2**53):
    if type(v) is not int or not minimum<=v<=maximum:raise ValueError('Bounded integer required')
    return v


def stats(data,index):
    before=data.counts(index);after=data.counts(index+1)
    return after[0]-before[0],after[1]-before[1],before[0]


class Inventory:
    def __init__(self,components,paths,tokenizer,objective,categories,max_batches):
        self.data=[];self.records=[];self.ends=[];self.batch_stats=[]
        seen_datasets=set();seen_content=set();seen_ids=set();seen_examples=set();parent_groups={};lineage_bytes=0;record_count=0
        try:
            if not 1<=len(components)<=16 or [c['id'] for c in components]!=sorted(c['id'] for c in components):
                raise ValueError('One to sixteen canonically ordered components required')
            for c in components:
                if set(c)!={'id','dataset_hash','weight','max_passes','max_positions'} or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',c['id']) or c['id'] in seen_ids:
                    raise ValueError('Unique canonical component identities required')
                if not isinstance(c['dataset_hash'],str) or not re.fullmatch('[a-f0-9]{64}',c['dataset_hash']):raise ValueError('Pinned component dataset hash required')
                seen_ids.add(c['id']);integer(c['weight'],maximum=1000000);integer(c['max_passes'],maximum=2);integer(c['max_positions'])
                d=ShardBatches(paths[c['id']],tokenizer,expected_fingerprint=c['dataset_hash']);self.data.append(d)
                if d.fingerprint in seen_datasets:raise ValueError('Overlapping dataset components')
                seen_datasets.add(d.fingerprint)
                if d.manifest.get('lineage_schema')!='record-content-spans-v2':raise ValueError('Mixing requires content-hashed lineage; reprepare legacy shards')
                if d.manifest['objective']!=objective or not set(d.manifest['allowed_categories'])<=set(categories):raise ValueError('Mixture objective/category differs')
                if sum(len(v) for v in self.batch_stats)+len(d)>max_batches:raise ValueError('Inventory exceeds batch metadata bound')
                rows=[];ends=[];cursor=0;supervised=0;sources=set()
                lineage_bytes+=(d.path/'lineage.jsonl').stat().st_size
                if lineage_bytes>128*1024*1024:raise ValueError('Lineage metadata exceeds explicit 128MiB bound')
                for line in (d.path/'lineage.jsonl').open():
                    record_count+=1
                    if record_count>1000000:raise ValueError('Lineage exceeds explicit record bound')
                    r=json.loads(line)
                    if r['split']!='train' or not all(isinstance(r.get(k),str) and r[k] for k in ('example_id','split_group','parent_group_id','source')):
                        raise ValueError('Invalid train lineage')
                    if r['example_id'] in seen_examples:raise ValueError('Duplicate record identity across inventory')
                    seen_examples.add(r['example_id'])
                    if not re.fullmatch('[a-f0-9]{64}',r.get('content_sha256','')):raise ValueError('Invalid content fingerprint')
                    if r['content_sha256'] in seen_content:raise ValueError('Duplicate content across mixture inventory')
                    seen_content.add(r['content_sha256'])
                    n=integer(r['prediction_positions']);s=integer(r['supervised_positions'],maximum=n)
                    rows.append({**r,'start':cursor,'end':cursor+n});cursor+=n;supervised+=s;ends.append(cursor)
                    parent=r['parent_group_id']
                    if parent in parent_groups and parent_groups[parent]!=r['split_group']:raise ValueError('Inconsistent parent-family mapping across inventory')
                    parent_groups[parent]=r['split_group']
                    sources.add(r['source'])
                if (not rows or len(sources)!=1 or cursor!=d.manifest['processed_tokens'] or supervised!=d.manifest['supervised_tokens']):
                    raise ValueError('Lineage totals or single-source identity differs')
                self.records.append(rows);self.ends.append(ends)
                sizes=[stats(d,i) for i in range(len(d))];self.batch_stats.append(sizes)
                # SFT has exactly one whole record per batch; foundation masks supervise all positions.
                if objective=='sft':
                    if len(rows)!=len(sizes) or any((r['end']-r['start'],r['supervised_positions'],r['start'])!=v for r,v in zip(rows,sizes)):
                        raise ValueError('SFT record/batch alignment differs')
                elif any(n!=s for n,s,_ in sizes):raise ValueError('Foundation masks differ')
        except BaseException:self.close();raise
    def parts(self,component,batch,objective):
        n,s,start=self.batch_stats[component][batch];end=start+n
        if objective=='sft':return [(batch,n,s)]
        records=self.records[component];i=bisect_right(self.ends[component],start);out=[]
        while i<len(records) and records[i]['start']<end:
            count=min(end,records[i]['end'])-max(start,records[i]['start']);out.append((i,count,count));i+=1
        if sum(v[1] for v in out)!=n:raise ValueError('Lineage does not cover batch')
        return out
    def close(self):
        for d in self.data:d.close()


def account(inventory,components,rows,objective,group_cap):
    source=[Counter() for c in components];seen=Counter();groups=Counter();record_counts=defaultdict(Counter)
    tokens=supervised=0
    for row in rows:
        ci,bi,pass_,n,s,pt,ps=(int(row[k]) for k in SCHEDULE.names)
        if not 0<=ci<len(components) or not 0<=bi<len(inventory.data[ci]):raise ValueError('Invalid scheduled component/batch')
        if (n,s)!=(inventory.batch_stats[ci][bi][:2]) or (pt,ps)!=(tokens,supervised):raise ValueError('Schedule counts differ')
        seen[ci,bi]+=1
        if pass_!=seen[ci,bi]-1 or seen[ci,bi]>components[ci]['max_passes']:raise ValueError('Schedule repeats exceed declared passes')
        metric=n if objective=='foundation' else s
        source[ci].update(processed=n,supervised=s,batches=1,metric=metric)
        if source[ci]['metric']>components[ci]['max_positions']:raise ValueError('Component token cap exceeded')
        for ri,pred,sup in inventory.parts(ci,bi,objective):
            r=inventory.records[ci][ri];key=r['split_group'];groups[key]+=pred if objective=='foundation' else sup
            if groups[key]>group_cap:raise ValueError('Family token cap exceeded')
            record_counts[ci,ri].update(processed=pred,supervised=sup)
            if seen[ci,bi]==1:record_counts[ci,ri].update(unique_prepared_processed=pred,unique_prepared_supervised=sup)
        tokens+=n;supervised+=s
    return source,record_counts,groups,tokens,supervised


def build_mixture(components,tokenizer,output,*,objective,budget,minimum,group_cap,seed='0',max_batches=1000000,allowed_categories=('sfw',)):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    integer(budget);integer(minimum,maximum=budget);integer(group_cap);integer(max_batches,maximum=1000000)
    if objective not in ('foundation','sft') or not isinstance(seed,str) or not seed or len(seed)>128:raise ValueError('Explicit objective/seed required')
    if not allowed_categories or len(set(allowed_categories))!=len(allowed_categories) or not set(allowed_categories)<=CATEGORIES:raise ValueError('Explicit categories required')
    paths={c['id']:c['path'] for c in components}
    specs=sorted([{k:v for k,v in c.items() if k!='path'} for c in components],key=lambda c:c['id'])
    if len(paths)!=len(specs):raise ValueError('Duplicate component identity')
    inv=Inventory(specs,paths,tokenizer,objective,allowed_categories,max_batches)
    temp=None
    try:
        # SHA sorting fixes order independently of NumPy RNG/library versions.
        orders=[]
        for ci,c in enumerate(specs):
            orders.append([(bi,p) for p in range(c['max_passes']) for bi in sorted(range(len(inv.data[ci])),
                key=lambda b:(digest([seed,c['dataset_hash'],p,b]),b))])
        positions=[0]*len(specs);spent=[0]*len(specs);families=Counter();rows=[];tokens=supervised=metric_total=0;excluded=Counter()
        while True:
            candidates=[]
            for ci,c in enumerate(specs):
                while positions[ci]<len(orders[ci]):
                    bi,p=orders[ci][positions[ci]];n,s,_=inv.batch_stats[ci][bi];cost=n if objective=='foundation' else s
                    additions=Counter()
                    for ri,pred,sup in inv.parts(ci,bi,objective):additions[inv.records[ci][ri]['split_group']]+=pred if objective=='foundation' else sup
                    reason=('total_budget' if metric_total+cost>budget else 'component_cap' if spent[ci]+cost>c['max_positions'] else
                            'family_cap' if any(families[g]+v>group_cap for g,v in additions.items()) else None)
                    if reason:
                        excluded[reason]+=1;positions[ci]+=1;continue
                    candidates.append((Fraction(spent[ci]+cost,c['weight']),ci,bi,p,n,s,cost,additions));break
            if not candidates:break
            _,ci,bi,p,n,s,cost,additions=min(candidates,key=lambda x:(x[0],x[1]))
            if len(rows)>=max_batches:raise ValueError('Schedule exceeds batch metadata bound')
            rows.append((ci,bi,p,n,s,tokens,supervised));tokens+=n;supervised+=s;metric_total+=cost
            positions[ci]+=1;spent[ci]+=cost;families.update(additions)
        if metric_total<minimum:raise ValueError('Insufficient eligible inventory under exposure/budget caps')
        array=np.array(rows,dtype=SCHEDULE)
        per_source,records,groups,checked_t,checked_s=account(inv,specs,array,objective,group_cap)
        assert (checked_t,checked_s)==(tokens,supervised)
        report={'objective':objective,'weight_basis':'processed_positions' if objective=='foundation' else 'supervised_positions',
            'planned_processed_positions':tokens,'planned_supervised_positions':supervised,'planned_metric_positions':metric_total,
            'budget':budget,'minimum':minimum,'unfilled_budget':budget-metric_total,'batches':len(rows),'excluded_candidates':dict(excluded),
            'unique_prepared_processed_positions':sum(v['unique_prepared_processed'] for v in records.values()),
            'unique_prepared_supervised_positions':sum(v['unique_prepared_supervised'] for v in records.values()),
            'record_identities_touched':len(records),'families_touched':len(groups),'max_family_metric_positions':max(groups.values()),
            'components':{c['id']:{**dict(per_source[i]),'realized_metric_fraction':spent[i]/metric_total,
                'requested_weight':c['weight'],'max_positions':c['max_positions'],'max_passes':c['max_passes']} for i,c in enumerate(specs)},
            'scope':'Finite prepared-position exposure, not lexical/semantic unique tokens or shared-prefix deduplication',
            'reallocation':'Weighted virtual finish time among remaining eligible sources; explicit component/family/pass caps always apply',
            'implicit_wraparound':False,'partial_batch_truncation':False}
        report['repeated_processed_positions']=tokens-report['unique_prepared_processed_positions']
        output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.mixture-',dir=output.parent))
        array.tofile(temp/'schedule.bin')
        with (temp/'exposure.jsonl').open('w') as f:
            for (ci,ri),counts in sorted(records.items()):
                r=inv.records[ci][ri]
                f.write(json.dumps({'component':specs[ci]['id'],'example_id':r['example_id'],'split_group':r['split_group'],
                    'content_sha256':r['content_sha256'],**dict(counts)},sort_keys=True)+'\n')
        (temp/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        manifest={'version':1,'kind':'finite-token-mixture-v1','components':specs,'objective':objective,
            'allowed_categories':sorted(allowed_categories),'budget':budget,'minimum':minimum,'group_cap':group_cap,'seed':seed,'max_batches':max_batches,
            'tokenizer_hash':inv.data[0].tokenizer_hash,'vocab_size':inv.data[0].vocab_size,'batches':len(rows),
            'processed_tokens':tokens,'supervised_tokens':supervised,'max_length':int(array['length'].max()),'index_dtype':SCHEDULE.descr,
            'builder_sha256':sha(__file__),'files':{p.name:sha(p) for p in sorted(temp.iterdir())}}
        # Recheck inputs before atomic publication; numeric payloads remain lazily checked by readers.
        for d in inv.data:d.counts(0)
        (temp/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n');os.rename(temp,output);temp=None
        return {'dataset_hash':sha(output/'manifest.json'),**report}
    finally:
        inv.close()
        if temp is not None:shutil.rmtree(temp,ignore_errors=True)


class MixtureBatches:
    def __init__(self,path,components,tokenizer,expected_fingerprint=None):
        self.path=Path(path);self.lock=RLock();self.closed=False;self.inventory=None;self.index=None
        self.stamps={};before=stamp(self.path/'manifest.json');self.fingerprint=sha(self.path/'manifest.json')
        m=json.loads((self.path/'manifest.json').read_text())
        if stamp(self.path/'manifest.json')!=before or (expected_fingerprint is not None and expected_fingerprint!=self.fingerprint):raise ValueError('Mixture fingerprint differs')
        if (type(m.get('version')) is not int or m.get('version')!=1 or m.get('kind')!='finite-token-mixture-v1' or m.get('objective') not in ('foundation','sft')
            or m.get('index_dtype')!=json.loads(json.dumps(SCHEDULE.descr))):raise ValueError('Unsupported mixture contract')
        for k in ('budget','minimum','group_cap','max_batches','batches'):integer(m[k])
        if m['minimum']>m['budget'] or m['max_batches']>1000000 or m['batches']>m['max_batches']:raise ValueError('Invalid mixture bounds')
        if not m['allowed_categories'] or not set(m['allowed_categories'])<=CATEGORIES:raise ValueError('Invalid mixture categories')
        self.stamps['manifest.json']=before
        if set(m['files'])!={'schedule.bin','exposure.jsonl','report.json'} or {p.name for p in self.path.iterdir()}!={*m['files'],'manifest.json'}:raise ValueError('Mixture file set differs')
        for name,expected in m['files'].items():
            identity=stamp(self.path/name)
            if sha(self.path/name)!=expected or stamp(self.path/name)!=identity:raise ValueError('Mixture checksum differs')
            self.stamps[name]=identity
        if (self.path/'schedule.bin').stat().st_size!=m['batches']*SCHEDULE.itemsize:raise ValueError('Mixture index size differs')
        try:
            if set(components)!={c['id'] for c in m['components']}:raise ValueError('Mixture component mapping differs')
            self.inventory=Inventory(m['components'],components,tokenizer,m['objective'],m['allowed_categories'],m['max_batches'])
            self.index=np.memmap(self.path/'schedule.bin',dtype=SCHEDULE,mode='r',shape=(m['batches'],))
            _,_,_,t,s=account(self.inventory,m['components'],self.index,m['objective'],m['group_cap'])
            metric=t if m['objective']=='foundation' else s
            if (t,s)!=(m['processed_tokens'],m['supervised_tokens']) or not m['minimum']<=metric<=m['budget'] or int(self.index['length'].max())!=m['max_length']:
                raise ValueError('Mixture accounting differs')
            first=self.inventory.data[0]
            if (first.tokenizer_hash,first.vocab_size)!=(m['tokenizer_hash'],m['vocab_size']):raise ValueError('Mixture tokenizer metadata differs')
            self.manifest=m;self.vocab_size=first.vocab_size;self.tokenizer_hash=first.tokenizer_hash;self.max_length=m['max_length'];self.items=self
        except BaseException:self.close();raise
    def _guard(self):
        if self.closed:raise ValueError('Mixture is closed')
        for name,identity in self.stamps.items():
            if stamp(self.path/name)!=identity:raise ValueError('Mixture changed after verification')
        for d in self.inventory.data:d.counts(0)
    def __len__(self):return self.manifest['batches']
    def __getitem__(self,index):
        with self.lock:
            self._guard()
            if type(index) is not int or not 0<=index<len(self):raise IndexError('Invalid mixture batch')
            row=self.index[index];out=self.inventory.data[int(row['component'])][int(row['batch'])]
            self._guard();return out
    def counts(self,cursor):
        with self.lock:
            self._guard()
            if type(cursor) is not int or not 0<=cursor<=len(self):raise ValueError('Invalid mixture cursor')
            if not cursor:return 0,0
            row=self.index[cursor-1];return int(row['prefix_tokens'])+int(row['length']),int(row['prefix_supervised'])+int(row['supervised'])
    def close(self):
        if self.inventory is not None:self.inventory.close()
        self.index=None;self.closed=True
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True);p.add_argument('--tokenizer',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();root=Path(a.config).resolve().parent;spec=json.loads(Path(a.config).read_text())
    components=spec.pop('components')
    for c in components:
        path=Path(c['path']);c['path']=path if path.is_absolute() else root/path
    print(json.dumps(build_mixture(components,a.tokenizer,a.output,**spec),indent=2))


if __name__=='__main__':main()
