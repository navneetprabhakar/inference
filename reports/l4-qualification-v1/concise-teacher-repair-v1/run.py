import json,subprocess,time,hashlib,datetime,re
from pathlib import Path
ROOT=Path('/opt/ownbase-nano');out=ROOT/'results/concise-teacher-repair-v1';out.mkdir(parents=True,exist_ok=False)
prefix='gs://forge-ownbase-a100-20261110/ownbase-v2/concise-teacher-repair-v1'
parent=ROOT/'results/literal-state-repair-v1/sft/step-00000605';base=ROOT/'results/stage-004/step-00011445';toksha='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'
def run(args,seconds):subprocess.run(['/usr/bin/python3','-u','-m',*args],check=True,timeout=seconds)
def quality(checkpoint,suite,name,budget=128):
 sha=hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest()
 run(['cloud_training.nano_quality','--repo',str(ROOT/'nanochat-source'),'--checkpoint',str(checkpoint),'--checkpoint-manifest-sha256',sha,'--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha256',toksha,'--suite',str(suite),'--reply-budget',str(budget),'--seconds','540','--output',str(out/name)],600)
 return json.loads((out/name).read_text())
def contracts(report):
 suite=json.loads((ROOT/'instruction-heldout-suite.json').read_text());specs={(session['id'],i):t for session in suite['sessions'] for i,t in enumerate(session['turns'])};records=[]
 for r in report['records']:
  c=specs[(r['session'],r['turn'])]['checks'];t=r['result'].get('assistant_text') or ''
  ok=r['result']['status']=='complete' and r['assessment']['calls_correct'] and len(t.split())<=45
  ok=ok and all(v.casefold() in t.casefold() for v in c.get('contains',[])) and all(v.casefold() not in t.casefold() for v in c.get('forbid',[]))
  if 'exact' in c:ok=ok and t.strip()==c['exact']
  if c.get('question'):ok=ok and '?' in t
  if c.get('sentences'):ok=ok and len(re.findall(r'[.!?](?:\s|$)',t))==c['sentences']
  records.append({'session':r['session'],'turn':r['turn'],'passed':bool(ok)})
 return {'passed':sum(r['passed'] for r in records),'total':len(records),'records':records,'limitation':'Mechanical content/format contracts, not full semantic acceptance.'}
def status(stage):
 print('PHASE '+stage,flush=True)
 (out/'status.json').write_text(json.dumps({'stage':stage,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
 subprocess.run(['gcloud','storage','cp',str(out/'status.json'),prefix+'/status.json','--quiet'],check=True,timeout=60)
try:
 status('baseline_evaluation')
 before=quality(parent,ROOT/'instruction-heldout-suite.json','before.json')
 status('targeted_training')
 deadline=datetime.datetime.fromtimestamp(min(time.time()+1800,1794476714-1200),datetime.timezone.utc).isoformat()
 run(['cloud_training.nano_sft','--manifest',str(ROOT/'sft/concise-teacher-repair-admitted-v1/manifest.json'),'--base',str(parent),'--base-manifest-sha','05ab60c277c0bcfb4288215b8909aa693a451ab1e059fa5aacd7946f2a1854a8','--ancestor',str(ROOT/'results/conversation-repair-v1/sft/step-00000090'),'--ancestor',str(ROOT/'results/instruction-repair-v3/sft/step-00000176'),'--ancestor',str(base),'--ancestor',str(ROOT/'results/instruction-repair-v2/sft/step-00000169'),'--ancestor',str(ROOT/'results/instruction-repair-v1/sft/step-00000076'),'--ancestor',str(ROOT/'results/broad-conversation-pilot-v1/sft/step-00001000'),'--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha',toksha,'--repo',str(ROOT/'nanochat-source'),'--backup-prefix',prefix+'/checkpoints','--stage','targeted','--lr-multiplier','0.25','--epochs','4','--batch-tokens','8192','--microbatch','4','--seed','141','--eval-rows','64','--eval-every-updates','1000','--checkpoint-seconds','1800','--checkpoint-reserve-seconds','300','--deterministic','--deterministic-attention','--kernel-path',str(ROOT/'kernel'),'--kernel-sha','85b2e0c2ef47d48eb6a2131ddf6d9066c4dc44f87a231114cc4222b3a2575953','--deadline-utc',deadline,'--output',str(out/'sft')],1860)
 result=json.loads((out/'sft/result.json').read_text())
 if result['status']!='complete':raise RuntimeError('Incomplete finite SFT; do not claim completed pilot')
 status('post_training_evaluation')
 checkpoint=Path(result['last_checkpoint']['path']);after=quality(checkpoint,ROOT/'instruction-heldout-suite.json','after.json');original=quality(checkpoint,ROOT/'cloud_training/evaluation/conversation-tools-dev.json','original-suite.json')
 constraints=quality(checkpoint,ROOT/'constraint-regression-suite.json','constraint-regression.json')
 teacher=quality(checkpoint,ROOT/'teacher-regression-suite.json','teacher-regression.json',256)
 general=quality(checkpoint,ROOT/'general-conversation-challenge.json','general-challenge.json')
 conversation=quality(checkpoint,ROOT/'conversation-regression-suite.json','conversation-regression.json')
 regression=quality(checkpoint,ROOT/'instruction-v3-regression-suite.json','regression-v3.json')
 regression2=quality(checkpoint,ROOT/'instruction-v2-regression-suite.json','regression-v2.json')
 required_original=[r for r in original['records'] if r['session'] in ('calculate-grounding','convert-grounding')]
 tool_records=[r for r in regression['records'] if r['session'].rsplit('-',1)[0] in ('calculate','convert','tool_correction')]
 tool_records += [r for r in regression2['records'] if r['session'].rsplit('-',1)[0] in ('calculate','convert','tool_correction')]
 preserved=(len(required_original)==2 and len(tool_records)==16 and all(r['assessment']['automated_pass'] for r in required_original+tool_records))
 (out/'concise-contracts.json').write_text(json.dumps({'before':contracts(before),'after':contracts(after)},indent=2)+'\n')
 summary={'tool_gains_preserved':preserved,'required_tool_cases_passed':sum(r['assessment']['automated_pass'] for r in required_original+tool_records),'required_tool_cases_total':18,'manual_conversation_review_required':True,'regression_v2_passed':regression2['automated_passed'],'regression_v2_total':regression2['automated_total'],'regression_v3_passed':regression['automated_passed'],'regression_v3_total':regression['automated_total'],'status':'complete','before_passed':before['automated_passed'],'after_passed':after['automated_passed'],'total':after['automated_total'],'original_suite_passed':original['automated_passed'],'usable_model_claim':False,'next':'Review exact action and transcript regressions before broader tuning'}
except Exception as e:summary={'status':'blocked','error':str(e),'usable_model_claim':False}
print(json.dumps(summary),flush=True)
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
subprocess.run(['gcloud','storage','rsync','--recursive',str(out),prefix+'/results','--exclude=.*payload[.]pt$','--quiet'],timeout=180,check=True)
