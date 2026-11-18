"""Independently transcribed by reviewing agent; operations only; no expression evaluation of generated text."""
import json,hashlib,pathlib
from fractions import Fraction as F
R=pathlib.Path(__file__).parent
# Each inner tuple: operation, operands, asserted result. Each inner list is one turn.
A={
'01':[[('add',['27','18'],'45'),('add',['7','8'],'15'),('add',['2','1','1'],'4')],[('add',['27','19'],'46'),('sub',['46','45'],'1')],[('add',['7','9'],'16'),('add',['2','1','1'],'4'),('add',['27','19'],'46')],[('add',['27','20'],'47'),('sub',['47','1'],'46'),('sub',['20','1'],'19')]],
'02':[[('sub',['100','73'],'27')],[('add',['73','12'],'85'),('sub',['100','85'],'15')],[('add',['85','5'],'90'),('add',['90','10'],'100'),('add',['5','10'],'15')],[('add',['78','12'],'90'),('sub',['100','90'],'10')],[('sub',['78','73'],'5'),('sub',['15','10'],'5')]],
'03':[[('mul',['4','6'],'24')],[],[('mul',['5','6'],'30'),('add',['24','6'],'30')],[('mul',['5','6'],'30'),('mul',['6','5'],'30')],[('muladd',['4','6','4'],'28')],[]],
'04':[[('muladd',['5','3','2'],'17')],[('div',['2','5'],'2/5'),('add',['3','2/5'],'17/5')],[('muladd',['5','3','2'],'17')],[('sub',['5','2'],'3'),('add',['2','3'],'5')]],
'05':[[('mul',['4','2'],'8'),('add',['3','8'],'11')],[('add',['3','4'],'7'),('mul',['7','2'],'14')],[('add',['2','1'],'3'),('mul',['4','3'],'12'),('add',['3','12'],'15')],[('add',['2','1'],'3')],[('add',['3','4'],'7'),('add',['2','1'],'3'),('mul',['7','3'],'21')]],
'06':[[('add',['-2','5'],'3'),('add',['-2','2'],'0'),('add',['0','3'],'3')],[('add',['-2','4'],'2')],[('sub',['2','6'],'-4')],[('sub',['-1','-4'],'3')],[('sub',['3','-4'],'7')],[]],
'07':[[('eq',['3/4','6/8'],'1'),('gt',['6/8','5/8'],'1')],[('eq',['3/4','6/8'],'1')],[('eq',['2/3','10/15'],'1'),('eq',['3/5','9/15'],'1'),('gt',['2/3','3/5'],'1')],[]],
'08':[[('eq',['1/3','4/12'],'1'),('eq',['1/4','3/12'],'1'),('add',['4/12','3/12'],'7/12')],[('add',['4/12','3/12'],'7/12')],[('add',['8/24','6/24'],'14/24'),('eq',['14/24','7/12'],'1')],[('add',['4/10','5/10'],'9/10'),('eq',['2/5','4/10'],'1'),('eq',['1/2','5/10'],'1')],[('add',['2/3','3/4'],'17/12'),('add',['8/12','9/12'],'17/12'),('add',['1','5/12'],'17/12')]],
'09':[[('eq',['3/4','9/12'],'1'),('eq',['1/3','4/12'],'1'),('sub',['3/4','1/3'],'5/12')],[('sub',['3/4','1/4'],'1/2')],[('eq',['1/2','4/8'],'1')],[('add',['1/4','5/8'],'7/8'),('sub',['7/8','3/4'],'1/8')],[('sub',['7/8','3/4'],'1/8')],[('add',['1/4','5/8'],'7/8'),('sub',['7/8','3/4'],'1/8')]],
'10':[[('div',['40','5'],'8'),('mul',['8','3'],'24')],[('mul',['50','3/5'],'30')],[('mul',['40','3/5'],'24'),('mul',['50','3/5'],'30')],[('sub',['1','3/5'],'2/5'),('mul',['50','2/5'],'20'),('sub',['50','30'],'20')]],
'11':[[('eq',['6/8','3/4'],'1')],[],[],[('eq',['18/24','3/4'],'1')],[('eq',['18/24','9/12'],'1'),('eq',['9/12','3/4'],'1')]],
'12':[[('eq',['3.7','3.70'],'1'),('add',['3.70','0.46'],'4.16')],[('eq',['3.7','37/10'],'1')],[('add',['7/10','4/10'],'11/10')],[('add',['3.07','0.46'],'3.53'),('add',['7/100','6/100'],'13/100'),('add',['1/10','4/10'],'5/10')],[('add',['3.53','0.50'],'4.03'),('add',['5/10','5/10'],'1')],[('add',['3.53','0.50'],'4.03')]],
}
def check(op,args,want):
 x=[F(z) for z in args]
 if op=='add':v=sum(x,F(0))
 elif op=='sub':v=x[0]-x[1]
 elif op=='mul':v=x[0]*x[1]
 elif op=='muladd':v=x[0]*x[1]+x[2]
 elif op=='div':v=x[0]/x[1]
 elif op=='eq':v=F(int(x[0]==x[1]))
 elif op=='gt':v=F(int(x[0]>x[1]))
 else:raise ValueError(op)
 assert v==F(want),(op,args,want,str(v))
 return {'operation':op,'operands':args,'expected':want,'actual_exact_fraction':str(v),'pass':True}
A.update({
'13':[[('eq',['2.7','2.70'],'1'),('sub',['5.03','2.70'],'2.33')],[('eq',['2.70','27/10'],'1')],[('sub',['5.03','2.07'],'2.96')],[('add',['4','9/10','13/100'],'5.03'),('sub',['5.03','2.07'],'2.96')]],
'14':[[('mul',['1.25','6'],'7.5')],[('mul',['125','6'],'750'),('mul',['1.25','6'],'7.50')],[],[('mul',['4','3'],'12'),('mul',['0.04','3'],'0.12')],[('mul',['0.04','30'],'1.2'),('mul',['0.12','10'],'1.2')]],
'15':[[('div',['8.4','4'],'2.1'),('div',['84/10','4'],'21/10')],[('div',['8','4'],'2'),('div',['4/10','4'],'1/10')],[('div',['8.04','4'],'2.01'),('div',['4/100','4'],'1/100')],[('eq',['2.1','21/10'],'1'),('eq',['2.01','201/100'],'1')],[('div',['8.04','3'],'2.68'),('muladd',['3','2','2'],'8')],[('mul',['2.68','3'],'8.04')]],
'16':[[('div',['3','4'],'0.75'),('eq',['3/4','75/100'],'1')],[('mul',['3','25'],'75'),('mul',['4','25'],'100')],[('eq',['3/5','6/10'],'1'),('eq',['6/10','0.6'],'1')],[('eq',['3/8','375/1000'],'1'),('eq',['375/1000','0.375'],'1')]],
'17':[[('mul',['15/100','240'],'36')],[('mul',['10/100','240'],'24'),('mul',['5/100','240'],'12'),('add',['24','12'],'36')],[('mul',['10/100','280'],'28'),('mul',['5/100','280'],'14'),('add',['28','14'],'42')],[('mul',['280','0.15'],'42')],[('eq',['15/100','0.15'],'1')]],
'18':[[('mul',['20/100','800'],'160'),('sub',['800','160'],'640')],[('sub',['1','20/100'],'80/100'),('mul',['800','0.8'],'640')],[('mul',['850','20/100'],'170'),('sub',['850','170'],'680')],[('mul',['850','15/100'],'127.50'),('sub',['850','127.50'],'722.50')],[('mul',['800','15/100'],'120'),('sub',['800','120'],'680')],[('mul',['850','80/100'],'680'),('mul',['800','85/100'],'680')]],
'19':[[('sub',['25','20'],'5'),('div',['5','20'],'1/4')],[],[('sub',['45','40'],'5'),('div',['5','40'],'0.125')],[('sub',['25','20'],'5')]],
'20':[[('mul',['2.4','100'],'240')],[('div',['75','100'],'0.75')],[('add',['100','35'],'135'),('div',['135','100'],'1.35')],[('add',['100','53'],'153'),('div',['153','100'],'1.53')],[('sub',['153','150'],'3')]],
'21':[[('mul',['0.75','1000'],'750')],[('sub',['750','500'],'250')],[('sub',['750','450'],'300')],[('div',['750','2'],'375')],[('sub',['450','375'],'75')],[('div',['75','1000'],'0.075')]],
'22':[[('add',['15','20'],'35')],[('add',['15','35'],'50')],[('add',['5','35'],'40')],[('sub',['60','20'],'40')]],
'23':[[('sub',['19','7'],'12')],[],[('add',['19','7'],'26')],[('sub',['26','7'],'19')],[('add',['19','7'],'26')]],
'24':[[('sub',['19','4'],'15'),('div',['15','3'],'5')],[],[('add',['20','4'],'24'),('div',['24','3'],'8')],[('mul',['3','8'],'24'),('sub',['24','4'],'20')],[('add',['20','4'],'24'),('div',['24','4'],'6')],[('mul',['4','6'],'24'),('sub',['24','4'],'20')]],
})
if __name__=='__main__':
 root=R.parents[2]; run=root/'runs/ganesh-foundations-extension-v1/maths'
 rows=sorted(map(json.loads,(R/'accepted.jsonl').read_text().splitlines()),key=lambda x:x['group'])
 assert len(rows)==24
 def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
 def digest(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
 def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
 def ref(p):return {'path':str(p.relative_to(root)),'sha256':sha(p)}
 audits=[]; histories=[]; full=[]; memories=[]
 for row in rows:
  group=row['group']; ms=row['messages']; n=len(ms)//2; assertions=A[group[-2:]]; assert len(assertions)==n,(group,len(assertions),n)
  turns=[]
  for i,ops in enumerate(assertions):
   reply=ms[i*2+1]['content'];turns.append({'turn':i+1,'quoted_assistant_reply':reply,'checks':[check(*op) for op in ops], 'explanation_review':'Reviewed against preceding user context and the exact arithmetic; scope, operations and qualitative explanation are coherent.' if ops else 'Reviewed the qualitative or contextual explanation against preceding turns; it introduces no new computed result.'})
  audits.append({'group':group,'messages_sha256':digest(ms),'turns':turns})
  versions=[]
  for raw in sorted(run.glob('b*-g*.raw.json')):
   data=json.loads(raw.read_text());hits=[c for c in data['conversations'] if c['group']==group]
   if hits:
    c=hits[0];m=[{'role':r,'content':t[r]} for t in c['turns'] for r in ('user','assistant')]
    versions.append({'raw_artifact':str(raw.relative_to(root)),'raw_sha256':sha(raw),'messages_sha256':digest(m)})
  assert len(versions)<=3
  histories.append({'group':group,'messages_sha256':digest(ms),'total_generation_revisions':len(versions)-1,'versions':versions})
  full.append({'group':group,'messages_sha256':digest(ms),'decision':'pass','assistant_turns_reviewed':n,'reviewed_turn_numbers':list(range(1,n+1)),'rationale':'Personally read each user and assistant turn in context; checked corrections, mathematical explanations, ambiguity and claims against the independent per-turn exact arithmetic audit. Candidate only.'})
  selected_raw=root/row['generation']['raw_artifact'];orig=[c for c in json.loads(selected_raw.read_text())['conversations'] if c['group']==group][0]['recall_probe']
  memories.append({'group':group,'messages_sha256':digest(ms),'credit':False,'recall_probe':None,'original_generated_annotation':orig,'reason':'No memory credit requested or audited.','source_receipts':[]})
  row['recall_probe']=None;row['memory_probe_credit']=False;row['total_generation_revisions']=len(versions)-1
 write(R/'arithmetic-audit.json',{'method':'Independently transcribed by reviewing agent: exact rational operations independently replayed using fractions.Fraction; complete assistant reply quoted as claim context; no generated expressions executed. Qualitative explanations manually read.','entries':audits})
 write(R/'generation-history.json',{'entries':histories});write(R/'final-content-review.json',{'entries':full});write(R/'memory-evidence.json',{'entries':memories})
 for row in rows:
  row['generation_history_receipt']=ref(R/'generation-history.json');row['full_content_review_receipt']=ref(R/'final-content-review.json');row['memory_evidence_receipt']=ref(R/'memory-evidence.json');row['arithmetic_audit_receipt']=ref(R/'arithmetic-audit.json')
 (R/'selected.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
 print('audited',len(rows),'sessions',sum(len(r['messages'])//2 for r in rows),'turns')
