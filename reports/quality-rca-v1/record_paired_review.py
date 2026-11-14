"""Record the root agent's full32-turn semantic review; assert actual calculator traces."""
import json,hashlib,datetime
from pathlib import Path
P=Path('reports/quality-rca-v1');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
reasons={
 50:{'notebook-tools-off':'Starts with correct owner, then contradicts ownership and loops; never terminates within192tokens.','literal-tools-off':'Copies the literal initially, then invents Python material and fails to terminate.','science-tools-off':'Incorrect/conflicting heat explanation and irrelevant experiment; violates one-sentence request and never terminates.','greeting-tools-off':'Initially relevant ingredients devolve into repetitive categories; no completed response.','notebook-tools-on':'Invented malformed conversion-like tool call for an ownership question.','literal-tools-on':'Calls42+42 and answers84 instead of copying the code.','science-tools-on':'Irrelevant15.5-20.5 calculator call and answer-5.','greeting-tools-on':'Introduces salmon into vegetarian advice and fails to terminate.'},
 194:{'notebook-tools-off':'Correct opening followed by invented people/notebooks, contradictory ownership and repetition; no completed response.','literal-tools-off':'Drops Q from literal and drifts into unrelated timed workshop agenda; no completed response.','science-tools-off':'Some heat-related opening then unrelated/incorrect instructions and scissors; violates one-sentence request and no termination.','greeting-tools-off':'Unrequested repetitive timed agenda, dinner topic drift and no completed response.','notebook-tools-on':'Invents unavailable blue notebook tool and web-like converter arguments.','literal-tools-on':'Invents unavailable code tool and addition instead of copying requested literal.','science-tools-on':'Irrelevant45-50 calculator call and answer-5.','greeting-tools-on':'Timed agenda and verbosity do not complete within budget; no completed response.'}}
reviews=[]
for step in [50,194]:
 p=P/f'step{step}-paired.json';raw=json.loads(p.read_text());assert raw['status']=='development_checks_complete' and len(raw['records'])==16;records=[]
 for r in raw['records']:
  name=r['session'];passed=name.startswith('calculator-');result=r['result']
  if passed:
   expected=[('add',1,39,40),('subtract',72,19,53),('multiply',7,8,56),('subtract',73,19,54)][int(name[-1])];op,a,b,value=expected
   trace=result['broker_trace'];assert len(trace)==1 and trace[0]['name']=='calculate' and trace[0]['ok'];args=trace[0]['arguments'];assert args['op']==op
   assert (args['a'],args['b'])==(a,b) or (op in ['add','multiply'] and (args['a'],args['b'])==(b,a))
   assert result['status']=='complete' and trace[0]['data']['result']==value and result['assistant_text']==str(value)
   reason='Actual dispatched calculate call has correct operation/operands/result and final answer; commutative operand order accepted.'
  elif r['turn']==1:
   reason='Blocked by prior failed turn; retained in denominator.' if not result['events'] else 'Malformed nested calculator call instead of applying requested literal correction.'
  else:reason=reasons[step][name]
  records.append({'session':name,'turn':r['turn'],'strict_pass':passed,'tool_workflow_pass':passed if passed else None,'reason':reason})
 review={'checkpoint_manifest_sha256':raw['checkpoint_manifest_sha256'],'raw_sha256':sha(p),'suite_sha256':raw['suite_sha256'],'reviewer':'root Codex agent; all decoded actions and calculator broker traces inspected','records':records,'strict_turns':{'passed':4,'total':16},'natural_state_turns':{'passed':0,'total':12},'calculator_turns':{'passed':4,'total':4},'complete_sessions':{'passed':4,'total':12},'quality_accepted':False}
 reviews.append(review)
summary={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'purpose':'mechanistic diagnostic, not release acceptance','all32turns_reviewed':True,'comparison':'Both best-dev50 and final194 fail all natural/state turns and pass four narrow calculator probes; rollback alone does not recover usable conversation.','runtime':'Both MPS/greedy192tokens per action; serving/tokenizer/model-loading unchanged. Evaluation runner changed only suite preflight/release-mode support between runs; both use development mode.','limitations':['Small exposed paired diagnostic, not representative accuracy estimate.','No4K evaluation; follow-ups blocked after errors remain failures.','Not an ablation of training data, LR, order, optimizer or base capacity.'],'reviews':reviews}
(P/'paired-review.json').write_text(json.dumps(summary,indent=2)+'\n')
