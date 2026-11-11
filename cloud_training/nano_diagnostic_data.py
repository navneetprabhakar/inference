"""Prepare a deterministic SFT diagnostic CANDIDATE; never admits or trains it."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import unicodedata
from cloud_training.nano_data import sha256_file
from cloud_training.nano_chat_format import encode_conversation,VERSION


def text_hash(text):
    normalized=' '.join(unicodedata.normalize('NFKC',text).casefold().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def user_hashes(row):
    return {text_hash(m['content']) for m in row['messages'] if m['role']=='user'}


def fingerprint(row):
    return hashlib.sha256(json.dumps({'messages':row['messages'],'policies':row.get('policies')},
        sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def choose(path,count,forbidden,seen,excluded_ids=()):
    selected=[];rejected=0
    with Path(path).open() as f:
        for line in f:
            row=json.loads(line);fp=fingerprint(row)
            if row.get('id') in excluded_ids or fp in seen or user_hashes(row)&forbidden:rejected+=1;continue
            seen.add(fp);selected.append(row)
            if len(selected)==count:break
    if len(selected)!=count:raise ValueError('Insufficient disjoint source sessions')
    return selected,rejected


def write_json(path,value):
    with Path(path).open('x') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')


def prepare(general,tools,tokenizer_dir,repo,suite,output,exclusions=None):
    general,tools,output=Path(general),Path(tools),Path(output)
    if output.exists():raise FileExistsError(output)
    excluded_ids=set()
    exclusion_receipt=None
    if exclusions:
        exclusion_receipt=json.loads(Path(exclusions).read_text())
        excluded_ids={e['id'] for e in exclusion_receipt['excluded_conversations']}
    sources=[];manifests={}
    for name,directory in [('general',general),('tools',tools)]:
        m=json.loads((directory/'manifest.json').read_text());manifests[name]=m
        if m['format_version']!=VERSION or m['context_tokens']!=2048:raise ValueError('Source format mismatch')
        for split in ('train','validation'):
            path=directory/m[split]['file']
            if sha256_file(path)!=m[split]['sha256']:raise ValueError('Source JSONL changed')
            sources.append({'kind':name,'split':split,'file':str(path),'sha256':m[split]['sha256'],
                'manifest_sha256':sha256_file(directory/'manifest.json')})
    tokenizer_sha=sha256_file(Path(tokenizer_dir)/'tokenizer.pkl')
    if any(m['tokenizer_sha256']!=tokenizer_sha for m in manifests.values()):raise ValueError('Tokenizer mismatch')
    sys.path.insert(0,str(Path(repo).resolve()))
    from nanochat.tokenizer import RustBPETokenizer
    tokenizer=RustBPETokenizer.from_directory(str(tokenizer_dir))
    exposed=json.loads(Path(suite).read_text())
    if exposed['purpose']!='development_only_never_train':raise ValueError('Only exposed dev suite allowed')
    quality_users={text_hash(t['user']) for s in exposed['sessions'] for t in s['turns']}
    forbidden=set(quality_users)
    # Protect ALL existing dev user prompts, not only the selected diagnostic dev.
    for directory in (general,tools):
        with (directory/'validation.jsonl').open() as f:
            for line in f:forbidden.update(user_hashes(json.loads(line)))
    rows={};rejections={};seen=set()
    for split,counts in [('validation',(256,128)),('train',(4096,2048))]:
        selected=[]
        for (name,directory),count in zip([('general',general),('tools',tools)],counts):
            subset,rejected=choose(directory/(split+'.jsonl'),count,quality_users if split=='validation' else forbidden,seen,excluded_ids)
            rejections[name+'/'+split]=rejected
            for row in subset:
                row=dict(row);row['diagnostic_source']=name;selected.append(row)
        # Stable mixed ordering, independent of Python hash and checkpoint.
        rows[split]=sorted(selected,key=lambda r:hashlib.sha256(('diagnostic103:'+fingerprint(r)).encode()).hexdigest())
    stats={}
    for split,items in rows.items():
        targets=positions=0;lengths=[];families={}
        for row in items:
            rendered=encode_conversation(tokenizer,row['messages'],policies=row.get('policies'),context=2048)
            n=len(rendered['ids']);t=sum(rendered['mask'][1:]);lengths.append(n);targets+=t;positions+=n
            if t<1:raise ValueError('No assistant targets')
            row['sequence_tokens']=n;row['assistant_target_count']=t
            family=row.get('family',row['diagnostic_source']);families[family]=families.get(family,0)+1
        stats[split]={'sessions':len(items),'assistant_targets':targets,'serialized_positions':positions,
                      'maximum_sequence_tokens':max(lengths),'family_counts':families,'lengths':lengths}
    output.mkdir(parents=True)
    manifest={'schema':1,'training_admitted':False,'tokenizer_sha256':tokenizer_sha,
              'format_version':VERSION,'context_tokens':2048}
    for split in ('train','validation'):
        path=output/(split+'.jsonl')
        with path.open('x') as f:
            for row in rows[split]:f.write(json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n')
        manifest[split]={'file':path.name,'sha256':sha256_file(path),'bytes':path.stat().st_size,
                         **{k:v for k,v in stats[split].items() if k!='lengths'}}
    review={'schema':1,'training_admitted':False,'status':'candidate_pending_root_review',
        'tokenizer_sha256':tokenizer_sha,'format_version':VERSION,
        'jsonl_sha256':[manifest[k]['sha256'] for k in ('train','validation')],
        'sources':sources,'quality_suite_sha256':sha256_file(suite),
        'exclusion':'Normalized exact user-message overlap against ALL source dev and exposed quality prompts; whole-conversation dedup across selected splits.',
        'selection':'First eligible sessions from immutable source order, then SHA256(diagnostic103:conversation_fingerprint) mixed order.',
        'rejections':rejections,'known_error_exclusions':exclusion_receipt,
        'exclusions_sha256':sha256_file(exclusions) if exclusions else None,'limits':['No semantic near-duplicate or benchmark-contamination guarantee.',
            'Tool samples share templates; this is a small instruction-learning diagnostic, not usability acceptance.',
            'General source is public synthetic smol-smoltalk (Apache-2.0 upstream); tool source is local broker-generated.',
            'No sealed acceptance files accessed. Root must review and publish a separate admitted manifest/receipt.']}
    write_json(output/'admission-candidate.json',review)
    manifest['admission']={'receipt':'admission-candidate.json','sha256':sha256_file(output/'admission-candidate.json')}
    write_json(output/'manifest-candidate.json',manifest)
    write_json(output/'lengths.json',stats)
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('general','tools','tokenizer','repo','suite','output'):p.add_argument('--'+name,required=True)
    p.add_argument('--exclusions')
    a=p.parse_args();m=prepare(a.general,a.tools,a.tokenizer,a.repo,a.suite,a.output,a.exclusions)
    print(json.dumps({s:m[s] for s in ('train','validation')},indent=2))
