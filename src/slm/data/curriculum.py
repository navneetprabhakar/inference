"""Immutable finite curriculum over reviewed token mixtures; no optimizer resets."""
from bisect import bisect_right
from collections import Counter
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from threading import RLock

from slm.data.mixture import MixtureBatches, account, integer
from slm.data.schema import digest
from slm.data.tokenized import sha, stamp


def schedule_recipe(base, schedule):
    if set(schedule)!={'lr','warmup_tokens','accumulation_steps','cooldown_tokens','final_lr_fraction'}:
        raise ValueError('Explicit complete stage schedule required')
    integer(schedule['cooldown_tokens'],minimum=0)
    fraction=schedule['final_lr_fraction']
    if type(fraction) not in (int,float) or not 0<=fraction<=1:
        raise ValueError('Invalid final learning-rate fraction')
    if not schedule['cooldown_tokens'] and fraction!=1:
        raise ValueError('Cooldown fraction requires cooldown positions')
    return replace(base,**{k:schedule[k] for k in ('lr','warmup_tokens','accumulation_steps')})


class _Stages:
    def __init__(self, specs, bindings, tokenizer, recipe, family_cap):
        self.data=[];self.ends=[];self.prefix=[(0,0)];self.recipes=[]
        self.processed=Counter();self.content=Counter();parents={};lineage_bytes=records=0
        try:
            integer(family_cap)
            if not 1<=len(specs)<=16 or len({s['id'] for s in specs})!=len(specs):
                raise ValueError('One to sixteen unique stages required')
            if set(bindings)!={s['id'] for s in specs}:raise ValueError('Stage bindings differ')
            for s in specs:
                if set(s)!={'id','dataset_hash','schedule'} or not re.fullmatch('[a-z][a-z0-9_-]{0,63}',s['id']):
                    raise ValueError('Invalid stage contract')
                if not isinstance(s['dataset_hash'],str) or not re.fullmatch('[a-f0-9]{64}',s['dataset_hash']):
                    raise ValueError('Pinned mixture hash required')
                stage_recipe=schedule_recipe(recipe,s['schedule']);self.recipes.append(stage_recipe)
                binding=bindings[s['id']]
                if set(binding)!={'path','components'}:raise ValueError('Explicit mixture/component bindings required')
                d=MixtureBatches(binding['path'],binding['components'],tokenizer,s['dataset_hash']);self.data.append(d)
                end=(self.ends[-1] if self.ends else 0)+len(d);self.ends.append(end)
                if end>1000000:raise ValueError('Curriculum exceeds one million scheduled batches')
                inv=d.inventory
                records+=sum(len(v) for v in inv.records)
                lineage_bytes+=sum((part.path/'lineage.jsonl').stat().st_size for part in inv.data)
                if records>1000000 or lineage_bytes>128*1024*1024:
                    raise ValueError('Curriculum lineage metadata bound exceeded')
                for part in inv.records:
                    for r in part:
                        parent=r['parent_group_id'];group=r['split_group']
                        if parent in parents and parents[parent]!=group:raise ValueError('Cross-stage parent-family mapping differs')
                        parents[parent]=group
                _,counts,_,t,u=account(inv,d.manifest['components'],d.index,d.manifest['objective'],d.manifest['group_cap'])
                for (ci,ri),v in counts.items():
                    r=inv.records[ci][ri];self.processed[r['split_group']]+=v['processed']
                    self.content[r['content_sha256']]+=1
                if max(self.processed.values())>family_cap:raise ValueError('Cross-stage family processed-position cap exceeded')
                before=self.prefix[-1];self.prefix.append((before[0]+t,before[1]+u))
                if s['schedule']['warmup_tokens']+s['schedule']['cooldown_tokens']>t:
                    raise ValueError('Stage warmup and cooldown overlap or exceed its finite inventory')
        except BaseException:self.close();raise
    def close(self):
        for d in self.data:d.close()


def build_curriculum(stages,tokenizer,output,*,recipe=None,family_processed_cap):
    from slm.common.training import Recipe
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    base=recipe if recipe is not None else Recipe()
    if not isinstance(base,Recipe):raise ValueError('Validated base recipe required')
    bindings={s['id']:{'path':s['path'],'components':s['components']} for s in stages}
    specs=[{k:v for k,v in s.items() if k not in ('path','components')} for s in stages]
    inv=_Stages(specs,bindings,tokenizer,base,family_processed_cap);temp=None
    try:
        report={'stage_order':[s['id'] for s in specs],'processed_positions':inv.prefix[-1][0],
            'supervised_positions':inv.prefix[-1][1],'microbatches':inv.ends[-1],
            'optimizer_updates':sum((len(d)+r.accumulation_steps-1)//r.accumulation_steps for d,r in zip(inv.data,inv.recipes)),
            'max_family_processed_positions':max(inv.processed.values()),'family_processed_cap':family_processed_cap,
            'distinct_content_fingerprints':len(inv.content),'content_fingerprints_in_multiple_stages':sum(v>1 for v in inv.content.values()),
            'scope':'Processed-position exposure across stages; no cross-objective unique-token or semantic-uniqueness claim',
            'stages':[{'id':s['id'],'objective':d.manifest['objective'],'dataset_hash':d.fingerprint,
                'microbatches':len(d),'processed_positions':d.counts(len(d))[0],'supervised_positions':d.counts(len(d))[1],
                'optimizer_updates':(len(d)+r.accumulation_steps-1)//r.accumulation_steps,'schedule':s['schedule']}
                for s,d,r in zip(specs,inv.data,inv.recipes)]}
        manifest={'version':1,'kind':'finite-curriculum-v1','stages':specs,'recipe':asdict(base),
            'tokenizer_hash':inv.data[0].tokenizer_hash,'vocab_size':inv.data[0].vocab_size,
            'family_processed_cap':family_processed_cap,'report_hash':digest(report),
            'builder_sha256':sha(Path(__file__)),'transition':'consume-stage-tail-preserve-global-adam-step-and-moments-v1',
            'lr_clock':'stage-processed-positions-after-update-v1'}
        output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.curriculum-',dir=output.parent))
        (temp/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        manifest['files']={'report.json':sha(temp/'report.json')}
        (temp/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        for d in inv.data:d.counts(0)
        os.rename(temp,output);temp=None
        return {'dataset_hash':sha(output/'manifest.json'),**report}
    finally:
        inv.close()
        if temp is not None:shutil.rmtree(temp,ignore_errors=True)


class CurriculumBatches:
    requires_stage_trainer = True

    def __init__(self,path,bindings,tokenizer,expected_fingerprint=None):
        from slm.common.training import Recipe
        self.path=Path(path);self.lock=RLock();self.closed=False;self.inventory=None;self.stamps={}
        before=stamp(self.path/'manifest.json');self.fingerprint=sha(self.path/'manifest.json')
        m=json.loads((self.path/'manifest.json').read_text())
        if stamp(self.path/'manifest.json')!=before or (expected_fingerprint is not None and self.fingerprint!=expected_fingerprint):
            raise ValueError('Curriculum fingerprint differs')
        if (type(m.get('version')) is not int or m['version']!=1 or m.get('kind')!='finite-curriculum-v1'
            or m.get('transition')!='consume-stage-tail-preserve-global-adam-step-and-moments-v1'
            or m.get('lr_clock')!='stage-processed-positions-after-update-v1'):
            raise ValueError('Unsupported curriculum policy')
        if set(m['files'])!={'report.json'} or {p.name for p in self.path.iterdir()}!={'manifest.json','report.json'}:
            raise ValueError('Curriculum file set differs')
        self.stamps['manifest.json']=before
        identity=stamp(self.path/'report.json')
        if sha(self.path/'report.json')!=m['files']['report.json'] or stamp(self.path/'report.json')!=identity:
            raise ValueError('Curriculum report checksum differs')
        report=json.loads((self.path/'report.json').read_text())
        if digest(report)!=m['report_hash']:raise ValueError('Curriculum report identity differs')
        self.stamps['report.json']=identity
        self.base_recipe=Recipe(**m['recipe'])
        try:
            self.inventory=_Stages(m['stages'],bindings,tokenizer,self.base_recipe,m['family_processed_cap'])
            inv=self.inventory
            if (m['tokenizer_hash'],m['vocab_size'])!=(inv.data[0].tokenizer_hash,inv.data[0].vocab_size):raise ValueError('Curriculum tokenizer metadata differs')
            if (report['processed_positions'],report['supervised_positions'],report['microbatches'])!=(*inv.prefix[-1],inv.ends[-1]):
                raise ValueError('Curriculum totals differ')
            self.manifest=m;self.tokenizer_hash=m['tokenizer_hash'];self.vocab_size=m['vocab_size']
            self.max_length=max(d.max_length for d in inv.data);self.items=self
            self._guard()
        except BaseException:self.close();raise
    def _guard(self):
        if self.closed:raise ValueError('Curriculum is closed')
        for name,identity in self.stamps.items():
            if stamp(self.path/name)!=identity:raise ValueError('Curriculum changed after verification')
        for d in self.inventory.data:d.counts(0)
    def __len__(self):return self.inventory.ends[-1]
    def _position(self,cursor):
        if type(cursor) is not int or not 0<=cursor<=len(self):raise ValueError('Invalid curriculum cursor')
        i=bisect_right(self.inventory.ends,cursor)
        start=0 if i==0 else self.inventory.ends[i-1]
        return i,cursor-start
    def __getitem__(self,index):
        with self.lock:
            self._guard();i,local=self._position(index)
            if i==len(self.inventory.data):raise IndexError('Curriculum exhausted')
            out=self.inventory.data[i][local];self._guard();return out
    def counts(self,cursor):
        with self.lock:
            self._guard();i,local=self._position(cursor);base=self.inventory.prefix[i]
            if i==len(self.inventory.data):return base
            t,s=self.inventory.data[i].counts(local);return base[0]+t,base[1]+s
    def context(self,cursor):
        with self.lock:
            self._guard();i,local=self._position(cursor)
            if i==len(self.inventory.data):raise StopIteration('Curriculum exhausted; no implicit wraparound')
            r=self.inventory.recipes[i];end=min(cursor+r.accumulation_steps,self.inventory.ends[i])
            return r,end,i,local
    def rate(self,cursor,end):
        r,expected,i,local=self.context(cursor)
        if expected!=end:raise ValueError('Update crosses stage boundary')
        start=0 if i==0 else self.inventory.ends[i-1];d=self.inventory.data[i]
        after=d.counts(end-start)[0];total=d.counts(len(d))[0]
        s=self.manifest['stages'][i]['schedule'];cooldown=s['cooldown_tokens']
        scale=1 if not cooldown else s['final_lr_fraction']+(1-s['final_lr_fraction'])*min(1,(total-after)/cooldown)
        return r.rate(after)*scale
    def progress(self,cursor):
        with self.lock:
            self._guard();i,local=self._position(cursor);rows=[];step=0
            for j,(s,d,r) in enumerate(zip(self.manifest['stages'],self.inventory.data,self.inventory.recipes)):
                used=len(d) if j<i else local if j==i else 0
                if used%r.accumulation_steps and used!=len(d):raise ValueError('Curriculum cursor is not an update boundary')
                updates=(used+r.accumulation_steps-1)//r.accumulation_steps;t,u=d.counts(used);step+=updates
                rows.append({'id':s['id'],'dataset_hash':s['dataset_hash'],'cursor':used,'updates':updates,
                    'processed_positions':t,'supervised_positions':u,'status':'complete' if used==len(d) else 'active' if j==i else 'pending'})
            return {'version':1,'plan_hash':self.fingerprint,'next_stage':None if i==len(rows) else rows[i]['id'],
                'completed_stages':i,'global_updates':step,'stages':rows}
    def close(self):
        if self.inventory is not None:self.inventory.close()
        self.closed=True
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def main():
    import argparse
    from slm.common.training import Recipe
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True);p.add_argument('--tokenizer',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();root=Path(a.config).resolve().parent;spec=json.loads(Path(a.config).read_text())
    for s in spec['stages']:
        v=Path(s['path']);s['path']=v if v.is_absolute() else root/v
        s['components']={k:(Path(v) if Path(v).is_absolute() else root/v) for k,v in s['components'].items()}
    if 'recipe' in spec:spec['recipe']=Recipe(**spec['recipe'])
    print(json.dumps(build_curriculum(tokenizer=a.tokenizer,output=a.output,**spec),indent=2))


if __name__=='__main__':main()
