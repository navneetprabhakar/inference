"""Qualify admitted grounded 2+2+0 whole-session streams, CPU metadata only.
No private-case access, model execution, admission mutation or capability claim.
Original reports/own-base-sft-data-admission/qualify_extension.py stays unchanged.
"""
import collections,hashlib,json,pathlib,sqlite3
ROOT=pathlib.Path(__file__).resolve().parents[2]
EXPECTED_DATASET='5f6ad7fd13f9d87a0dbb4c61c234ff1855e0a67b424c41a07ec85b6467e23abe'
EXPECTED_DATABASE='69ec59f14944c73701405ad5a04370e186f60ece5403f08fc4ee7f721b0768e6'
EXPECTED_FINAL={'train':498,'exposed-development':54}
def sha(path):
 with pathlib.Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):return json.loads(pathlib.Path(path).read_bytes())
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def require(condition,reason):
 if not condition:raise ValueError(reason)
def main():
 d=ROOT/'data/grounded-session-aligned-v2';source=ROOT/'data/grounded-session-candidates-v2';out=d/'four-call-qualification.json'
 require(not any(p.exists() for p in [ROOT/'runs/STOP',d/'STOP',source/'STOP']),'STOP')
 require(not out.exists(),'preserve prior qualification')
 require(sha(d/'receipt.json')==EXPECTED_DATASET,'pinned aligned identity')
 receipt=read(d/'receipt.json');freeze=read(d/'freeze.json');proof=read(d/'independent-verification.json');admission=read(d/'diagnostic-admission.json')
 require(receipt['role']=='four_call_extension' and freeze['role']=='four_call_extension','role')
 require(sha(d/'freeze.json')==receipt['freeze_sha256'] and freeze['source']==str(source),'freeze identity')
 require(proof['state']=='PASS' and proof['failures']==[] and proof['dataset_sha256']==EXPECTED_DATASET,'independent stream proof')
 require(admission['training_admitted'] is True and admission['dataset_sha256']==EXPECTED_DATASET,'root diagnostic admission required')
 require(admission.get('quality_certified') is False and admission.get('launch_authorized') is False,'diagnostic-only admission')
 require(admission.get('verification_receipt')=='independent-verification.json','admission uses independent stream proof')
 pins={str(d/'receipt.json'):EXPECTED_DATASET,str(d/'independent-verification.json'):sha(d/'independent-verification.json'),str(d/'diagnostic-admission.json'):sha(d/'diagnostic-admission.json'),str(d/'freeze.json'):sha(d/'freeze.json'),str(pathlib.Path(__file__).resolve()):sha(__file__)}
 for relative,expected in freeze['pins'].items():
  path=(ROOT/relative).resolve();require(path.is_relative_to(ROOT),'freeze path escape');require(sha(path)==expected,'frozen dependency identity');pins[str(path)]=expected
 # The packed proof pins only dataset/runtime artifacts, never custody case text.
 for name,expected in proof['pins'].items():
  path=pathlib.Path(name).resolve();require(path.is_relative_to(ROOT),'packed proof path escape');require(sha(path)==expected,'independent proof dependency changed');pins[str(path)]=expected
 for name,metadata in receipt['outputs'].items():
  path=d/name;require(path.stat().st_size==metadata['bytes'] and sha(path)==metadata['sha256'],'packed output identity');pins[str(path)]=metadata['sha256']
 manifest=read(source/'candidate-manifest.json');candidate_proof=read(source/'candidate-verification.json')
 require(sha(source/'candidates.sqlite')==EXPECTED_DATABASE==manifest['database']['sha256']==candidate_proof['database_sha256'],'candidate DB identity')
 require(candidate_proof['state']=='PASS_independent_grounded_candidates_not_admitted' and candidate_proof['failures']==[] and candidate_proof['manifest_sha256']==sha(source/'candidate-manifest.json'),'independent semantic proof')
 excluded=set();custody_pins={}
 for name,key in [('custody.json','pins'),('public-development-custody.json','candidate_pins')]:
  custody=read(source/name);require(custody['state']=='screened_not_admitted' and custody['training_admitted'] is False,'custody state')
  require(custody['counts']['reviewed']==candidate_proof['verified_rows'],'complete custody inventory')
  for artifact in ['candidates.sqlite','candidate-manifest.json']+(['candidate-verification.json'] if name.startswith('public') else []):require(custody[key][artifact]==sha(source/artifact),'custody candidate identity')
  require(len(custody['excluded_doc_ids'])==len(set(custody['excluded_doc_ids']))==custody['counts']['excluded'],'unique custody exclusions')
  excluded.update(custody['excluded_doc_ids']);custody_pins[name]=sha(source/name)
 require(len(excluded)==freeze['exclusion_union_count']==receipt['exclusion_union_count']==proof['exclusion_union_count'],'custody union identity')
 counts={};seen=set();targets={};binding_count=0
 with sqlite3.connect(f'file:{source}/candidates.sqlite?mode=ro',uri=True) as db:
  db.row_factory=sqlite3.Row;require(db.execute('pragma integrity_check').fetchone()[0]=='ok','database integrity')
  require(db.execute('select count(*) from documents').fetchone()[0]==candidate_proof['verified_rows'],'candidate population')
  retained={r['doc_id'] for r in db.execute('select doc_id from documents')} - excluded
  for split,expected_number in EXPECTED_FINAL.items():
   index=[json.loads(line) for line in (d/f'{split}.index.jsonl').open()];groups=collections.defaultdict(list)
   for entry in index:groups[entry['doc_id']].append(entry)
   require(len(groups)==expected_number and len(index)==3*expected_number,'complete three-prefix population')
   require(receipt['counts'][split]['histories']==expected_number and proof['counts'][split]['histories']==expected_number,'proof/receipt retained count')
   targets[split]=0
   for did,entries in groups.items():
    require(did in retained and did not in seen,'excluded/repeated source history');seen.add(did)
    require([e['turn'] for e in entries]==[0,1,2],'one prefix for each turn')
    row=db.execute('select * from documents where doc_id=?',(did,)).fetchone();require(row['split']==split,'source split')
    lesson=json.loads(row['original_lesson_json']);turns=json.loads(row['adapted_json']);metadata=json.loads(row['row_metadata_json']);require(hashlib.sha256(canonical(lesson).encode()).hexdigest()==did,'original lesson binding')
    require(len(turns)==len(metadata)==len(lesson['policy'])==3,'three-turn lesson')
    require([x['turn_index'] for x in turns]==[0,1,2] and [m['current_turn_calls'] for m in metadata]==[2,2,0],'2+2+0 source program')
    require([x['policy']['permit_calls'] for x in turns]==[True,True,False],'exact turn permissions')
    history=turns[-1]['history'];calls=[m for m in history if m['role']=='assistant' and 'call' in m];records=[m['record'] for m in history if m['role']=='tool']
    require(len(calls)==len(records)==4 and [r['call_id'] for r in records]==['c1','c2','c3','c4'],'four unique actual records')
    require(records==lesson['observations'],'all original observations retained')
    require(all(r['ok'] is True and r['source']=='offline fixture' and 'data' in r and 'error' not in r for r in records),'actual successful observations only')
    for call,record in zip(calls,records):
     require(call['call_id']==record['call_id'] and call['call']['name']==record['name'] and call['call']['arguments']==record['arguments'],'observed binding to exact proposal');binding_count+=1
    require([sum('call' in m for m in t['history']) for t in turns]==[2,4,4],'complete cumulative call history')
    require([sum(m['role']=='user' for m in t['history']) for t in turns]==[1,2,3],'complete cumulative user history')
    for prior,later in zip(turns,turns[1:]):require(later['history'][1:len(prior['history'])]==prior['history'][1:],'prior full history preserved except current policy')
    last=max(i for i,m in enumerate(history) if m['role']=='user');require(len(history[last:])==2 and history[-1]['role']=='assistant' and set(history[-1])=={'role','text'},'final answer without call')
    history_sha=hashlib.sha256(canonical(lesson['history']).encode()).hexdigest()
    for entry,meta in zip(entries,metadata):
     require(entry['source']=='four_call_extension' and entry['split']==split and entry['family']==row['family'],'index identity')
     require(entry['original_lesson_sha256']==did and entry['original_history_sha256']==history_sha,'index original binding')
     require(entry['length']==meta['input_tokens'] and entry['target_count']==meta['assistant_targets'],'index/independent stream row count')
     targets[split]+=entry['target_count']
   counts[split]=len(groups);require(targets[split]==receipt['counts'][split]['targets']==proof['counts'][split]['targets'],'qualified target totals')
 require(seen==retained and len(seen)==proof['four_call_qualified_histories'],'all and only custody-surviving histories qualified')
 require(all(sha(path)==expected for path,expected in pins.items()),'qualification dependencies changed')
 result=dict(state='PASS',dataset_sha256=EXPECTED_DATASET,session_calls=4,final_turn=2,final_prefixes=counts,qualified_assistant_targets=targets,actual_bound_successful_observations=binding_count,source_database_sha256=EXPECTED_DATABASE,custody_sha256=custody_pins['custody.json'],public_development_custody_sha256=custody_pins['public-development-custody.json'],exclusion_union_count=len(excluded),independent_stream_verification_sha256=sha(d/'independent-verification.json'),diagnostic_admission_sha256=sha(d/'diagnostic-admission.json'),candidate_verification_sha256=sha(source/'candidate-verification.json'),code_sha256=sha(__file__),pins=pins,scope='All indexed admitted whole 2+2+0 source histories retain four actual successful bound observations and final no-call answers; structure qualification only, no model capability or training launch claim')
 with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 print(json.dumps({k:result[k] for k in ['state','dataset_sha256','final_prefixes','actual_bound_successful_observations']}))
if __name__=='__main__':main()
