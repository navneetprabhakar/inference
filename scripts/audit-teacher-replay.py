#!/usr/bin/env python3
"""Bounded offline fixture replay. This never invokes a real conversation teacher."""
# Creator: Navneet Prabhakar
import argparse
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
from slm.data.schema import digest
from slm.teacher.journal import Journal
from slm.teacher.providers import Replay
from slm.teacher.workflow import Recipe,request_payload,generate
from slm.teacher.scenarios import fixture_scenario,output_schema,execute_mock,validate


def demonstration(s):
    replies={'professional':'The total for two cups is 2500 minor currency units.',
        'casual':'Two cups come to 2500 minor currency units.',
        'terse':'Total: 2500 minor currency units.',
        'humorous':'Two cups, one bill: 2500 minor currency units.',
        'caveman':'Two cups. Total 2500 minor currency units. No quantity change.'}
    return {'reply':'How many cups do you need?' if s['task']=='clarification' else replies[s['style']],
        'facts':deepcopy(s['facts']),'action':deepcopy(s['expected_action']),
        'tool_result':execute_mock(s['expected_action']),'style':s['style'],'content_category':s['content_category']}


def audit(output,report_file):
    output,report_file=Path(output),Path(report_file)
    if output.exists() or report_file.exists():raise FileExistsError('Fresh audit destinations required')
    output.mkdir(parents=True)
    recipe=Recipe('Offline handcrafted fixture, not a model teacher','offline-fixture-v1',Replay.identity)
    jobs=[];replays={}
    for task in ('conversation','clarification','correction','style_pair','tool_trajectory','student_correction'):
        for style in ('professional','casual','terse','humorous','caveman'):
            scenario=fixture_scenario(task,style);schema=output_schema(scenario)
            payload=request_payload(recipe,scenario,schema);value=demonstration(scenario)
            response={'id':'fixture-'+digest(payload)[:16],'model':recipe.model_id,'status':'completed',
                'service_tier':'default','usage':{'input_tokens':0,'output_tokens':0},
                'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':json.dumps(value)}]}]}
            jobs.append((scenario,schema));replays[digest(payload)]=response
    provider=Replay(replays);journal=Journal(output/'journal.sqlite',0,'offline-fixture-only',max_requests=len(jobs))
    results=[]
    for scenario,schema in jobs:
        result=generate(journal,provider,recipe,scenario,schema,validate,'structured-oracle-v1')
        assert result['validation']['status']=='pending_human_review'
        assert not result['validation']['training_eligible']
        results.append(result)
    for scenario,schema in jobs:
        assert generate(journal,provider,recipe,scenario,schema,validate,'structured-oracle-v1')['cache_hit']
    assert provider.calls==len(jobs)
    (output/'records.jsonl').write_text(''.join(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n' for r in results))
    report={'scope':'Handcrafted offline fixture replay only; not teacher generation, model-quality evidence or a reviewed dataset',
        'unique_requests':len(jobs),'repeated_cache_hits':len(jobs),'fixture_provider_calls':provider.calls,
        'live_http_calls':0,'real_teacher_outputs':0,'training_eligible':0,'human_approvals':0,
        'tasks':sorted({s['task'] for s,_ in jobs}),'style_labels':sorted({s['style'] for s,_ in jobs}),
        'unique_families':len({s['family_id'] for s,_ in jobs}),
        'free_text_quality_verified':False,'style_verified':False,'content_verified':False,
        'records_sha256':digest(results),'recipe':asdict(recipe),'journal':journal.summary()}
    report_file.parent.mkdir(parents=True,exist_ok=True)
    report_file.write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--report',required=True)
    a=p.parse_args();print(json.dumps(audit(a.output,a.report),indent=2))
