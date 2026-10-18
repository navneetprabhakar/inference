"""Raw-history evaluation, bound human reviews and fail-closed stage reports."""
from collections import defaultdict
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import tempfile
from slm.data.schema import digest
from slm.eval.cases import RUBRIC


def write_new(path,value):
    path=Path(path)
    if path.exists():raise FileExistsError(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.evaluation-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:json.dump(value,f,sort_keys=True,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n')
        # Link publishes a completed file atomically without replacing an existing result.
        os.link(name,path)
    finally:os.unlink(name)


def validate_suite(suite):
    if (set(suite)!={'version','suite_id','status','split','scope','cases'} or type(suite['version']) is not int
        or suite['version']!=1 or suite['split']!='test' or suite['status']!='candidate_pending_review'
        or not isinstance(suite['suite_id'],str) or not suite['suite_id'] or not 1<=len(suite['cases'])<=5000):
        raise ValueError('Bounded candidate test suite required')
    ids=set();scenarios={}
    for c in suite['cases']:
        if set(c)!={'id','family_id','scenario_id','slice','style','content_category','messages','oracle','reference'}:raise ValueError('Invalid case contract')
        for k in ('id','family_id','scenario_id','slice','style','reference'):
            if not isinstance(c[k],str) or not c[k]:raise ValueError('Nonempty case identities/reference required')
        if c['id'] in ids or c['content_category']!='sfw':raise ValueError('Unique SFW candidate cases required')
        ids.add(c['id'])
        if c['scenario_id'] in scenarios and scenarios[c['scenario_id']]!=c['family_id']:raise ValueError('Scenario family differs')
        scenarios[c['scenario_id']]=c['family_id']
        if not c['messages'] or c['messages'][-1].get('role') not in ('user','tool'):raise ValueError('User/tool-ended raw context required')
        for m in c['messages']:
            if set(m)!={'role','content'} or m['role'] not in ('system','user','assistant','tool') or not isinstance(m['content'],str):raise ValueError('Plain conversation messages required')
        oracle=c['oracle']
        if oracle.get('kind')=='exact':
            if (set(oracle)!={'kind','normalization','accepted'} or oracle['normalization']!='strip-only'
                or not oracle['accepted'] or any(not isinstance(v,str) or not v for v in oracle['accepted'])
                or c['reference'] not in oracle['accepted']):raise ValueError('Explicit exact answer contract required')
        elif oracle.get('kind')=='human':
            if set(oracle)!={'kind','rubric','required_facts'} or oracle['rubric']!=list(RUBRIC) or not oracle['required_facts']:raise ValueError('Complete human rubric required')
        else:raise ValueError('Unknown evaluation oracle')


def suite_review_packet(suite):
    validate_suite(suite)
    return {'version':1,'suite_hash':digest(suite),'reviewer':'Navneet Prabhakar','human_attestation':False,
        'cases':{c['id']:{'case_hash':digest(c),'approved':False,'notes':''} for c in suite['cases']}}


def reviewed_cases(suite,packet):
    expected=suite_review_packet(suite)
    if packet is None:return set()
    if (set(packet)!=set(expected) or type(packet['version']) is not int or packet['version']!=1
        or packet['suite_hash']!=expected['suite_hash'] or packet['reviewer']!='Navneet Prabhakar'
        or type(packet['human_attestation']) is not bool or set(packet['cases'])!=set(expected['cases'])):
        raise ValueError('Bound reviewed suite packet required')
    approved=set()
    for id,item in packet['cases'].items():
        if (set(item)!={'case_hash','approved','notes'} or item['case_hash']!=expected['cases'][id]['case_hash']
            or type(item['approved']) is not bool or not isinstance(item['notes'],str)):
            raise ValueError('Suite case review differs')
        if item['approved']:
            if not packet['human_attestation'] or not item['notes'].strip():raise ValueError('Human attestation and case-review evidence required')
            approved.add(id)
    return approved


def evaluate(suite,model,max_new_tokens=64):
    validate_suite(suite)
    if type(max_new_tokens) is not int or not 1<=max_new_tokens<=512:raise ValueError('Bounded generation budget required')
    rows=[]
    for c in suite['cases']:
        row={'id':c['id'],'case_hash':digest(c),'response':None,'generation_error':None,'reference_loss':None,'reference_error':None}
        try:row['response']=model.generate(deepcopy(c['messages']),max_new_tokens)
        except (ValueError,FloatingPointError) as exc:row['generation_error']={'type':type(exc).__name__,'message':str(exc)}
        # Reference scoring is separate and never passed to generate().
        try:row['reference_loss']=model.reference_loss(deepcopy(c['messages']),c['reference'])
        except (ValueError,FloatingPointError) as exc:row['reference_error']={'type':type(exc).__name__,'message':str(exc)}
        rows.append(row)
    return {'version':1,'suite_hash':digest(suite),'identity':deepcopy(model.identity),'max_new_tokens':max_new_tokens,
        'mode':'raw_model_generation','records':rows,'scope':'Unassisted recent conversation; no external state, constrained decoding, tool execution, repair or teacher fallback'}


def check_results(suite,result):
    validate_suite(suite)
    if (type(result.get('version')) is not int or result['version']!=1 or result.get('suite_hash')!=digest(suite)
        or result.get('mode')!='raw_model_generation' or not isinstance(result.get('identity'),dict)
        or type(result.get('max_new_tokens')) is not int or not 1<=result['max_new_tokens']<=512):
        raise ValueError('Bound raw evaluation results required')
    rows=result.get('records',[])
    if len(rows)!=len(suite['cases']) or [r['id'] for r in rows]!=[c['id'] for c in suite['cases']]:raise ValueError('Complete ordered results required; no omitted failures')
    for c,r in zip(suite['cases'],rows):
        if set(r)!={'id','case_hash','response','generation_error','reference_loss','reference_error'} or r['case_hash']!=digest(c):raise ValueError('Case/result binding differs')
        response=r['response']
        if response is None:
            if not isinstance(r['generation_error'],dict):raise ValueError('Missing generation must retain an error')
        else:
            fields={'text','token_ids','stop_reason','prompt_tokens','generated_tokens','content_tokens','ttft_seconds','seconds','max_new_tokens'}
            if (set(response)!=fields or r['generation_error'] is not None or not isinstance(response['text'],str)
                or response['stop_reason'] not in ('eos','message_end','length','invalid_structural')
                or response['max_new_tokens']!=result['max_new_tokens']):raise ValueError('Invalid generation record')
            for k in ('prompt_tokens','generated_tokens','content_tokens'):
                if type(response[k]) is not int or response[k]<0:raise ValueError('Invalid generation count')
            if (not isinstance(response['token_ids'],list) or len(response['token_ids'])!=response['generated_tokens']
                or not 1<=response['generated_tokens']<=result['max_new_tokens']
                or any(type(v) is not int or v<0 for v in response['token_ids'])):raise ValueError('Invalid raw generated IDs')
            for k in ('ttft_seconds','seconds'):
                if type(response[k]) not in (int,float) or not math.isfinite(response[k]) or response[k]<0:raise ValueError('Invalid timing')
            stops={'eos':1,'message_end':3}
            raw=response['token_ids'];reason=response['stop_reason']
            if (response['prompt_tokens']<1 or response['ttft_seconds']>response['seconds']
                or (reason in stops and (raw[-1]!=stops[reason] or any(v<10 for v in raw[:-1])))
                or (reason=='length' and (len(raw)!=result['max_new_tokens'] or any(v<10 for v in raw)))
                or (reason=='invalid_structural' and (not 0<=raw[-1]<10 or raw[-1] in (1,3) or any(v<10 for v in raw[:-1])))
                or response['content_tokens']!=len(raw)-(reason!='length')):raise ValueError('Inconsistent raw stop/count record')
        loss=r['reference_loss']
        if loss is None:
            if not isinstance(r['reference_error'],dict):raise ValueError('Missing reference score needs error')
        elif (set(loss)!={'nll_sum','content_targets','utf8_bytes','scope'} or r['reference_error'] is not None
              or type(loss['nll_sum']) not in (int,float) or not math.isfinite(loss['nll_sum']) or loss['nll_sum']<0
              or type(loss['content_targets']) is not int or loss['content_targets']<1
              or type(loss['utf8_bytes']) is not int or loss['utf8_bytes']!=len(c['reference'].encode('utf-8'))):raise ValueError('Invalid reference loss')


def output_review_packet(suite,result):
    check_results(suite,result)
    return {'version':1,'suite_hash':digest(suite),'result_hash':digest(result),'reviewer':'Navneet Prabhakar','human_attestation':False,
        'cases':{c['id']:{'record_hash':digest(r),'grades':{k:None for k in RUBRIC},'notes':''}
            for c,r in zip(suite['cases'],result['records']) if c['oracle']['kind']=='human'}}


def human_grades(suite,result,packet):
    expected=output_review_packet(suite,result)
    if packet is None:return {}
    if (set(packet)!=set(expected) or type(packet['version']) is not int or packet['version']!=1
        or any(packet[k]!=expected[k] for k in ('suite_hash','result_hash','reviewer'))
        or type(packet['human_attestation']) is not bool or set(packet['cases'])!=set(expected['cases'])):raise ValueError('Bound output-review packet required')
    grades={}
    for id,row in packet['cases'].items():
        if (set(row)!={'record_hash','grades','notes'} or row['record_hash']!=expected['cases'][id]['record_hash']
            or set(row['grades'])!=set(RUBRIC) or not isinstance(row['notes'],str)
            or any(v is not None and type(v) is not bool for v in row['grades'].values())):raise ValueError('Invalid human rubric grades')
        if all(type(v) is bool for v in row['grades'].values()):
            if not packet['human_attestation'] or not row['notes'].strip():raise ValueError('Human grading requires attestation/evidence')
            grades[id]=row['grades']
    return grades


def interval(success,total):
    if not total:return None
    z=1.959963984540054;p=success/total;den=1+z*z/total
    center=(p+z*z/(2*total))/den;half=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [0 if success==0 else max(0,center-half),1 if success==total else min(1,center+half)]


def aggregate(rows):
    n=len(rows);mech=[r for r in rows if r['oracle']=='exact'];human=[r for r in rows if r['oracle']=='human']
    graded=[r for r in human if r['human_grades'] is not None];success=sum(r['exact_pass'] for r in mech)
    families=defaultdict(list);scenarios=defaultdict(list)
    for r in mech:families[r['family_id']].append(r['exact_pass']);scenarios[r['scenario_id']].append(r['exact_pass'])
    return {'cases':n,'scenarios':len({r['scenario_id'] for r in rows}),'template_families':len({r['family_id'] for r in rows}),
        'approved_cases':sum(r['suite_approved'] for r in rows),'generation_errors':sum(r['generation_error'] for r in rows),
        'exact_cases':len(mech),'exact_passes':success,'exact_rate':success/len(mech) if mech else None,
        'exact_case_wilson95_descriptive':interval(success,len(mech)),
        'exact_scenario_all_variants_pass_rate':sum(all(v) for v in scenarios.values())/len(scenarios) if scenarios else None,
        'exact_family_macro_rate':sum(sum(v)/len(v) for v in families.values())/len(families) if families else None,
        'human_cases':len(human),'human_graded':len(graded),'human_pending':len(human)-len(graded),
        'human_all_rubrics_passes':sum(all(r['human_grades'].values()) and r['terminated'] for r in graded),
        'human_rubric_rates':{k:sum(r['human_grades'][k] for r in graded)/len(graded) if graded else None for k in RUBRIC},
        'interval_scope':'Descriptive case-level interval; correlated scenario/style/template variants are not independent samples'}


def score(suite,result,*,suite_review=None,output_review=None):
    check_results(suite,result);approved=reviewed_cases(suite,suite_review);grades=human_grades(suite,result,output_review);rows=[]
    losses=[];times=[]
    for c,r in zip(suite['cases'],result['records']):
        response=r['response'];terminated=response is not None and response['stop_reason'] in ('eos','message_end') and bool(response['text'].strip())
        exact=bool(terminated and c['oracle']['kind']=='exact' and response['text'].strip() in c['oracle']['accepted'])
        rows.append({'id':c['id'],'family_id':c['family_id'],'scenario_id':c['scenario_id'],'slice':c['slice'],'style':c['style'],
            'oracle':c['oracle']['kind'],'suite_approved':c['id'] in approved,'exact_pass':exact,'terminated':terminated,
            'generation_error':r['generation_error'] is not None,'human_grades':grades.get(c['id'])})
        if r['reference_loss'] is not None:losses.append(r['reference_loss'])
        if response is not None:times.append(response['seconds'])
    nll=sum(v['nll_sum'] for v in losses);targets=sum(v['content_targets'] for v in losses);bytes_=sum(v['utf8_bytes'] for v in losses)
    slices={k:aggregate([r for r in rows if r['slice']==k]) for k in sorted({r['slice'] for r in rows})}
    styles={k:aggregate([r for r in rows if r['style']==k]) for k in sorted({r['style'] for r in rows})}
    return {'version':1,'suite_hash':digest(suite),'result_hash':digest(result),'suite_review_hash':digest(suite_review) if suite_review else None,
        'output_review_hash':digest(output_review) if output_review else None,'identity':result['identity'],'overall':aggregate(rows),'slices':slices,'styles':styles,
        'reference_loss':{'scored_cases':len(losses),'failed_cases':len(rows)-len(losses),'nll_sum':nll,'content_targets':targets,'utf8_bytes':bytes_,
            'mean_content_nll':nll/targets if targets else None,'bits_per_reference_byte':nll/math.log(2)/bytes_ if bytes_ else None,
            'scope':'One teacher-forced reference per case, excluding structural targets; not evidence of free-generation correctness'},
        'latency':{'completed_generations':len(times),'mean_seconds':sum(times)/len(times) if times else None,
            'scope':'All returned generations including length/structural failures; not a production latency acceptance sample'},
        'rows':rows,'scope':'Candidate SFW raw-history evaluation. Human language/style judgments remain pending unless bound reviews supplied. No tool execution or broad-conversation acceptance.'}
