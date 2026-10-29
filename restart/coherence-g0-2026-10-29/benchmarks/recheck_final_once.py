import json,hashlib,collections
from pathlib import Path
from sentencepiece import SentencePieceProcessor
P=Path(__file__).resolve().parent;R=P.parents[2];D=R/'restart/coherence-g0-2026-10-29/final-custody/private'
p=D/'final.jsonl';oldp=D/'pre-repair/final.jsonl';a=[json.loads(x) for x in p.read_text().splitlines()];old=[json.loads(x) for x in oldp.read_text().splitlines()]
assert hashlib.sha256(p.read_bytes()).hexdigest()=='3fef3cddd3863c46f3e62d563e7620c0c22c7359f01ccb0ec88bfd554c8238ee'
assert hashlib.sha256(oldp.read_bytes()).hexdigest()=='a5c87d489a8526b1001c5d4fa81502ea0de8166c8f9175fc76600cc29476b498'
sp=SentencePieceProcessor(model_file=str(R/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
changed=[];maxcontext=0;maxreply=0
for x,y in zip(old,a):
 assert x['id']==y['id'] and len(x['messages'])==len(y['messages'])
 assert ' record: ' not in y['messages'][0]['content']
 for j,(u,v) in enumerate(zip(x['messages'],y['messages'])):
  before=u['content'].split(' record: ',1)[-1] if j==0 else u['content']
  if before!=v['content']:changed.append((y['id'],j//2+1,v['role']))
 for j,(u,v) in enumerate(zip(y['messages'][::2],y['messages'][1::2])):
  assert y['contracts'][j]['reference']==v['content']
  if 'no second sentence' in u['content']:assert '. ' not in v['content'] and v['content'].startswith('Note: ')
  maxreply=max(maxreply,len(sp.encode(v['content']))+1)
 worst=1+sum(len(sp.encode('User: '+m['content']+'\nAssistant:')) for m in y['messages'][::2])+32*y['turns'];assert worst<=256;maxcontext=max(maxcontext,worst)
assert len(changed)==16
assert len(a)==240 and sum(x['turns'] for x in a)==710 and maxreply<=32
for f in ['grounding','comprehension','clarification','correction','instructions','explanation']:
 group=[x for x in a if x['family']==f];assert len(group)==40 and sum(x['interruption_continuity'] for x in group)==10 and sum(x['answerability_contrast'] for x in group)==40
r={'status':'FIXED_RECHECK_PASS_NOT_ADMITTED_OR_SEALED','reviewer':'g0_benchmarks nonauthor separate model agent; not human or separate provider','initial_payload_sha256':hashlib.sha256(oldp.read_bytes()).hexdigest(),'rechecked_payload_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'initial_semantic_review':{'conversations':240,'turns':710},'fixed_recheck':{'all_240_prompt_prefix_removals_verified':True,'other_changed_messages_inspected':16,'contract_reference_consistency':'all710','F01':'resolved9reference sentence violations','F02':'resolved ambiguous question','F03':'resolved function-identifying prefixes','F04':'resolved conditional strength in6family adaptations'},'counts':{'conversations':240,'turns':710,'per_function':40,'per_structure':60,'interruption_per_function':10,'answerability_per_function':40},'independent_native_context_check':{'max_worst_history':maxcontext,'max_reply_including_eos':maxreply},'admitted':False,'sealed':False,'g5_eligible':False,'remaining_limitations':['Campaign stopped at STOP_DATA_ADMISSION','Cross-corpus exact/scenario-overlap clearance not complete','40 scenario clusters recur across6functions','Repeated interruption/missingness wording limits breadth','Procedural same-user custody, not cryptographic isolation'],'repair_batches_used':1,'further_repair_allowed':False}
(P/'final_recheck_metadata.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
