"""Development-only retrieved demonstrations; every answer remains student-generated.

Never used for confirmation without a separately frozen, guarded protocol.
"""
import argparse,collections,copy,hashlib,json,math,re
from pathlib import Path
from tokenizers import Tokenizer
import evaluate_eight_hour_v3 as evaluator
from sft_common import ROOT,render

def terms(text):
 words=[w for w in re.findall(r'[a-z]+',text.lower()) if len(w)>1]
 return collections.Counter(words+[' '.join(words[i:i+2]) for i in range(len(words)-1)])

class Retriever:
 def __init__(self,path,tok):
  self.path=Path(path);self.sha=hashlib.sha256(self.path.read_bytes()).hexdigest();self.tok=tok;self.rows=[]
  manifest=json.loads((self.path.parent/'manifest.json').read_text())
  assert manifest['files'][self.path.name]==self.sha
  for line in self.path.read_text().splitlines():
   r=json.loads(line);messages=r['messages'];start=next(i for i,m in enumerate(messages) if m['role']=='user');end=next((i for i in range(start+1,len(messages)) if messages[i]['role']=='user'),len(messages));example=messages[start:end]
   if not any(m['role']=='assistant' for m in example):continue
   if len(tok.encode(render(example,False)).ids)>128:continue
   tool=any(m['role']=='system' and 'Tools:' in m['content'] for m in messages)
   self.rows.append({'id':r['id'],'tool_mode':tool,'prompt':messages[start]['content'],'example':example,'terms':terms(messages[start]['content'])})
  df=collections.Counter(t for r in self.rows for t in r['terms']);n=len(self.rows)
  self.idf={t:math.log((1+n)/(1+count))+1 for t,count in df.items()}
  for r in self.rows:r['norm']=math.sqrt(sum((v*self.idf[k])**2 for k,v in r['terms'].items()))
 def augment(self,messages):
  query=next(m['content'] for m in messages if m['role']=='user');tool=any(m['role']=='system' and 'Tools:' in m['content'] for m in messages);q=terms(query);qnorm=math.sqrt(sum((v*self.idf.get(k,0))**2 for k,v in q.items()))
  candidates=[]
  for r in self.rows:
   if r['tool_mode']!=tool or r['prompt'].strip().casefold()==query.strip().casefold():continue
   score=sum(q[k]*v*self.idf[k]**2 for k,v in r['terms'].items() if k in q)/(max(qnorm*r['norm'],1e-12))
   if score>0:candidates.append((score,r['id'],r))
  candidates.sort(key=lambda x:(-x[0],x[1]))
  intro='The first exchange below is a separate example. Answer the actual conversation after it using that conversation\'s facts, not the example\'s facts.'
  for score,ident,row in candidates[:10]:
   actual=copy.deepcopy(messages)
   if actual and actual[0]['role']=='system':prefix=actual.pop(0);prefix['content']+='\n'+intro
   else:prefix={'role':'system','content':intro}
   augmented=[prefix]+copy.deepcopy(row['example'])+actual
   if len(self.tok.encode(render(augmented,True)).ids)<=400:
    return augmented,{'id':ident,'similarity':score,'example_messages':row['example'],'corpus_sha256':self.sha}
  return messages,{'id':None,'reason':'no_candidate_or_context_budget','corpus_sha256':self.sha}

def main(a):
 if a.split!='development':raise RuntimeError('Retrieval experiment is development-only; confirmation protocol not authorized')
 out=Path(a.output)
 if out.exists():raise RuntimeError('Preserve earlier experiments; output must be new')
 tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'));retriever=Retriever(a.corpus,tok);original=evaluator.generate
 def generate(model,tok,messages,**kwargs):
  augmented,trace=retriever.augment(messages);result=original(model,tok,augmented,**kwargs);result['retrieved_demonstration']=trace;return result
 evaluator.generate=generate
 evaluator.main(a)
 p=out/'report.json';report=json.loads(p.read_text());report['kind']='retrieved_demonstration_student_decode_NOT_unassisted_model';report['retrieval']={'corpus':str(retriever.path),'corpus_sha256':retriever.sha,'method':'TFIDF unigram/bigram cosine; same initial user query each turn; one complete example exchange; max128exampletokens and400totalprompttokens; preserves allactualhistory','candidate_count':len(retriever.rows),'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'confirmation_allowed':False,'answers':'Actual student outputs; no teacher API or answer substitution at inference'};p.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--split',choices=['development'],default='development');p.add_argument('--output',required=True);p.add_argument('--evaluation-root',required=True);p.add_argument('--corpus',required=True);p.add_argument('--prose-penalty',type=float,default=1.2);p.add_argument('--tool-penalty',type=float,default=1.2);a=p.parse_args();a.selection=None;main(a)
