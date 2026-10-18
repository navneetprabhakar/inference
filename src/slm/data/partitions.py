"""Bounded OASST official ID-column projection and complete-tree partition join."""
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
from threading import Lock
import urllib.request
from slm.data.schema import digest
from slm.data.build import read_source
from slm.data.acquire import fetch

COLUMNS=['message_id','parent_id','message_tree_id']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PayloadBudget:
    def __init__(self,limit):self.limit=limit;self.reserved=0;self.lock=Lock()
    def reserve(self,size):
        with self.lock:
            if size<0 or self.reserved+size>self.limit:raise ValueError('Partition range payload budget exceeded')
            self.reserved+=size


class RangeCache(io.RawIOBase):
    """Reads only previously acquired spans. Unexpected Parquet I/O cannot fetch text."""
    def __init__(self,size,folder,spans=None):
        super().__init__();self.size=size;self.folder=Path(folder);self.position=0
        self.spans=spans if spans is not None else json.loads((self.folder/'ranges.json').read_text())
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.position
    def seek(self,offset,whence=0):
        position=offset if whence==0 else self.position+offset if whence==1 else self.size+offset if whence==2 else -1
        if position<0:raise ValueError('Invalid sparse seek')
        self.position=position;return position
    def read(self,size=-1):
        size=self.size-self.position if size<0 else min(size,max(0,self.size-self.position))
        if not size:return b''
        start=self.position
        for span in self.spans:
            if span['start']<=start and start+size<=span['start']+span['size']:
                path=self.folder/span['file'];data=path.read_bytes()
                if len(data)!=span['size'] or hashlib.sha256(data).hexdigest()!=span['sha256']:
                    raise ValueError('Partition range cache checksum mismatch')
                offset=start-span['start'];self.position+=size;return data[offset:offset+size]
        raise ValueError('Parquet requested an unacquired span; no network fallback')


def acquire_span(url,file_size,start,size,folder,budget):
    if start<0 or size<=0 or start+size>file_size:raise ValueError('Range outside pinned object')
    budget.reserve(size)
    # Vary the public URL by range as well, avoiding non-compliant intermediary range caches.
    address=url+f'?download=true&slm_range={start}-{start+size-1}'
    request=urllib.request.Request(address,headers={'Range':f'bytes={start}-{start+size-1}',
        'Accept-Encoding':'identity','User-Agent':'portable-slm-partition-audit/1'})
    with urllib.request.urlopen(request,timeout=45) as response:
        expected=f'bytes {start}-{start+size-1}/{file_size}'
        if response.status!=206 or response.headers.get('Content-Range')!=expected:
            raise ValueError('Exact HTTP partial response required; full download refused')
        if response.headers.get('Content-Encoding','identity')!='identity':raise ValueError('Encoded range refused')
        data=response.read(size+1)
    if len(data)!=size:raise ValueError('Partial response length differs')
    name=f'range-{start}-{size}.bin';(Path(folder)/name).write_bytes(data)
    return {'start':start,'size':size,'file':name,'sha256':hashlib.sha256(data).hexdigest()}


def metadata_from_spans(cache):
    import pyarrow as pa
    import pyarrow.parquet as pq
    cache.seek(0);header=cache.read(4);cache.seek(cache.size-8);tail=cache.read(8)
    if header!=b'PAR1' or tail[4:]!=b'PAR1':raise ValueError('Invalid Parquet magic')
    length=struct.unpack('<I',tail[:4])[0]
    if length>1024*1024 or length>cache.size-12:raise ValueError('Parquet footer exceeds metadata budget')
    cache.seek(cache.size-8-length);footer=cache.read(length)
    # Parse the real footer without asking Arrow for a 64 KiB window containing other columns.
    metadata=pq.read_metadata(pa.BufferReader(header+footer+tail))
    return metadata


def column_spans(metadata):
    spans=[]
    for group in range(metadata.num_row_groups):
        block=metadata.row_group(group)
        for col in range(block.num_columns):
            value=block.column(col)
            if value.path_in_schema in COLUMNS:
                offsets=[value.data_page_offset]
                if value.dictionary_page_offset is not None and value.dictionary_page_offset>=0:offsets.append(value.dictionary_page_offset)
                spans.append((min(offsets),value.total_compressed_size))
    merged=[]
    for start,size in sorted(spans):
        if merged and start<=merged[-1][0]+merged[-1][1]:
            prior,length=merged[-1];merged[-1]=(prior,max(prior+length,start+size)-prior)
        else:merged.append((start,size))
    return merged


def project_file(spec,revision,folder,budget,cache=None):
    import pyarrow.parquet as pq
    folder=Path(folder);folder.mkdir()
    if cache is None:
        url=f'https://huggingface.co/datasets/OpenAssistant/oasst2/resolve/{revision}/{spec["path"]}'
        initial=[]
        for start,size in ((0,4),(spec['size']-8,8)):
            initial.append(acquire_span(url,spec['size'],start,size,folder,budget))
        reader=RangeCache(spec['size'],folder,initial);reader.seek(spec['size']-8)
        tail=reader.read(8);length=struct.unpack('<I',tail[:4])[0]
        if tail[4:]!=b'PAR1' or not 0<length<=1024*1024 or length>spec['size']-12:raise ValueError('Invalid bounded footer')
        initial.append(acquire_span(url,spec['size'],spec['size']-8-length,length,folder,budget))
        metadata=metadata_from_spans(RangeCache(spec['size'],folder,initial))
        plan=column_spans(metadata)
        if sum(size for _,size in plan)>budget.limit-budget.reserved:raise ValueError('ID projection exceeds range budget')
        with ThreadPoolExecutor(max_workers=4) as pool:
            projected=list(pool.map(lambda span:acquire_span(url,spec['size'],*span,folder,budget),plan))
        spans=initial+projected
        (folder/'ranges.json').write_text(json.dumps(sorted(spans,key=lambda v:(v['start'],v['size'])),sort_keys=True,indent=2)+'\n')
    else:
        shutil.copytree(cache,folder,dirs_exist_ok=True)
        metadata=metadata_from_spans(RangeCache(spec['size'],folder))
    reader=RangeCache(spec['size'],folder)
    if metadata.num_rows!=spec['rows'] or metadata.num_rows>200000:raise ValueError('Pinned partition row count differs')
    if not set(COLUMNS)<=set(metadata.schema.names):raise ValueError('Missing official identity columns')
    parquet=pq.ParquetFile(reader,metadata=metadata,pre_buffer=False,buffer_size=0,arrow_extensions_enabled=False)
    table=parquet.read(columns=COLUMNS,use_threads=False)
    if table.column_names!=COLUMNS or table.num_rows!=spec['rows']:raise ValueError('Incomplete identity projection')
    report={**spec,'row_groups':metadata.num_row_groups,'range_payload_bytes':sum(s['size'] for s in reader.spans),
        'ranges':len(reader.spans),'projected_rows_sha256':digest(table.to_pylist()),'full_file_sha256_verified':False}
    return table.to_pylist(),report


def official_trees(partitions):
    trees=defaultdict(dict);splits={};seen=set()
    for split,records in partitions:
        if split not in ('train','validation','test'):raise ValueError('Unknown upstream partition')
        for row in records:
            key,parent,root=(row[k] for k in COLUMNS)
            if not all(isinstance(x,str) and x and len(x)<=128 for x in (key,root)) or (parent is not None and not isinstance(parent,str)):
                raise ValueError('Invalid official identity fields')
            if key in seen:raise ValueError('Duplicate official message identity')
            seen.add(key)
            if root in splits and splits[root]!=split:raise ValueError('Official conversation crosses partitions')
            splits[root]=split;trees[root][key]=parent
    for root,nodes in trees.items():
        if nodes.get(root,'missing') is not None or {k for k,v in nodes.items() if v is None}!={root}:
            raise ValueError('Official tree root differs')
        for key in nodes:
            cursor=key;visited=set()
            while cursor is not None:
                if cursor not in nodes or cursor in visited:raise ValueError('Official tree has missing parent or cycle')
                visited.add(cursor);cursor=nodes[cursor]
    return trees,splits


def join_ready(records,partitions):
    trees,splits=official_trees(partitions);mapped={}
    for tree in records:
        root=tree['message_tree_id'];nodes={}
        if root in mapped or tree.get('tree_state')!='ready_for_export':raise ValueError('Duplicate/incomplete ready tree')
        def visit(node,parent=None):
            key=node['message_id']
            if (key in nodes or node.get('message_tree_id') not in (None,root) or node.get('parent_id')!=parent
                or not isinstance(node.get('replies'),list)):raise ValueError('Ready-tree identity differs')
            nodes[key]=parent
            for child in node['replies']:visit(child,key)
        visit(tree['prompt'])
        if tree['prompt']['message_id']!=root or root not in trees or nodes!=trees[root]:
            raise ValueError('Complete ready-tree membership differs from official projection')
        mapped[root]={'split':splits[root],'messages':len(nodes),'node_identity_sha256':digest(sorted(nodes.items()))}
    return mapped,{'official_rows':sum(len(v) for v in trees.values()),'official_trees':len(trees),
        'official_trees_by_split':dict(Counter(splits.values())),'selected_trees':len(mapped),
        'selected_trees_by_split':dict(Counter(v['split'] for v in mapped.values()))}


def verify_bundle(path,expected_sha256=None):
    path=Path(path)
    if expected_sha256 is not None and sha(path/'manifest.json')!=expected_sha256:raise ValueError('Pinned partition manifest differs')
    manifest=json.loads((path/'manifest.json').read_text())
    if manifest.get('version')!=1 or manifest.get('kind')!='oasst-official-id-projection-v1':raise ValueError('Unknown partition bundle')
    files={str(p.relative_to(path)) for p in path.rglob('*') if p.is_file() and p!=path/'manifest.json'}
    if files!=set(manifest['files']):raise ValueError('Partition bundle file set differs')
    if sum((path/f).stat().st_size for f in files)>20*1024*1024:raise ValueError('Partition bundle exceeds bounded audit scope')
    for name,checksum in manifest['files'].items():
        if sha(path/name)!=checksum:raise ValueError('Partition bundle checksum mismatch')
    return manifest


def collect(source_record,ready_sample,destination,registry='configs/oasst2-partitions-v1.json',cache=None):
    source=read_source(source_record);ready_sample=Path(ready_sample);destination=Path(destination)
    if destination.exists():raise FileExistsError(destination)
    config=json.loads(Path(registry).read_text())
    if ((source.source_id,source.revision)!=(config['source_id'],config['revision']) or config['columns']!=COLUMNS
        or type(config['max_range_payload_bytes']) is not int or not 0<config['max_range_payload_bytes']<=16*1024*1024):
        raise ValueError('Pinned OASST source identity differs')
    acquisition=json.loads((ready_sample/'acquisition.json').read_text());rows_hash=sha(ready_sample/'rows.jsonl')
    records=[json.loads(line) for line in (ready_sample/'rows.jsonl').read_text().splitlines()]
    if (acquisition['source']!=source.source_id or acquisition['revision']!=source.revision
        or acquisition['rows_sha256']!=rows_hash or acquisition['rows']!=len(records) or not 1<=len(records)<=500):
        raise ValueError('Ready-tree acquisition binding differs')
    if cache is not None:
        cache=Path(cache);verify_bundle(cache)
        if json.loads((cache/'registry.json').read_text())!=config:raise ValueError('Cached partition registry differs')
        metadata=(cache/'repository-data-files.json').read_bytes()
    else:
        metadata,_=fetch(f'https://huggingface.co/api/datasets/{source.source_id}/tree/{source.revision}/data?recursive=false&expand=false')
    published={entry['path']:entry for entry in json.loads(metadata)}
    for spec in config['files']:
        actual=published.get(spec['path'],{})
        if actual.get('size')!=spec['size'] or actual.get('lfs',{}).get('oid')!=spec['lfs_sha256']:
            raise ValueError('Published pinned Parquet object differs')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.partition-audit-',dir=destination.parent))
    budget=PayloadBudget(config['max_range_payload_bytes'])
    try:
        partitions=[];evidence=[]
        for spec in config['files']:
            data,report=project_file(spec,source.revision,temp/spec['split'],budget,None if cache is None else cache/spec['split'])
            partitions.append((spec['split'],data));evidence.append(report)
        mapped,summary=join_ready(records,partitions)
        mapping={'version':1,'source':asdict(source),'source_record_sha256':digest(asdict(source)),
            'ready_rows_sha256':rows_hash,'trees':mapped,'summary':summary,'evidence':evidence,
            'scope':'Pinned official identity projection; no source/content approval or whole-Parquet checksum verification'}
        (temp/'mapping.json').write_text(json.dumps(mapping,sort_keys=True,indent=2)+'\n')
        (temp/'registry.json').write_text(json.dumps(config,sort_keys=True,indent=2)+'\n')
        (temp/'repository-data-files.json').write_bytes(metadata)
        manifest={'version':1,'kind':'oasst-official-id-projection-v1',
            'files':{str(p.relative_to(temp)):sha(p) for p in sorted(temp.rglob('*')) if p.is_file()}}
        (temp/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        os.rename(temp,destination)
    except BaseException:
        shutil.rmtree(temp,ignore_errors=True);raise
    return {'bundle_sha256':sha(destination/'manifest.json'),**summary,
        'range_payload_bytes':sum(v['range_payload_bytes'] for v in evidence),
        'new_range_payload_bytes':budget.reserved,'metadata_response_bytes':len(metadata),'cache_replay':cache is not None,
        'full_file_sha256_verified':False,'source_approved':False}


def load_mapping(path,expected_sha256,source,rows_sha256):
    if not isinstance(expected_sha256,str) or not re.fullmatch('[a-f0-9]{64}',expected_sha256):
        raise ValueError('Explicit partition manifest SHA-256 required')
    verify_bundle(path,expected_sha256)
    mapping=json.loads((Path(path)/'mapping.json').read_text())
    if (mapping['version']!=1 or mapping['source']!=json.loads(json.dumps(asdict(source)))
        or mapping['source_record_sha256']!=digest(asdict(source)) or mapping['ready_rows_sha256']!=rows_sha256):
        raise ValueError('Official partition mapping input/source differs')
    return mapping['trees'],expected_sha256


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-record',required=True);p.add_argument('--ready-sample',required=True)
    p.add_argument('--output',required=True);p.add_argument('--registry',default='configs/oasst2-partitions-v1.json')
    p.add_argument('--cache')
    a=p.parse_args();print(json.dumps(collect(a.source_record,a.ready_sample,a.output,a.registry,a.cache),indent=2))


if __name__=='__main__':main()
