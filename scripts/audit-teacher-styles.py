#!/usr/bin/env python3
"""Read-only teacher style/meaning observations; never grants approval."""
# Creator: Navneet Prabhakar
import argparse
from collections import defaultdict
from itertools import combinations
import json
from pathlib import Path
import sqlite3
from slm.data.schema import digest
from slm.teacher.bridge import verify_record,sha
from slm.teacher.styles import assess,compare,VERSION
from slm.teacher.workflow import parse_json


def audit(records,journal,report_file):
    report_file=Path(report_file)
    if report_file.exists():raise FileExistsError(report_file)
    if not 2<=len(records)<=20:raise ValueError('Two to twenty cached teacher records required')
    before=sha(journal);rows=[];groups=defaultdict(list);seen=set()
    for path in map(Path,records):
        raw=path.read_bytes()
        if len(raw)>256*1024:raise ValueError('Bounded teacher record required')
        record=parse_json(raw.decode());scenario,candidate,recipe,_=verify_record(record,journal)
        if record['request_key'] in seen:raise ValueError('Duplicate teacher request')
        seen.add(record['request_key']);diagnostic=assess(scenario,candidate)
        fields=('family_id','split','task','content_category','parents','context','facts','expected_action')
        group=digest({'semantic':{k:scenario[k] for k in fields},'requested_model':recipe.model_id,'prompt_version':recipe.prompt_version})
        groups[group].append((record,scenario,candidate))
        rows.append({'request_key':record['request_key'],'record_file':str(path),'record_file_sha256':__import__('hashlib').sha256(raw).hexdigest(),
            'prompt_version':recipe.prompt_version,'requested_model':recipe.model_id,'resolved_model':None,
            'comparison_group':group,'diagnostic':diagnostic})
    pairs=[]
    for group,items in sorted(groups.items()):
        for left,right in combinations(items,2):
            if left[1]['style']==right[1]['style']:continue
            compared=compare(left[1],left[2],right[1],right[2]);compared.pop('left');compared.pop('right')
            pairs.append({'comparison_group':group,'prompt_version':left[0]['recipe']['prompt_version'],
                'left_request_key':left[0]['request_key'],'right_request_key':right[0]['request_key'],**compared})
    if sha(journal)!=before:raise ValueError('Journal changed during read-only style audit')
    report={'version':1,'style_contract':VERSION,'scope':'Structured metadata checks and non-authorizing surface review cues; no free-text truth/style acceptance',
        'records':rows,'pairs':pairs,'record_count':len(rows),'pair_count':len(pairs),
        'surface_nonseparation_cues':sum(p['style_nonseparation_cue'] is True for p in pairs),
        'comparison_grouping':'Same semantic scenario, context, requested model and prompt version; no cross-version style-effect claim',
        'journal_unchanged':True,'journal_sha256':before,'new_generation_launches':0,'training_approvals':0,
        'meaning_equivalence_verified':False,'style_separation_verified':False,'human_attestation':False,
        'source_hashes':{p:sha(p) for p in ('src/slm/teacher/styles.py','src/slm/teacher/cli.py','src/slm/teacher/bridge.py','scripts/audit-teacher-styles.py')}}
    report_file.parent.mkdir(parents=True,exist_ok=True)
    with report_file.open('x') as f:f.write(json.dumps(report,indent=2)+'\n')
    return {'records':len(rows),'pairs':len(pairs),'surface_nonseparation_cues':report['surface_nonseparation_cues'],'journal_unchanged':True,'training_approvals':0}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--record',action='append',required=True);p.add_argument('--journal',required=True);p.add_argument('--report',required=True)
    a=p.parse_args();print(json.dumps(audit(a.record,a.journal,a.report),sort_keys=True))
