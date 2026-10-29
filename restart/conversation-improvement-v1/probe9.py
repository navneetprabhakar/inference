import adapter9 as a
from journal_meter import Meter
from sentencepiece import SentencePieceProcessor
import torch,json
s=a.s
meter=Meter('cycle9-diagnosis')
try:
 sp=SentencePieceProcessor(model_file=str(s.serializer.TOK));m=a.Adapter();out=[]
 for step in [200,400]:
  m.restore(torch.load(s.PRIVATE/f'cycle9-{step}.pt',weights_only=False));row=dict(step=step)
  row['development']=s.generate(m.e,m.common,a.c.repair.run.bank('development'),sp,48,meter,f'cycle9-{step}-development')
  row['seen']=s.generate(m.e,m.common,s.read(s.PRIVATE/'probe-seen.json'),sp,48,meter,f'cycle9-{step}-seen');out.append(row);s.save(s.ROOT/'cycle9-diagnosis.json',out);print(json.dumps(row),flush=True)
finally:meter.close()
