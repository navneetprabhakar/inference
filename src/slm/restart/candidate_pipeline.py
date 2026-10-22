"""Authorized one-candidate pipeline; final semantic review remains explicit.

Every stage owns its existing fail-closed authority and accounting checks. This
module adds no retry, model selection, budget extension or post-final training.
"""
from pathlib import Path
from . import candidate_launch,final_launch
from .supervisor import atomic_json


def run(project):
    binding=candidate_launch.prepare(Path(project))
    candidate=Path(binding['output'])
    pilot=candidate_launch.stage(binding,'pilot')
    if pilot['status']!='PILOT_PASS':
        result=dict(status='M1_INCOMPLETE_PILOT',pilot=pilot,final_research_pass=False)
        atomic_json(candidate/'pipeline-completion.json',result)
        return result
    continuation=candidate_launch.stage(binding,'continuation')
    if continuation['status'] not in ('NORMAL_BUDGET_END','PLATEAU_END','WORK_BUDGET_END'):
        raise ValueError('Continuation cannot advance to final evaluation')
    final=final_launch.launch(binding)
    if final['status']!='NARRATIVE_REVIEW_REQUIRED' or final['final_research_pass'] is not False:
        raise ValueError('Unexpected final assessment state')
    result=dict(status='NARRATIVE_REVIEW_REQUIRED',pilot=pilot,continuation=continuation,final=final,final_research_pass=False)
    atomic_json(candidate/'pipeline-completion.json',result)
    return result
