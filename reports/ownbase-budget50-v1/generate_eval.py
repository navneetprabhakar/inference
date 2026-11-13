"""Generate a new2K assessment candidate pool; no automatic freezing/admission."""
import json,subprocess,fcntl,datetime
from pathlib import Path
R=Path('runs/ownbase-budget50-v1/eval-candidates');R.mkdir(exist_ok=True)
lock=Path('runs/concise-teacher-generation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
S={'type':'string'}
def obj(p):return {'type':'object','properties':p,'required':list(p),'additionalProperties':False}
calc=obj({'name':{'type':'string','enum':['calculate']},'arguments':obj({'op':{'type':'string','enum':['add','subtract','multiply','divide']},'a':{'type':'number'},'b':{'type':'number'}})})
conv=obj({'name':{'type':'string','enum':['convert']},'arguments':obj({'value':{'type':'number'},'from':S,'to':S})})
turn=obj({'user':S,'rubric':S,'permit_calls':{'type':'boolean'},'expected_calls':{'type':'array','items':{'anyOf':[calc,conv]}},'acceptable_answers':{'type':'array','items':S}})
schema=obj({'sessions':{'type':'array','items':obj({'id':S,'family':S,'turns':{'type':'array','items':turn}})}})
seen=[]
for batch,category in enumerate(['natural','natural','tool','tool','code_state','code_state'],1):
 d=R/f'batch-{batch:02d}';d.mkdir(exist_ok=False);(d/'schema.json').write_text(json.dumps(schema))
 prompt=f'''Do not use any tools, files, network or agents. Return10 distinct new evaluation conversations for a537M2K-context assistant, category:{category}, IDs b50-{batch:02d}-01 through10. Each has3 substantive USER turns with explicit fixed evidence and a later correction, interruption or ambiguity. No reference to prior unknown model answers: supplied user facts must make the scripted followup coherent even if the model errs. Cases are unseen assessment, never training. Do not supply assistant dialogue. Rubric explicitly states expected correct facts/actions per turn; acceptable_answers contains alternative exact complete responses only when user requests short exact output, otherwise []. Natural cases need real practical explanations/revisions, no exact-only majority. Tool cases use only calculate(add/subtract/multiply/divide) and convert(length mm/cm/m/km, mass g/kg, time s/min/h); maximum2calls/turn,4/session. Include late operand retrieval and grounded result followups. permit_calls=false means no tool calls; user requests must be consistent with policy or deliberately test appropriate refusal/clarification described by rubric. No unsupported tools, external actions, real legal/medical/financial guidance, fabricated facts or opinions as facts. Code_state cases use small supplied Python snippets, explain or fix concrete bugs, state changes, aliasing, truthiness, iteration, scope, string operations; avoid broad algorithms already in corpus: interval merge/subtract, tree outline, ledger reconciliation, CSV parser, topk, LRU, event reducer. Keep each3-turn session comfortably within1800tokens including short assistant answers. No irrelevant padding, role markers or coaching expected answers in followup questions. Avoid same scenario/name/arithmetic operands as these already reserved families:{json.dumps(seen)}. All numeric results in rubrics must be correct. Use named fictional settings with enough evidence. Do not claim benchmark independence beyond these deliberately new cases.'''
 (d/'prompt.txt').write_text(prompt)
 argv=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(d.resolve()),'-m','gpt-6.1-terra','-c','model_reasoning_effort="high"','--output-schema',str((d/'schema.json').resolve()),'--output-last-message',str((d/'output.json').resolve()),'--json','-']
 with (d/'events.jsonl').open('w') as out,(d/'stderr.log').open('w') as err:r=subprocess.run(argv,input=prompt,text=True,stdout=out,stderr=err,timeout=600)
 assert r.returncode==0
 result=json.loads((d/'output.json').read_text());assert len(result['sessions'])==10;seen.extend(s['family'] for s in result['sessions'])
 print(json.dumps({'batch':batch,'category':category,'generated':10,'reviewed':0}),flush=True)
