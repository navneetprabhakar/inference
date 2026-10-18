"""Verified train-only token shards, deterministic framing and disk-backed batches."""
from collections import Counter,defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from threading import RLock
import numpy as np
from slm.common.tokenizer import BPE,STRUCTURAL
from slm.data.review import training_examples,CATEGORIES
from slm.data.build import verify
from slm.data.schema import digest

INDEX=np.dtype([('shard','<u4'),('offset','<u8'),('length','<u4'),('supervised','<u4'),
                ('prefix_tokens','<u8'),('prefix_supervised','<u8')],align=False)
DTYPES={'x':'<u4','y':'<u4','loss':'u1'}


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()


def stamp(path):
    stat=Path(path).stat();return stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_ino


class Writer:
    def __init__(self,root,shard_positions,max_positions):
        self.root=root;self.limit=shard_positions;self.max_positions=max_positions
        (root/'shards').mkdir();self.index=(root/'index.bin').open('wb')
        self.buffers={k:[] for k in DTYPES};self.positions=0;self.shards=[]
        self.batches=0;self.processed=0;self.supervised=0;self.shard_supervised=0
    def add(self,x,y,mask):
        if len(x)>self.limit:raise ValueError('Single batch exceeds shard position limit')
        if self.processed+len(x)>self.max_positions:raise ValueError('Tokenization exceeds explicit position budget; no partial corpus')
        if self.positions and self.positions+len(x)>self.limit:self.flush()
        supervised=int(sum(mask))
        if not len(x) or not supervised:raise ValueError('Nonempty supervised batch required')
        np.array([(len(self.shards),self.positions,len(x),supervised,self.processed,self.supervised)],dtype=INDEX).tofile(self.index)
        for name,values in zip(DTYPES,(x,y,mask)):self.buffers[name].append(np.asarray(values,dtype=DTYPES[name]))
        self.positions+=len(x);self.processed+=len(x);self.supervised+=supervised
        self.shard_supervised+=supervised;self.batches+=1
    def flush(self):
        if not self.positions:return
        number=len(self.shards);files={}
        for name in DTYPES:
            filename=f'shards/{number:06d}-{name}.bin'
            np.concatenate(self.buffers[name]).astype(DTYPES[name],copy=False).tofile(self.root/filename)
            files[name]=filename
        self.shards.append({'positions':self.positions,'supervised':self.shard_supervised,'files':files})
        self.buffers={k:[] for k in DTYPES};self.positions=0;self.shard_supervised=0
    def close(self):self.index.close()


def document_tokens(bpe,example,objective,context_length):
    messages=example['messages']
    if example.get('task')=='student_correction':raise ValueError('Continuation-only supervision adapter required for student corrections')
    if any(set(m)!={'role','content'} for m in messages):raise ValueError('Structured message payload requires dedicated tool serializer')
    if len(messages)==1 and messages[0]['role']=='text':
        if objective=='sft':return None,'not_dialogue'
        tokens=bpe.encode(messages[0]['content'])+[STRUCTURAL['eos']]
        return (tokens,[1]*len(tokens)),None
    x,y,mask=bpe.serialize(messages,objective='assistant' if objective=='sft' else 'all')
    if objective=='sft' and len(x)>context_length:return None,'over_context_no_truncation'
    if not any(mask):return None,'no_supervised_targets'
    return (x+[y[-1]],[0]+mask),None


def build_shards(release,tokenizer,output,objective,context_length=1024,shard_positions=262144,
                 max_positions=64000000,allowed_categories=('sfw',),allowed_sources=None):
    release,tokenizer,output=Path(release),Path(tokenizer),Path(output)
    if output.exists():raise FileExistsError(output)
    if objective not in ('foundation','sft'):raise ValueError('Explicit foundation or SFT objective required')
    if any(type(v) is not int or v<1 for v in (context_length,shard_positions,max_positions)) or shard_positions<context_length:
        raise ValueError('Positive context/shard/budget limits required; shard must fit a full context')
    if not allowed_categories or len(set(allowed_categories))!=len(allowed_categories) or not set(allowed_categories)<=CATEGORIES:
        raise ValueError('Explicit supported content-category selection required')
    if allowed_sources is not None and (not allowed_sources or len(set(allowed_sources))!=len(allowed_sources) or not all(isinstance(v,str) and v for v in allowed_sources)):
        raise ValueError('Explicit nonempty source selection required')
    release_hash=sha(release/'manifest.json');tokenizer_hash=sha(tokenizer/'manifest.json')
    bpe=BPE.load(tokenizer)
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.token-shards-',dir=output.parent))
    writer=None
    rejected=Counter();sources=defaultdict(Counter);categories=Counter();groups=set();records=0;encoded=0;buffer=[]
    try:
        writer=Writer(temp,shard_positions,max_positions)
        with (temp/'lineage.jsonl').open('w') as lineage:
            for example in training_examples(release):
                if allowed_sources is not None and example['source'] not in allowed_sources:
                    rejected['source_excluded']+=1;continue
                if example['content_category'] not in allowed_categories:
                    rejected['content_category_excluded']+=1;continue
                # One document is encoded at a time; fail, never silently shorten a large document.
                byte_count=sum(len(m['content'].encode('utf-8')) for m in example['messages'])
                if byte_count>4*1024*1024:raise ValueError('Document exceeds bounded encoding size')
                result,reason=document_tokens(bpe,example,objective,context_length)
                if reason is not None:rejected[reason]+=1;continue
                tokens,mask=result
                contribution=len(tokens)-int(objective=='sft' or encoded==0)
                supervised=contribution if objective=='foundation' else sum(mask[1:])
                record={'example_id':example['example_id'],'record_sha256':digest(example),'content_sha256':digest(example['messages']),'source':example['source'],
                    'source_revision':example['source_revision'],'parent_group_id':example['parent_group_id'],
                    'split_group':example['validation_results']['split_group'],'split':'train',
                    'encoded_positions':len(tokens),'prediction_positions':contribution,'supervised_positions':supervised}
                lineage.write(json.dumps(record,sort_keys=True)+'\n')
                groups.add(record['split_group']);records+=1;encoded+=len(tokens);categories[example['content_category']]+=1
                sources[example['source']].update(records=1,utf8_bytes=byte_count,encoded_positions=len(tokens),
                    prediction_positions=contribution,supervised_positions=supervised)
                if objective=='sft':writer.add(tokens[:-1],tokens[1:],mask[1:])
                else:
                    buffer.extend(tokens);start=0
                    while len(buffer)-start>context_length:
                        chunk=buffer[start:start+context_length+1]
                        writer.add(chunk[:-1],chunk[1:],[1]*context_length);start+=context_length
                    buffer=buffer[start:]
        if objective=='foundation' and len(buffer)>1:writer.add(buffer[:-1],buffer[1:],[1]*(len(buffer)-1))
        writer.flush();writer.close()
        if not writer.batches:raise ValueError('No eligible supervised training batches: '+json.dumps(dict(rejected)))
        if sum(v['prediction_positions'] for v in sources.values())!=writer.processed or sum(v['supervised_positions'] for v in sources.values())!=writer.supervised:
            raise AssertionError('Token accounting differs')
        verify(release);BPE.load(tokenizer)
        if sha(release/'manifest.json')!=release_hash or sha(tokenizer/'manifest.json')!=tokenizer_hash:
            raise ValueError('Source release/tokenizer changed during tokenization')
        report={'objective':objective,'split':'train','retained_records':records,'retained_groups':len(groups),
            'excluded_records':dict(rejected),'categories':dict(categories),'sources':{k:dict(v) for k,v in sorted(sources.items())},
            'one_pass_encoded_positions':encoded,'processed_prediction_positions':writer.processed,
            'supervised_positions':writer.supervised,'batches':writer.batches,'shards':len(writer.shards),
            'explicit_passes':1,'implicit_wraparound':False,'cross_document_attention':objective=='foundation',
            'truncation':False,'scope':'Verified bootstrap release to disk-backed token shards; tokenizer selection and model training are separate gates'}
        (temp/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        manifest={'version':1,'kind':'portable-token-shards-v1','split':'train','objective':objective,
            'context_length':context_length,'vocab_size':bpe.vocab_size,'batch_size':1,
            'tokenizer_hash':tokenizer_hash,'release_manifest_sha256':release_hash,
            'lineage_schema':'record-content-spans-v2',
            'builder_sha256':sha(__file__),'serializer_sha256':sha(Path(__file__).parents[1]/'common/tokenizer.py'),
            'allowed_categories':list(allowed_categories),'allowed_sources':list(allowed_sources) if allowed_sources is not None else None,'batches':writer.batches,
            'processed_tokens':writer.processed,'supervised_tokens':writer.supervised,
            'index_dtype':INDEX.descr,'shards':writer.shards,
            'files':{str(p.relative_to(temp)):sha(p) for p in sorted(temp.rglob('*')) if p.is_file()}}
        (temp/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        os.rename(temp,output)
    except BaseException:
        try:
            if writer is not None:writer.close()
        finally:shutil.rmtree(temp,ignore_errors=True)
        raise
    return {'dataset_hash':sha(output/'manifest.json'),'tokenizer_hash':tokenizer_hash,**report}


def validate_batch_objective(values,objective):
    x,y,mask=(a[0] for a in values)
    if not np.array_equal(x[1:],y[:-1]):raise ValueError('Next-token shift differs inside batch')
    if objective=='foundation':
        if not np.all(mask==1):raise ValueError('Foundation objective requires all next-token targets')
        return
    tokens=np.concatenate((x[:1],y));expected=np.zeros(tokens.size,dtype=np.float32)
    if tokens[0]!=STRUCTURAL['bos'] or tokens[-1]!=STRUCTURAL['eos']:raise ValueError('Invalid SFT message envelope')
    position=1;last_role=None
    while position<tokens.size-1:
        role=int(tokens[position])
        if role not in (STRUCTURAL['system'],STRUCTURAL['user'],STRUCTURAL['assistant'],STRUCTURAL['tool']):
            raise ValueError('Invalid SFT role marker')
        end=position+1
        while end<tokens.size and tokens[end]>=len(STRUCTURAL):end+=1
        if end>=tokens.size or tokens[end]!=STRUCTURAL['message_end']:raise ValueError('Invalid SFT message boundary')
        if role==STRUCTURAL['assistant']:expected[position+1:end+1]=1
        last_role=role;position=end+1
    expected[-1]=int(last_role==STRUCTURAL['assistant'])
    if not np.array_equal(mask,expected[1:]):raise ValueError('SFT role-derived supervision differs')


class ShardBatches:
    """Ordered B1 batches. Index maps metadata; only one data shard is cached."""
    def __init__(self,path,tokenizer,expected_fingerprint=None):
        self.path=Path(path);self.lock=RLock();self._closed=False;self._cache=None;self._index=None
        manifest_stamp=stamp(self.path/'manifest.json')
        manifest=json.loads((self.path/'manifest.json').read_text());self.fingerprint=sha(self.path/'manifest.json')
        if stamp(self.path/'manifest.json')!=manifest_stamp:raise ValueError('Dataset manifest changed during verification')
        if expected_fingerprint is not None and expected_fingerprint!=self.fingerprint:raise ValueError('Pinned token dataset differs')
        if (manifest.get('version')!=1 or manifest.get('kind')!='portable-token-shards-v1' or manifest.get('split')!='train'
            or manifest.get('batch_size')!=1 or manifest.get('objective') not in ('foundation','sft')
            or manifest.get('index_dtype')!=json.loads(json.dumps(INDEX.descr))):raise ValueError('Unsupported token-shard conventions')
        self.manifest=manifest;self.tokenizer_hash=manifest['tokenizer_hash'];self.vocab_size=manifest['vocab_size']
        if sha(Path(tokenizer)/'manifest.json')!=self.tokenizer_hash or BPE.load(tokenizer).vocab_size!=self.vocab_size:
            raise ValueError('Token-shard tokenizer differs')
        self._stamps={};files=manifest['files']
        expected={'index.bin','lineage.jsonl','report.json'}
        for i,shard in enumerate(manifest['shards']):
            if type(shard['positions']) is not int or shard['positions']<1 or set(shard['files'])!=set(DTYPES):raise ValueError('Invalid shard dimensions')
            for name,filename in shard['files'].items():
                if filename!=f'shards/{i:06d}-{name}.bin':raise ValueError('Noncanonical shard filename')
                expected.add(filename)
                if (self.path/filename).stat().st_size!=shard['positions']*np.dtype(DTYPES[name]).itemsize:raise ValueError('Shard size mismatch')
        actual={str(p.relative_to(self.path)) for p in self.path.rglob('*') if p.is_file() and p!=self.path/'manifest.json'}
        if set(files)!=expected or actual!=expected:raise ValueError('Token-shard file set differs')
        self._stamps['manifest.json']=manifest_stamp
        for name in ('index.bin','lineage.jsonl','report.json'):self._verify_file(name)
        if type(manifest['batches']) is not int or manifest['batches']<1 or (self.path/'index.bin').stat().st_size!=manifest['batches']*INDEX.itemsize:
            raise ValueError('Invalid batch index size')
        self._index=np.memmap(self.path/'index.bin',dtype=INDEX,mode='r',shape=(manifest['batches'],))
        self.max_length=0;tokens=supervised=shard_id=offset=0
        for row in self._index:
            sid,start,length,count,prefix_t,prefix_s=(int(row[k]) for k in INDEX.names)
            if (sid!=shard_id or start!=offset or not 1<=length<=manifest['context_length']
                or not 1<=count<=length or (prefix_t,prefix_s)!=(tokens,supervised)):
                raise ValueError('Invalid batch cursor/index accounting')
            tokens+=length;supervised+=count;offset+=length;self.max_length=max(self.max_length,length)
            if shard_id>=len(manifest['shards']) or offset>manifest['shards'][shard_id]['positions']:raise ValueError('Index exceeds shard')
            if offset==manifest['shards'][shard_id]['positions']:shard_id+=1;offset=0
        if (offset or shard_id!=len(manifest['shards']) or tokens!=manifest['processed_tokens'] or supervised!=manifest['supervised_tokens']):
            raise ValueError('Dataset totals/index differ')
        self.items=self
    def _verify_file(self,name):
        path=self.path/name;before=stamp(path)
        if sha(path)!=self.manifest['files'][name] or stamp(path)!=before:raise ValueError('Token-shard checksum mismatch: '+name)
        self._stamps[name]=before
    def _guard(self):
        if self._closed:raise ValueError('Token dataset is closed')
        for name,identity in self._stamps.items():
            if stamp(self.path/name)!=identity:raise ValueError('Token dataset changed after verification: '+name)
    def __len__(self):return self.manifest['batches']
    def __getitem__(self,index):
        with self.lock:
            self._guard()
            if type(index) is not int or not 0<=index<len(self):raise IndexError('Batch index outside dataset')
            row=self._index[index];sid,start,length=(int(row[k]) for k in ('shard','offset','length'))
            if self._cache is None or self._cache[0]!=sid:
                self._cache=None
                spec=self.manifest['shards'][sid];arrays={}
                for name,filename in spec['files'].items():
                    self._verify_file(filename)
                    arrays[name]=np.memmap(self.path/filename,dtype=DTYPES[name],mode='r',shape=(spec['positions'],))
                if (np.any(arrays['x']>=self.vocab_size) or np.any(arrays['y']>=self.vocab_size)
                    or not np.isin(arrays['loss'],[0,1]).all() or int(arrays['loss'].sum())!=spec['supervised']):
                    raise ValueError('Invalid shard token/mask values')
                active=set(spec['files'].values())
                self._stamps={k:v for k,v in self._stamps.items() if not k.startswith('shards/') or k in active}
                self._cache=(sid,arrays)
            arrays=self._cache[1]
            result=tuple(np.array(arrays[name][start:start+length],dtype=np.float32 if name=='loss' else np.int64,copy=True).reshape(1,length) for name in DTYPES)
            if int(result[2].sum())!=int(row['supervised']):raise ValueError('Batch supervision/index differs')
            validate_batch_objective(result,self.manifest['objective'])
            self._guard()
            for a in result:a.flags.writeable=False
            return result
    def counts(self,cursor):
        with self.lock:
            self._guard()
            if type(cursor) is not int or not 0<=cursor<=len(self):raise ValueError('Invalid dataset cursor')
            if cursor==0:return 0,0
            row=self._index[cursor-1]
            return int(row['prefix_tokens'])+int(row['length']),int(row['prefix_supervised'])+int(row['supervised'])
    def close(self):
        with self.lock:self._cache=None;self._index=None;self._closed=True
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release',required=True);p.add_argument('--tokenizer',required=True);p.add_argument('--output',required=True)
    p.add_argument('--objective',choices=['foundation','sft'],required=True);p.add_argument('--context-length',type=int,default=1024)
    p.add_argument('--shard-positions',type=int,default=262144);p.add_argument('--max-positions',type=int,default=64000000)
    p.add_argument('--category',action='append',default=None);p.add_argument('--source',action='append',default=None)
    a=p.parse_args();print(json.dumps(build_shards(a.release,a.tokenizer,a.output,a.objective,a.context_length,a.shard_positions,a.max_positions,tuple(a.category or ['sfw']),tuple(a.source) if a.source else None),indent=2))


if __name__=='__main__':main()
