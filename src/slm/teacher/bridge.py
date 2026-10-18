"""Offline CLI-cache to reviewable transcripts. Never generates or grants approval."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from slm.data.schema import digest,make_example
from slm.teacher.cli import CLIRecipe,OVERRIDES,PROMPT_V1,PROMPT_V2,SUPPORTED_VERSION,check_raw,render_prompt
from slm.teacher.workflow import INSTRUCTIONS,check_scenario,check_schema,evaluate_response,parse_json
from slm.teacher.scenarios import output_schema,validate
from slm.tools.local import LocalTools,Session
from slm.tools.protocol import canonical,validate_messages

VERSION='cli-host-transcript-v1'
HOST_MAPPING={'teacher_tool':'multiply_amount','host_tool':'arithmetic','operation':'multiply',
    'arguments':{'unit_price_minor':'left','quantity':'right'},'result':{'total_minor':'value'}}
REVIEW_FIELDS=('reply_meaning_verified','style_content_verified','history_conversion_verified','host_grounding_verified')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def cached_response(journal_path,key):
    """Read-only SQLite URI: no journal creation, reserve, reconcile or provider call."""
    if not isinstance(key,str) or len(key)!=64 or any(c not in '0123456789abcdef' for c in key):
        raise ValueError('Canonical request digest required')
    path=Path(journal_path).resolve(strict=True)
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT status,response,response_hash FROM requests WHERE key=?',(key,)).fetchone()
    if row is None or row[0]!='complete':raise ValueError('Completed CLI cache entry required; no generation allowed')
    raw=parse_json(row[1])
    if digest(raw)!=row[2]:raise ValueError('Cached response checksum differs')
    return raw


def schema_order(value):
    if isinstance(value,dict):return {k:sorted(v) if k=='required' else schema_order(v) for k,v in value.items()}
    if isinstance(value,list):return [schema_order(v) for v in value]
    return value


def verify_record(record,journal_path):
    # Never reconstruct a generation request or reserve a cache miss. V1 schema arrays
    # encode historical insertion order; compare their meaning without changing the key.
    request=record['request'];key=record['request_key']
    if set(request)!={'scenario','schema','recipe','instructions','provider','cli_version','controls'} or digest(request)!=key:
        raise ValueError('Teacher request binding differs')
    recipe=CLIRecipe(**request['recipe']);scenario=request['scenario'];check_scenario(scenario)
    if (request['provider']!='codex-cli-chatgpt-v1' or request['cli_version']!=SUPPORTED_VERSION
        or request['instructions']!=INSTRUCTIONS or request['controls']!=OVERRIDES
        or record['provider']!=request['provider'] or record['cli_version']!=request['cli_version']
        or record['recipe']!=asdict(recipe) or record['requested_model']!=recipe.model_id
        or record['resolved_model'] is not None or record['scenario_sha256']!=digest(scenario)
        or record['family_id']!=scenario['family_id'] or record['split']!='train'
        or scenario['content_category']!='sfw'):
        raise ValueError('Teacher identity, scenario or controls differ')
    schema=request['schema'];check_schema(schema)
    if schema_order(schema)!=schema_order(output_schema(scenario)):raise ValueError('Teacher oracle schema differs')
    submitted=hashlib.sha256(render_prompt(scenario,recipe.prompt_version)).hexdigest()
    # Oldest v1 record predates this field; absence is recorded, never invented as old evidence.
    if record.get('submitted_prompt_sha256',submitted)!=submitted:raise ValueError('Submitted teacher prompt differs')
    if recipe.prompt_version==PROMPT_V2 and 'submitted_prompt_sha256' not in record:
        raise ValueError('V2 submitted-prompt hash required')
    raw=cached_response(journal_path,key);check_raw(raw,recipe)
    if record['provider_response_sha256']!=digest(raw) or record['usage']!=raw['usage']:
        raise ValueError('Teacher response binding differs')
    checked=evaluate_response(raw,schema,scenario,validate,'structured-oracle-v1')
    if checked['status']!='pending_human_review' or not checked['semantic_passed']:
        raise ValueError('Teacher structured oracle rejected candidate')
    if digest(record['validation'].get('candidate'))!=digest(checked['candidate']):
        raise ValueError('Recorded candidate differs from cached response')
    return scenario,checked['candidate'],recipe,submitted


def normalize(record,journal_path,output_format='typed',*,parent_release=None):
    if output_format not in ('plain','typed'):raise ValueError('Explicit plain or typed output required')
    scenario,candidate,recipe,submitted=verify_record(record,journal_path)
    parent_proofs=[];parent_manifest=None
    if scenario['parents']:
        if parent_release is None:raise ValueError('Verified reviewed parent release required for derived teacher scenarios')
        from slm.data.review import training_examples
        parent_manifest=sha(Path(parent_release)/'manifest.json')
        parents={e['example_id']:e for e in training_examples(parent_release)}
        for parent in scenario['parents']:
            actual=parents.get(parent['example_id'])
            if actual is None or actual['parent_group_id'].removeprefix('family:')!=parent['family_id'].removeprefix('family:'):
                raise ValueError('Teacher parent is not an approved train member of the declared family')
            parent_proofs.append({'example_id':actual['example_id'],'record_sha256':digest(actual),
                'source':actual['source'],'source_revision':actual['source_revision'],'license_record':actual['license_record'],
                'parent_group_id':actual['parent_group_id'],'split':'train'})
        if sha(Path(parent_release)/'manifest.json')!=parent_manifest:raise ValueError('Parent release changed during composition')
    context=deepcopy(scenario['context'])
    if context[-1]['role']!='user' or any(m['role']=='tool' for m in context):
        raise ValueError('Bridge requires user-ended plain history; partial tool exchanges are unsupported')
    expected='user'
    for i,m in enumerate(context):
        if m['role']=='system' and i==0:continue
        if m['role']!=expected or not m['content'].strip():raise ValueError('Alternating nonempty user/assistant history required')
        expected='assistant' if expected=='user' else 'user'
    if not isinstance(candidate['reply'],str) or not 0<len(candidate['reply'].strip())<600:
        raise ValueError('Bounded nonempty continuation reply required')
    kind=candidate['action'].get('kind')
    if kind not in ('answer','clarify','call'):raise ValueError('Supported teacher action kind required')
    missing=sorted(k for k,v in candidate['facts'].items() if v is None) if kind=='clarify' else []
    if kind=='clarify' and not missing:raise ValueError('Clarification needs explicit unknown fact fields')
    if kind=='call' and output_format!='typed':raise ValueError('Tool exchange requires typed output')
    if kind!='call' and (candidate['action'].get('name') is not None or candidate['action'].get('arguments')!={}):
        raise ValueError('Non-tool action must not carry a tool name or arguments')
    control=f"Response style: {scenario['style']}. Content setting: {scenario['content_category']}."
    if context[0]['role']=='system':context[0]['content']+='\n'+control
    else:context.insert(0,{'role':'system','content':control})
    registry=LocalTools();context_hash=None;history_wrapped=0
    if output_format=='typed':
        from slm.inference.tools import tool_context
        header=tool_context(registry);context_hash=digest(header);context[0]['content']+='\n'+header
        for message in context:
            if message['role']=='assistant':
                # This is quoted old assistant text, NOT asserted verified facts or new targets.
                message['content']=canonical({'kind':'answer','text':message['content'],'facts':{}});history_wrapped+=1
    history_messages=len(context);messages=deepcopy(context);mapping=None;host_result=None
    facts=deepcopy(candidate['facts'])
    if kind=='call':
        action=candidate['action'];args=action['arguments']
        if action['name']!='multiply_amount':raise ValueError('No registered bridge for teacher mock name')
        if any(digest(facts.get(k))!=digest(args[k]) for k in ('unit_price_minor','quantity')):
            raise ValueError('Teacher facts and call arguments disagree')
        if facts.get('currency')!='fixture_minor_units':raise ValueError('Only synthetic minor-unit tool scenarios are registered')
        call={'kind':'call','id':'teacher_'+record['request_key'][:24],'name':'arithmetic',
            'arguments':{'operation':'multiply','left':args['unit_price_minor'],'right':args['quantity']}}
        session=Session(registry);host_result=session.call(call)
        if not host_result['ok'] or digest(host_result['data']['value'])!=digest(candidate['tool_result']['total_minor']):
            raise ValueError('Registered host result disagrees with teacher mock oracle')
        facts['total_minor']=host_result['data']['value']
        messages.extend([{'role':'assistant','content':canonical(call)}, {'role':'tool','content':canonical(host_result)}])
        mapping=deepcopy(HOST_MAPPING)
    if output_format=='plain':messages.append({'role':'assistant','content':candidate['reply']})
    else:
        if kind=='clarify':
            final={'kind':'clarify','question':candidate['reply'],'missing':missing}
        else:final={'kind':'answer','text':candidate['reply'],'facts':facts}
        messages.append({'role':'assistant','content':canonical(final)})
        validate_messages(messages)
    from slm.data.holdout import check_training_context
    check_training_context(messages,(scenario['scenario_id'],scenario['family_id']))
    proof={'version':VERSION,'teacher_record_sha256':digest(record),'request_key':record['request_key'],
        'provider_response_sha256':record['provider_response_sha256'],'scenario_sha256':digest(scenario),
        'scenario_id':scenario['scenario_id'],'family_id':scenario['family_id'],'parent_lineage':deepcopy(scenario['parents']),
        'verified_parent_records':parent_proofs,'parent_release_manifest_sha256':parent_manifest,
        'requested_model':recipe.model_id,'resolved_model':None,'prompt_version':recipe.prompt_version,
        'reconstructed_prompt_sha256':submitted,'submitted_prompt_hash_previously_recorded':'submitted_prompt_sha256' in record,
        'output_format':output_format,'registry_sha256':registry.fingerprint if output_format=='typed' else None,
        'host_context_sha256':context_hash,'history_assistant_wrappers':history_wrapped,
        'history_messages':history_messages,'generated_messages':len(messages)-history_messages,
        'host_mapping':mapping,'host_result':host_result,'composed_messages_sha256':digest(messages),
        'legacy_tool_reply_role_ambiguous':kind=='call' and recipe.prompt_version==PROMPT_V1,
        'automated_scope':'Structured metadata and registered host result only; no prose, style, rights or human approval',
        'human_attestation':False,'training_eligible':False}
    return {'version':1,'kind':'teacher-transcript-candidate-v1','scenario_id':scenario['scenario_id'],
        'family_id':scenario['family_id'],'style':scenario['style'],'content_category':scenario['content_category'],
        'messages':messages,'proof':proof,'supervision':'last-user-turn-v1','training_eligible':False,
        'required_human_checks':list(REVIEW_FIELDS),'source_evidence_supplied':False}


def source_example(record,journal_path,source,output_format='typed',*,parent_release=None):
    if source.review_status!='sample_only':raise ValueError('Teacher bridge only emits sample-only source records')
    if 'codex-cli-chatgpt-v1' not in source.upstream_origins:raise ValueError('Source must declare CLI teacher origin')
    preview=normalize(record,journal_path,output_format,parent_release=parent_release)
    task='tool_dialogue' if output_format=='typed' else 'student_correction' if record['request']['scenario']['task']=='student_correction' else record['request']['scenario']['task']
    return make_example(source,record['request_key'],'family:'+preview['family_id'],deepcopy(preview['messages']),
        official_split='train',task=task,style=preview['style'],content_category=preview['content_category'],language='unknown',
        lineage=['teacher-request:'+record['request_key'],'teacher-response:'+record['provider_response_sha256']],
        upstream_references=[record['provider']],validation_results={'supervision':'last-user-turn-v1','teacher_bridge':preview['proof']})


def review_requirements(record):
    """Check composed receipt integrity; human decisions still supply qualitative gates."""
    proof=record['validation_results']['teacher_bridge'];messages=record['messages']
    if (proof.get('version')!=VERSION or proof.get('composed_messages_sha256')!=digest(messages)
        or record['validation_results'].get('supervision')!='last-user-turn-v1'
        or record['parent_group_id']!='family:'+proof.get('family_id','')
        or proof.get('training_eligible') is not False or proof.get('human_attestation') is not False
        or proof.get('output_format') not in ('plain','typed')):
        raise ValueError('Teacher composition receipt differs')
    n=proof.get('history_messages')
    if (type(n) is not int or not 1<=n<len(messages) or messages[n-1]['role']!='user'
        or any(m['role']=='user' for m in messages[n:])
        or proof.get('generated_messages')!=len(messages)-n):
        raise ValueError('Teacher continuation boundary differs')
    if proof['output_format']=='typed':
        from slm.inference.tools import tool_context
        registry=LocalTools();validate_messages(messages)
        if (record['task']!='tool_dialogue' or proof.get('registry_sha256')!=registry.fingerprint
            or proof.get('host_context_sha256')!=digest(tool_context(registry))
            or not messages[0]['content'].endswith(tool_context(registry))):
            raise ValueError('Teacher host context differs')
        suffix=messages[n:]
        if proof.get('host_mapping') is not None:
            if len(suffix)!=3 or [m['role'] for m in suffix]!=['assistant','tool','assistant']:
                raise ValueError('Teacher host exchange differs')
            call=parse_json(suffix[0]['content'])
            if proof['host_mapping']!=HOST_MAPPING or call['name']!='arithmetic' or call['arguments'].get('operation')!='multiply':
                raise ValueError('Teacher host mapping differs')
            result=Session(registry).call(call)
            if digest(result)!=digest(proof.get('host_result')) or digest(result)!=digest(parse_json(suffix[1]['content'])):
                raise ValueError('Teacher host grounding differs')
            final=parse_json(suffix[-1]['content'])
            if final['kind']!='answer' or digest(final['facts'].get('total_minor'))!=digest(result['data']['value']):
                raise ValueError('Teacher final structured total differs from host result')
        elif len(suffix)!=1:raise ValueError('Unexpected teacher continuation messages')
    elif len(messages)-n!=1 or proof.get('host_mapping') is not None:
        raise ValueError('Plain teacher continuation cannot contain a tool exchange')
    return REVIEW_FIELDS


def snapshot(record_files,journal_path,source_record,output,output_format='typed',*,parent_release=None):
    """Caller supplies pinned actual terms/card evidence; review remains separate."""
    from slm.data.build import read_source
    from slm.data.curation import curate
    output=Path(output);source_record=Path(source_record)
    if output.exists():raise FileExistsError(output)
    if not 1<=len(record_files)<=20:raise ValueError('One to twenty bounded cached teacher records required')
    source=read_source(source_record);examples=[];inputs={}
    for path in map(Path,record_files):
        if path.stat().st_size>256*1024:raise ValueError('Bounded teacher record required')
        raw=path.read_bytes()
        if len(raw)>256*1024:raise ValueError('Bounded teacher record required')
        record=parse_json(raw.decode());examples.append(source_example(record,journal_path,source,output_format,parent_release=parent_release))
        inputs[record['request_key']]=hashlib.sha256(raw).hexdigest()
    if len(inputs)!=len(examples):raise ValueError('Duplicate teacher requests refused')
    items,report=curate(examples,{source.source_id:source})
    if len(items)!=len(examples):raise ValueError('Teacher composition needs manual privacy/quality repair; no partial snapshot')
    originals={e.example_id:e for e in examples}
    if any(e.messages!=originals[e.example_id].messages for e in items):
        raise ValueError('Curation changed composed teacher text; manual repair and fresh composition required')
    report.update(scope='Composed CLI teacher candidates only; no training approval',teacher_bridge_version=VERSION,
        teacher_records=inputs,human_attestation=False,training_eligible=False)
    output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.teacher-snapshot-',dir=output.parent))
    try:
        for split in ('train','validation','test'):
            selected=[e for e in items if e.split==split]
            if selected:(temp/f'{split}-00000.jsonl').write_text(''.join(json.dumps(e.to_dict(),sort_keys=True,ensure_ascii=False)+'\n' for e in selected))
        # Retain exact evidence bytes, not just claims or hashes. Recheck after copying.
        descriptor=parse_json(source_record.read_text())
        for key,field in [('card','card_sha256'),('license','license_text_sha256')]:
            path=source_record.parent/descriptor['evidence_files'][key]
            if path.stat().st_size>1024*1024:raise ValueError('Teacher source evidence exceeds bound')
            target=temp/f'source-{key}.txt';target.write_bytes(path.read_bytes())
            if sha(target)!=getattr(source,field):raise ValueError('Teacher source evidence changed')
        (temp/'sources.json').write_text(json.dumps({source.source_id:asdict(source)},sort_keys=True,indent=2)+'\n')
        (temp/'heldout-groups.json').write_text(json.dumps(report['heldout_groups'],sort_keys=True,indent=2)+'\n')
        (temp/'report.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
        manifest={'version':1,'release':'sample_only','teacher_bridge_version':VERSION,
            'source_descriptor_sha256':sha(source_record),'bridge_sha256':sha(__file__),
            'files':{p.name:sha(p) for p in sorted(temp.iterdir())}}
        (temp/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
        os.rename(temp,output)
    except BaseException:shutil.rmtree(temp,ignore_errors=True);raise
    return report


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--record',action='append',required=True)
    p.add_argument('--journal',required=True);p.add_argument('--output',required=True);p.add_argument('--format',choices=['plain','typed'],default='typed')
    p.add_argument('--parent-release',help='Verified reviewed release for declared derivative parents')
    p.add_argument('--source-record',help='Pinned source descriptor with actual terms/card evidence; absent produces preview only')
    a=p.parse_args()
    if a.source_record:result=snapshot(a.record,a.journal,a.source_record,a.output,a.format,parent_release=a.parent_release)
    else:
        if len(a.record)!=1:p.error('Preview accepts one record; snapshot accepts a bounded list')
        source=Path(a.record[0])
        if source.stat().st_size>256*1024:raise ValueError('Bounded teacher record required')
        result=normalize(parse_json(source.read_text()),a.journal,a.format,parent_release=a.parent_release)
        with Path(a.output).open('x') as f:f.write(json.dumps(result,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'kind':result.get('kind','sample_only_snapshot'),'training_eligible':False},sort_keys=True))


if __name__=='__main__':main()
