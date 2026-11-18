"""Reviewing-agent-transcribed arithmetic; no generated expressions executed."""
from fractions import Fraction
CASES={
 'decisions-09':{4:[('sub',['95','90'],'5')]},
 'decisions-13':{2:[('add',['5','15','20','5'],'45')]},
 'decisions-14':{4:[('add',['10','15','5'],'30')]},
 'decisions-19':{1:[('add',['35','35','30','20'],'120')],3:[('sub',['120','30','25','25'],'40')]},
 'decisions-21':{2:[('add',['10','15','40','15','10'],'90')]},
 'decisions-22':{2:[('add',['5','5'],'10')]},
 'orch_008':{1:[('sub',['4','2'],'2')],2:[('sub',['5','2'],'3')],3:[('add',['3','1'],'4')],4:[('sub',['5','2'],'3')]},
 'orch_018':{2:[('sub',['2','1'],'1')],3:[('add',['1','1'],'2')],6:[('add',['1','2'],'3')]},
 'orch_019':{1:[('sub',['18','12'],'6')]},
 'orch_024':{1:[('sub',['2','1'],'1')],2:[('sub',['2','1'],'1')],3:[('add',['1','1'],'2')]},
}
def replay(op,operands,expected):
 x=[Fraction(v) for v in operands]
 if op=='add':actual=sum(x,Fraction(0))
 elif op=='sub':actual=x[0]-sum(x[1:],Fraction(0))
 else:raise ValueError(op)
 assert actual==Fraction(expected)
 return {'operation':op,'operands':operands,'expected':expected,'actual_exact_fraction':str(actual)}
def entry(row,digest):
 return {'group':row['group'],'messages_sha256':digest(row['messages']),'turns':[{'turn':i+1,'quoted_assistant_reply':m['content'],'checks':[replay(*x) for x in CASES.get(row['group'],{}).get(i+1,[])],'review':'Read in context; numeric facts copied from user or proposals except explicitly replayed derived values. Weekday arithmetic uses Monday=1; schedule remains proposed.'} for i,m in enumerate(row['messages'][1::2])]}
