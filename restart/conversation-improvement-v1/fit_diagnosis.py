import adapter9 as a
from journal_meter import Meter
from sentencepiece import SentencePieceProcessor
import torch,json
s=a.s;ROOT=s.ROOT
meter=Meter('cycle10-fit-diagnosis')
try:
 m=a.Adapter();m.restore(torch.load(s.PRIVATE/'cycle10-1600.pt',weights_only=False));sp=SentencePieceProcessor(model_file=str(s.serializer.TOK));ground=s.read(s.PRIVATE/'grounding.json');sample=[]
 for family in sorted({x['family'] for x in ground}):sample.extend([x for x in ground if x['family']==family][:8])
 s.save(s.PRIVATE/'cycle10-seen-grounding-probe.json',sample)
 result=s.generate(m.e,m.common,sample,sp,48,meter,'cycle10-1600-seen-grounding')
 result['scope']='First eight existing training records per family; fitting diagnostic only, not selection or held-out evidence.'
 result['family_training_nll']={}
 for family in sorted({x['family'] for x in sample}):
  rows=[x for x in sample if x['family']==family];x,y,mask,_=s.serializer.collate(rows);meter.reserve(x.size,'seen-grounding-masked-loss');v=m.loss(m.a,m.mx.array(x),m.mx.array(y),m.mx.array(mask));m.mx.eval(v);result['family_training_nll'][family]=float(v)
 s.save(ROOT/'cycle10-fit-diagnosis.json',result);print(json.dumps(result),flush=True)
finally:meter.close()
