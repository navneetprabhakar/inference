"""Bounded, source-pinned general SFT preparation; no training or cloud actions.

Preserve complete source conversations, reject unsupported tool frames, dedupe
exact conversations and isolate validation user-prompt sequences. Public test is
DEVELOPMENT, never final acceptance. Outputs stay training_admitted=false until
separate review. One CPU thread, streaming Parquet and disk-backed deterministic
shuffle keep preparation bounded alongside base-corpus work.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import random
import resource
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request

from cloud_training.nano_chat_format import VERSION, encode_conversation, canonical

REPOSITORY='HuggingFaceTB/smol-smoltalk'
REVISION='f73fe857d519ff6ac5af2ea67c4d3834da7b8bcc'
TOKENIZER_SHA='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'
MAX_DOWNLOAD=1_000_000_000
MIN_FREE=80*1024**3
FILES=[
 ('test-00000-of-00001.parquet',48177022,'be6773dcce145f3918ff14237b1f765affa427b0b13f6a02d397e665ac908b9a'),
 ('train-00000-of-00004.parquet',229710350,'498cd4580014f42c40cfde066573564ed28e3e1548a5566715b615f5ea932856'),
 ('train-00001-of-00004.parquet',230298184,'5412c03df579fc7dd7d06c7f5249627d99d0621882fb8f2cd5c13582eb2a80f6'),
 ('train-00002-of-00004.parquet',230587255,'aefcac6571abf275b4e1629baa01f326c0fe279d35cd0349b7439319923815a7'),
 ('train-00003-of-00004.parquet',231879938,'c15edfca888c9924a626dad7b7f4e9f08d8f406f997ac13be46bc9be0a6192db')]
TOOL_MARKUP=re.compile(r'<\|(?:python_start|output_start)\|>|<tool_call>|<function_call>|"(?:tool_calls|function_call)"\s*:')
UNSUPPORTED_ACTION=re.compile(r"\bI(?:['’]ve| have|['’]ll| will| can)\s+(?:(?:already|successfully|now)\s+|proceed\s+with\s+)?(?:send|sent|schedule|scheduled|scheduling|book|booked|booking|purchase|purchased|purchasing|delete|deleted|deleting|upload|uploaded|uploading|email|emailed|emailing)\b",re.IGNORECASE)
UNSUPPORTED_SYSTEM=re.compile(r'confirm.{0,40}appointments.{0,40}reminders.{0,60}setting',re.IGNORECASE|re.DOTALL)


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def atomic_json(path,value):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.partial')
    with tmp.open('w') as f:
        json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(tmp,path)


def rss_bytes():
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform=='darwin' else value*1024)


def resources(path,min_free=MIN_FREE):
    if shutil.disk_usage(path).free<min_free:raise RuntimeError('SFT prep disk guard: less than reserved free space')
    if rss_bytes()>=4*1024**3:raise RuntimeError('SFT prep exceeded4GiB peak RSS guard')


def download_sources(directory,*,min_free=MIN_FREE):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    if sum(n for _,n,_ in FILES)>MAX_DOWNLOAD:raise ValueError('Source download budget exceeds1GB')
    receipts=[]
    for name,expected_size,digest in FILES:
        resources(directory,min_free)
        target=directory/name
        if target.exists():
            if target.stat().st_size!=expected_size or sha(target)!=digest:raise ValueError('Existing source file differs: '+name)
        else:
            partial=target.with_suffix('.parquet.partial')
            url=f'https://huggingface.co/datasets/{REPOSITORY}/resolve/{REVISION}/data/{name}'
            count=0;h=hashlib.sha256()
            with urllib.request.urlopen(url,timeout=60) as response,partial.open('wb') as f:
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk:break
                    count+=len(chunk)
                    if count>expected_size:raise ValueError('Download exceeds pinned size')
                    f.write(chunk);h.update(chunk)
                    if count%(64*1024*1024)<1024*1024:resources(directory,min_free)
                f.flush();os.fsync(f.fileno())
            if count!=expected_size or h.hexdigest()!=digest:raise ValueError('Downloaded source hash/size mismatch')
            os.replace(partial,target)
        receipts.append({'file':name,'bytes':expected_size,'sha256':digest})
        atomic_json(directory/'download-receipt.json',{'repository':REPOSITORY,'revision':REVISION,'files':receipts,'bytes':sum(v['bytes'] for v in receipts)})
        print(json.dumps({'event':'source_verified','file':name,'bytes':expected_size}),flush=True)
    return receipts


def normalize_general(row):
    messages=row.get('messages') if isinstance(row,dict) else None
    if not isinstance(messages,list) or not messages:raise ValueError('invalid_messages')
    normalized=[]
    for i,message in enumerate(messages):
        if not isinstance(message,dict) or set(message)!={'role','content'}:raise ValueError('unsupported_message_fields')
        role,content=message['role'],message['content']
        if not isinstance(content,str) or not content.strip():raise ValueError('empty_or_nontext_content')
        if len(content.encode('utf8'))>65536:raise ValueError('oversize_message')
        if role=='system' and i==0:pass
        elif role not in ('user','assistant'):raise ValueError('unsupported_role_or_tool')
        if role=='assistant' and TOOL_MARKUP.search(content):raise ValueError('unsupported_tool_markup')
        if role=='assistant' and UNSUPPORTED_ACTION.search(content):raise ValueError('unsupported_external_action_claim')
        if role=='system' and UNSUPPORTED_SYSTEM.search(content):raise ValueError('unsupported_system_capability')
        normalized.append({'role':role,'content':content})
    ordinary=normalized[1:] if normalized[0]['role']=='system' else normalized
    if not ordinary or len(ordinary)%2:raise ValueError('incomplete_conversation')
    if any(m['role']!=('user' if i%2==0 else 'assistant') for i,m in enumerate(ordinary)):
        raise ValueError('role_order')
    fingerprint=hashlib.sha256(canonical({'messages':normalized,'policies':None}).encode()).hexdigest()
    prompt_hash=hashlib.sha256(canonical([m['content'] for m in ordinary if m['role']=='user']).encode()).hexdigest()
    return normalized,fingerprint,prompt_hash


def encode_general(row,tokenizer):
    messages,fingerprint,prompt_hash=normalize_general(row)
    try:rendered=encode_conversation(tokenizer,messages,context=2048)
    except ValueError as exc:
        if 'Context overflow' in str(exc):raise ValueError('context_overflow') from exc
        raise ValueError('format_rejected') from exc
    targets=sum(rendered['mask'][1:])
    if not targets:raise ValueError('no_assistant_targets')
    return {'messages':messages,'policies':None,'id':fingerprint,
            'assistant_target_count':targets,'sequence_tokens':len(rendered['ids']),
            'user_turns':sum(m['role']=='user' for m in messages)},prompt_hash


def process_rows(rows_by_split,tokenizer,output,*,source_identity,seed=103,min_free=MIN_FREE):
    """Iterable row tuples (source_file,row_index,source_record), validation first."""
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    resources(output,min_free)
    db=sqlite3.connect(output/'shuffle.sqlite')
    db.execute('PRAGMA cache_size=-16384');db.execute('PRAGMA temp_store=FILE');db.execute('PRAGMA threads=1')
    db.execute('CREATE TABLE accepted (split TEXT, id TEXT PRIMARY KEY, shuffle TEXT, content TEXT)')
    seen=set();dev_prompts=set();stats={};started=time.monotonic()
    try:
        for split in ('validation','train'):
            stats[split]={'seen':0,'accepted':0,'rejected':Counter(),'assistant_targets':0,
                          'sequence_tokens':0,'user_turns':0,'multiturn_sessions':0,
                          'source_counts':Counter(),'max_sequence_tokens':0}
            st=stats[split]
            for file,row_index,row in rows_by_split[split]:
                st['seen']+=1
                try:
                    item,prompt=encode_general(row,tokenizer)
                    if item['id'] in seen:raise ValueError('duplicate_exact_conversation')
                    if split=='train' and prompt in dev_prompts:raise ValueError('validation_prompt_overlap')
                    item['source']={'dataset':source_identity['repository'],'revision':source_identity['revision'],
                                    'file':file,'row':row_index,'component':row.get('source','unknown')}
                    content=canonical(item)
                    if len(content.encode())>1_048_576:raise ValueError('overlarge_jsonl_row')
                    order=hashlib.sha256(f'{seed}:{item["id"]}'.encode()).hexdigest()
                    db.execute('INSERT INTO accepted VALUES (?,?,?,?)',(split,item['id'],order,content))
                    seen.add(item['id'])
                    if split=='validation':dev_prompts.add(prompt)
                    st['accepted']+=1;st['assistant_targets']+=item['assistant_target_count']
                    st['sequence_tokens']+=item['sequence_tokens'];st['user_turns']+=item['user_turns']
                    st['multiturn_sessions']+=int(item['user_turns']>1)
                    st['source_counts'][str(row.get('source','unknown'))]+=1
                    st['max_sequence_tokens']=max(st['max_sequence_tokens'],item['sequence_tokens'])
                except (ValueError,TypeError,UnicodeError) as exc:
                    st['rejected'][str(exc)[:100]]+=1
                if st['seen']%1000==0:
                    db.commit();resources(output,min_free)
                    atomic_json(output/'progress.json',{'status':'processing','current_split':split,'stats':stats,
                                                         'seconds':time.monotonic()-started,'peak_rss_bytes':rss_bytes()})
                    if st['seen']%10000==0:print(json.dumps({'event':'sft_rows','split':split,'seen':st['seen'],'accepted':st['accepted']}),flush=True)
            db.commit()
            if st['accepted']==0:raise ValueError('No retained '+split+' conversations')
        manifest={'schema':1,'training_admitted':False,'format_version':VERSION,
                  'tokenizer_sha256':TOKENIZER_SHA,'context_tokens':2048,'source':source_identity,
                  'split_policy':'Upstream test becomes development; validation exact conversations and user-message sequences excluded from train. No final acceptance accessed.',
                  'shuffle':{'method':'SHA256(seed:conversation_id) lexical order','seed':seed},
                  'stats':stats,'peak_rss_bytes':rss_bytes(),'seconds':time.monotonic()-started,
                  'limits':['Exact dedup only; near-duplicate/source benchmark contamination audit remains.','General conversation source is public synthetic data; semantic quality is not established by formatting checks.','No corpus replay, truncation or arbitrary tool-call conversion.','Conservative first-person external-action claim filter can remove legitimate quoted/fictional text and does not detect every semantic false claim.']}
        for split in ('train','validation'):
            path=output/(split+'.jsonl')
            with path.open('w') as f:
                for (content,) in db.execute('SELECT content FROM accepted WHERE split=? ORDER BY shuffle,id',(split,)):
                    f.write(content+'\n')
                f.flush();os.fsync(f.fileno())
            manifest[split]={'file':path.name,'sha256':sha(path),'bytes':path.stat().st_size,
                             'sessions':stats[split]['accepted'],'assistant_targets':stats[split]['assistant_targets']}
        atomic_json(output/'manifest.json',manifest)
        atomic_json(output/'progress.json',{'status':'prepared_not_admitted','stats':stats,'seconds':time.monotonic()-started,'peak_rss_bytes':rss_bytes()})
        return manifest
    finally:db.close()


def combine_counted(general, tokenizer, output, *, tool_per_family=16, min_free=MIN_FREE):
    """One-pass mixture after measured source counts; no replay or assumed ratio.

    This is a mechanically checked candidate, not automatic SFT admission or a
    claim that a tiny tool share is sufficient. Report assistant-token proportions
    so the caller can decide on a separate targeted phase.
    """
    from cloud_training.nano_tool_lessons import build_lessons, validate_lesson
    general=Path(general);output=Path(output)
    source=json.loads((general/'manifest.json').read_text())
    if source.get('format_version')!=VERSION or source.get('tokenizer_sha256')!=TOKENIZER_SHA:
        raise ValueError('General corpus format/tokenizer mismatch')
    if type(tool_per_family)is not int or not 1<=tool_per_family<=1000:raise ValueError('Bounded tool count required')
    output.mkdir(parents=True,exist_ok=False);resources(output,min_free)
    seen=set()
    for split in ('validation','train'):
        path=general/source[split]['file']
        if source[split]['file']!=split+'.jsonl' or sha(path)!=source[split]['sha256']:raise ValueError('General source file changed')
        with path.open() as f:
            for line in f:
                row=json.loads(line)
                fingerprint=hashlib.sha256(canonical({'messages':row['messages'],'policies':row.get('policies')}).encode()).hexdigest()
                if fingerprint in seen:raise ValueError('General conversation duplicates/crosses split')
                seen.add(fingerprint)
    result={'schema':1,'training_admitted':False,'format_version':VERSION,'tokenizer_sha256':TOKENIZER_SHA,
            'context_tokens':2048,'general_manifest_sha256':sha(general/'manifest.json'),
            'mix_policy':'One pass of all retained general conversations plus bounded unique tool lessons; deterministic even interleaving, no replay.',
            'stats':{},'limits':['Measured proportions are not claimed optimal. A separate targeted phase may be needed.','Formatting, execution and exact split checks do not establish model quality or source semantic admission.']}
    for split in ('validation','train'):
        tools=[];tool_targets=0;tool_calls=0;duplicates=0
        for lesson in build_lessons(split,per_family=tool_per_family):
            audit=validate_lesson(lesson)
            fingerprint=hashlib.sha256(canonical({'messages':lesson['messages'],'policies':lesson['policies']}).encode()).hexdigest()
            if fingerprint in seen:duplicates+=1;continue
            seen.add(fingerprint)
            rendered=encode_conversation(tokenizer,lesson['messages'],policies=lesson['policies'],context=2048)
            count=sum(rendered['mask'][1:]);tool_targets+=count;tool_calls+=audit['actual_calls']
            tools.append({'messages':lesson['messages'],'policies':lesson['policies'],'id':fingerprint,
                          'source':{'kind':'own_executed_broker_lessons','family':lesson['family'],'template_id':lesson['template_id']},
                          'assistant_target_count':count,'sequence_tokens':len(rendered['ids'])})
        general_count=source[split]['sessions'];stride=max(1,general_count//max(1,len(tools)))
        destination=output/(split+'.jsonl');added=0;general_targets=0;rows=0
        with destination.open('w') as out,(general/source[split]['file']).open() as inp:
            for line in inp:
                item=json.loads(line);general_targets+=item['assistant_target_count'];rows+=1
                out.write(line)
                if rows%stride==0 and added<len(tools):out.write(canonical(tools[added])+'\n');added+=1
                if rows%10000==0:resources(output,min_free)
            for item in tools[added:]:out.write(canonical(item)+'\n')
            out.flush();os.fsync(out.fileno())
        if rows!=general_count or general_targets!=source[split]['assistant_targets']:
            raise ValueError('General source counts changed')
        total=general_targets+tool_targets
        result[split]={'file':destination.name,'sha256':sha(destination),'bytes':destination.stat().st_size,
                       'sessions':rows+len(tools),'assistant_targets':total}
        result['stats'][split]={'general_sessions':rows,'tool_sessions':len(tools),'tool_duplicates_rejected':duplicates,
                               'general_assistant_targets':general_targets,'tool_assistant_targets':tool_targets,
                               'tool_assistant_target_fraction':tool_targets/total,'actual_broker_calls':tool_calls}
    atomic_json(output/'manifest.json',result)
    return result


def tool_inventory(tokenizer,output,*,max_sessions=16384,seed=103,min_free=MIN_FREE):
    """Count unique broker lessons for a later targeted phase, never replay them.

    Repeated generation attempts are deduplicated by actual messages/policies;
    different metadata never makes a duplicate into a new training example.
    The fixed validation template/entity split stays separate.
    """
    from cloud_training.nano_tool_lessons import build_lessons, validate_lesson, FAMILIES, ENTITIES
    if type(max_sessions)is not int or not 1<=max_sessions<=16384:raise ValueError('Tool inventory capped at16384 unique sessions')
    output=Path(output);output.mkdir(parents=True,exist_ok=False);resources(output,min_free)
    seen=set();counts=Counter();targets=0;calls=0;attempts=0;duplicates=0;milestones={}
    entity_rng=random.Random(seed+10000019);entity_operations=Counter()
    path=output/'train.jsonl';prefix_hash=hashlib.sha256();prefix_bytes=0
    with path.open('w') as f:
        for batch in range(5):
            generated=build_lessons('train',per_family=1000,seed=seed+batch)
            groups={name:[row for row in generated if row['family']==name] for name in FAMILIES}
            for index in range(1000):
                for family in FAMILIES:
                    lesson=groups[family][index];attempts+=1
                    # Entity labels are a separately sampled synthetic parameter,
                    # not a modulo-index shortcut for operation or template.
                    old_entity=lesson['spec']['entity'];new_entity=entity_rng.choice(ENTITIES['train'])
                    for message in lesson['messages']:
                        if 'content' in message:
                            message['content']=re.sub(r'\b'+re.escape(old_entity)+r'\b',new_entity,message['content'])
                    lesson['spec']['entity']=new_entity;lesson['entities']=[new_entity]
                    fingerprint=hashlib.sha256(canonical({'messages':lesson['messages'],'policies':lesson['policies']}).encode()).hexdigest()
                    if fingerprint in seen:duplicates+=1;continue
                    seen.add(fingerprint)
                    audit=validate_lesson(lesson)
                    rendered=encode_conversation(tokenizer,lesson['messages'],policies=lesson['policies'],context=2048)
                    target_count=sum(rendered['mask'][1:]);targets+=target_count;calls+=audit['actual_calls'];counts[family]+=1
                    if family=='arithmetic':entity_operations[new_entity+'/'+lesson['spec']['op']]+=1
                    row={'messages':lesson['messages'],'policies':lesson['policies'],'id':fingerprint,
                         'source':{'kind':'own_executed_broker_lessons','family':family,'template_id':lesson['template_id'],'seed':seed+batch,'entity':new_entity,'entity_assignment':'independent-seeded'},
                         'assistant_target_count':target_count,'sequence_tokens':len(rendered['ids'])}
                    line=canonical(row)+'\n';f.write(line);encoded=line.encode();prefix_hash.update(encoded);prefix_bytes+=len(encoded)
                    if len(seen) in (8192,16384,max_sessions):
                        milestones[str(len(seen))]={'sessions':len(seen),'assistant_targets':targets,'actual_broker_calls':calls,'family_counts':dict(counts),
                                                    'prefix_bytes':prefix_bytes,'prefix_sha256':prefix_hash.hexdigest()}
                    if len(seen)>=max_sessions:break
                if len(seen)>=max_sessions:break
            if len(seen)>=max_sessions:break
            resources(output,min_free)
        if len(seen)<max_sessions:raise ValueError('Unique tool-generation budget exhausted')
        f.flush();os.fsync(f.fileno())
    dev=build_lessons('validation',per_family=16,seed=seed)
    dev_targets=0
    with (output/'validation.jsonl').open('w') as f:
        for lesson in dev:
            fingerprint=hashlib.sha256(canonical({'messages':lesson['messages'],'policies':lesson['policies']}).encode()).hexdigest()
            if fingerprint in seen:raise ValueError('Tool train/development overlap')
            seen.add(fingerprint);validate_lesson(lesson)
            rendered=encode_conversation(tokenizer,lesson['messages'],policies=lesson['policies'],context=2048)
            target_count=sum(rendered['mask'][1:]);dev_targets+=target_count
            f.write(canonical({'messages':lesson['messages'],'policies':lesson['policies'],'id':fingerprint,
                               'source':{'kind':'own_executed_broker_lessons','family':lesson['family'],'template_id':lesson['template_id']},
                               'assistant_target_count':target_count,'sequence_tokens':len(rendered['ids'])})+'\n')
    result={'schema':1,'training_admitted':False,'format_version':VERSION,'tokenizer_sha256':TOKENIZER_SHA,'context_tokens':2048,
            'train':{'file':'train.jsonl','sha256':sha(path),'sessions':max_sessions,'assistant_targets':targets},
            'validation':{'file':'validation.jsonl','sha256':sha(output/'validation.jsonl'),'sessions':len(dev),'assistant_targets':dev_targets},
            'milestones':milestones,'generation_attempts':attempts,'duplicates_discarded':duplicates,'entity_operation_counts':dict(entity_operations),
            'limits':['Unique parameterizations still share a small template family inventory; counts do not imply generalization.',
                      'No training replay or mixing performed. Root must choose a bounded targeted phase with general-conversation retention and held-out development.']}
    atomic_json(output/'manifest.json',result)
    return result


def parquet_rows(paths):
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    for path in paths:
        index=0
        for batch in pq.ParquetFile(path).iter_batches(batch_size=128,columns=['messages','source'],use_threads=False):
            for row in batch.to_pylist():yield path.name,index,row;index+=1


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['download','prepare','combine','tool-inventory'])
    p.add_argument('--root',default='runs/ownbase-v2-sft')
    p.add_argument('--tokenizer',default='runs/ownbase-v2-data/tokenizer')
    p.add_argument('--repo',default='runs/nanochat-source')
    p.add_argument('--tools-per-family',type=int,default=16)
    args=p.parse_args();root=Path(args.root);root.mkdir(parents=True,exist_ok=True)
    if args.command=='download':download_sources(root/'source');return
    os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
    if sha(Path(args.tokenizer)/'tokenizer.pkl')!=TOKENIZER_SHA:raise ValueError('Final own tokenizer identity mismatch')
    revision=subprocess.check_output(['git','-C',args.repo,'rev-parse','HEAD'],text=True).strip()
    dirty=subprocess.check_output(['git','-C',args.repo,'status','--porcelain'],text=True).strip()
    if revision!='92d63d4e8bb4df75c3b71618f31ddde2378b2bcd' or dirty:
        raise ValueError('Pinned clean nanochat checkout required')
    sys.path.insert(0,str(Path(args.repo).resolve()))
    from nanochat.tokenizer import RustBPETokenizer
    tokenizer=RustBPETokenizer.from_directory(args.tokenizer)
    if args.command=='tool-inventory':
        result=tool_inventory(tokenizer,root/'tool-candidates')
        print(json.dumps({'status':'tool_inventory_not_admitted','milestones':result['milestones']}),flush=True)
        return
    if args.command=='combine':
        result=combine_counted(root/'general',tokenizer,root/'combined',tool_per_family=args.tools_per_family)
        print(json.dumps({'status':'combined_not_admitted','stats':result['stats']}),flush=True)
        return
    for name,size,digest in FILES:
        path=root/'source'/name
        if path.stat().st_size!=size or sha(path)!=digest:raise ValueError('Source identity mismatch '+name)
    source={'repository':REPOSITORY,'revision':REVISION,'license':'Apache-2.0 (upstream dataset card)',
            'files':[{'file':n,'bytes':s,'sha256':h} for n,s,h in FILES]}
    rows={'validation':parquet_rows([root/'source'/FILES[0][0]]),
          'train':parquet_rows([root/'source'/f[0] for f in FILES[1:]])}
    manifest=process_rows(rows,tokenizer,root/'general',source_identity=source)
    print(json.dumps({'status':'prepared_not_admitted','train':manifest['train'],'validation':manifest['validation']}),flush=True)


if __name__=='__main__':main()
