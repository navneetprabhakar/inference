"""Explicitly configured offline generation; shipped live configuration is disabled."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
from slm.teacher.journal import Journal
from slm.teacher.workflow import Recipe,Approval,generate,parse_json,request_payload
from slm.teacher.providers import OpenAIResponses
from slm.teacher.scenarios import output_schema,validate


def run(config_file,scenario_file,output):
    config_file=Path(config_file);output=Path(output)
    if output.exists():raise FileExistsError(output)
    config=parse_json(config_file.read_text())
    if config.get('live_enabled') is not True:raise ValueError('Live teacher generation is disabled')
    if config.get('approval') is None:raise ValueError('Explicit teacher terms/access/pricing/budget approval required')
    recipe=Recipe(**config['recipe']);approval=Approval(**config['approval'])
    if recipe.provider_id!=OpenAIResponses.identity:raise ValueError('Configured live adapter is unsupported')
    if (config['journal']['authorization_id']!=approval.authorization_id
        or type(config['journal']['cap_nanousd']) is not int or config['journal']['cap_nanousd']<=0):
        raise ValueError('Configured teacher spending authorization differs')
    scenario=parse_json(Path(scenario_file).read_text());schema=output_schema(scenario)
    request_payload(recipe,scenario,schema)  # validate before creating journal or any HTTP request
    path=Path(config['journal']['path'])
    if not path.is_absolute():path=config_file.resolve().parent/path
    journal=Journal(path,config['journal']['cap_nanousd'],approval.authorization_id,config['journal']['max_requests'])
    result=generate(journal,OpenAIResponses(),recipe,scenario,schema,validate,'structured-oracle-v1',approval)
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.teacher-result-',dir=output.parent))
    try:
        (temp/'record.json').write_text(json.dumps(result,sort_keys=True,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
        os.rename(temp,output)
    except BaseException:
        shutil.rmtree(temp,ignore_errors=True);raise
    return {'request_key':result['request_key'],'cache_hit':result['cache_hit'],
        'status':result['validation']['status'],'training_eligible':False,'journal':result['journal']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True);p.add_argument('--scenario',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(json.dumps(run(a.config,a.scenario,a.output),indent=2))


if __name__=='__main__':main()
