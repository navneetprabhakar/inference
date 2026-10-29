"""Matched EOS-loss study; inherited code/data are immutable."""
import sys,time,json,gc
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'resume-repair-v1'))
import validate as repair
s=repair.s;s.ROOT=ROOT;s.PRIVATE=ROOT/'private'
from sentencepiece import SentencePieceProcessor
from mlx.utils import tree_unflatten

class Meter(s.Meter):
    def check(self):
        super().check()
        assert self.data['model_seconds']+time.time()-self.start<600,'ABLATION_TIME_CAP'
    def reserve(self,n,kind,updates=0,sft=0,narrative=0):
        for key,value,limit in [('positions',n,5000000),('updates',updates,400),('sft_targets',sft,30000),('narrative_targets',narrative,1000000)]:
            assert self.data[key]+value<=limit,'ABLATION_CAP_'+key
        super().reserve(n,kind,updates,sft,narrative)

def loss_functions(e,factor):
    mx=e.mx
    def loss(params,x,y,mask):
        e.model.update(tree_unflatten([(k,v.astype(mx.bfloat16)) for k,v in params.items()]))
        logits=e.model(x).astype(mx.float32)
        weights=mask*mx.where(y==2,factor,1.)
        return mx.sum(e.nn.losses.cross_entropy(logits,y,reduction='none')*weights)/mx.sum(mask)
    return mx.compile(loss),mx.compile(mx.value_and_grad(loss))

def inspect(e,c,rows,sp,meter,label):
    model=c.bind(e);out=[]
    for row in rows:
        ids,mask,spans=s.serializer.serialize(sp,row['messages']);span=spans[-1]
        meter.reserve(len(ids)-1,'teacher-forced-'+label)
        logits=model(e.mx.array(ids[:-1][None,:],e.mx.int32))[0].astype(e.mx.float32)
        selected=logits[e.mx.arange(span['start']-1,span['end']-1)]
        e.mx.eval(selected);e.memory();z=np.array(selected);y=ids[span['start']:span['end']]
        pred=z.argmax(-1);gold=z[np.arange(len(y)),y];margin=z[:,sp.eos_id()]-gold
        out.append(dict(id=row['id'],family=row['family'],targets=y.tolist(),predictions=pred.tolist(),eos_minus_gold=margin.tolist(),sequence_token_count={str(int(t)):int(sum(np.array(row['ids'])==t)) for t in y}))
    s.save(s.PRIVATE/(label+'-positions.json'),out)
    summary={}
    for family in sorted({r['family'] for r in out}):
        rs=[r for r in out if r['family']==family]
        margins=[m for r in rs for m in r['eos_minus_gold'][:-1]]
        summary[family]=dict(content_positions=len(margins),content_correct=sum(sum(a==b for a,b in zip(r['targets'][:-1],r['predictions'][:-1])) for r in rs),premature_eos=sum(sum(p==sp.eos_id() for p in r['predictions'][:-1]) for r in rs),positive_eos_margin=sum(m>0 for m in margins),max_eos_minus_gold=max(margins),mean_eos_minus_gold=float(np.mean(margins)))
    s.save(ROOT/(label+'-diagnosis.json'),summary)
    return summary

def numerical(e,rows,meter):
    import torch
    sys.path.insert(0,str(s.PROJECT/'restart/mac15m-feasibility-v1/upstream'))
    from model import ModelArgs,Transformer
    torch.set_num_threads(2)
    model=Transformer(ModelArgs(**e.origin['model_args']));model.load_state_dict(e.origin['model'],strict=True);model.eval()
    x,y,m,_=s.serializer.collate(rows[:4]+rows[16:20]);mx=e.mx
    meter.reserve(x.size*4,'weighted-independent-numerical')
    fn,gfn=loss_functions(e,.25);value,g=gfn(e.params,mx.array(x),mx.array(y),mx.array(m));mx.eval(value,g)
    logits=model(torch.tensor(x,dtype=torch.long));weights=torch.tensor(m)*torch.where(torch.tensor(y)==2,.25,1.)
    loss=(torch.nn.functional.cross_entropy(logits.reshape(-1,32000),torch.tensor(y,dtype=torch.long).reshape(-1),reduction='none').reshape(y.shape)*weights).sum()/torch.tensor(m).sum();loss.backward()
    a={e.mapping()[k]:p.grad.detach().numpy() for k,p in model.named_parameters()};b={k:np.array(v) for k,v in g.items()}
    aa=sum(float(np.sum(v.astype(np.float64)**2)) for v in a.values());bb=sum(float(np.sum(v.astype(np.float64)**2)) for v in b.values());diff=sum(float(np.sum((a[k].astype(np.float64)-b[k])**2)) for k in a);dot=sum(float(np.sum(a[k].astype(np.float64)*b[k])) for k in a)
    altered=y.copy();altered[m==0]=17
    masked=fn(e.params,mx.array(x),mx.array(altered),mx.array(m));mx.eval(masked)
    # Factor 1 is exactly the original supervised objective.
    unit,_=loss_functions(e,1.);orig,_=s.serializer.loss_functions(e)
    meter.reserve(x.size*2,'unit-factor-equivalence')
    u=unit(e.params,mx.array(x),mx.array(y),mx.array(m));o=orig(e.params,mx.array(x),mx.array(y),mx.array(m));mx.eval(u,o)
    result=dict(nll_delta=abs(float(value)-float(loss.detach())),gradient_relative_l2=(diff/aa)**.5,cosine=dot/(aa*bb)**.5,masked_delta=abs(float(value)-float(masked)),unit_factor_delta=abs(float(u)-float(o)),content_weights_unchanged=bool(np.all(np.array(weights)[(m==1)&(y!=2)]==1)),eos_factor=.25)
    s.save(ROOT/'numerical.json',result)
    assert result['nll_delta']<=.02 and result['gradient_relative_l2']<=.08 and result['cosine']>=.995
    assert result['masked_delta']==0 and result['unit_factor_delta']==0 and result['content_weights_unchanged']

def main():
    assert not (ROOT/'ledger.json').exists(),'No implicit retry'
    s.assert_frozen();meter=Meter('ablation')
    try:
        sp=SentencePieceProcessor(model_file=str(s.serializer.TOK));assert sp.eos_id()==2
        rows=s.read(s.PRIVATE/'fit.json');sched=s.read(s.PRIVATE/'schedule.json')['fit'];replay=np.load(s.PRIVATE/'replay.npy').astype(np.int32)
        e,c=s.load(mode='fresh');numerical(e,rows,meter)
        baseline=s.generate(e,c,rows,sp,16,meter,'baseline')
        inspect(e,c,rows,sp,meter,'baseline')
        s.save(ROOT/'baseline.json',baseline);del e,c;gc.collect()
        e,c=s.load(s.PROJECT/'restart/teacher-bridge-execution-v2/private/fit-200.pt');inspect(e,c,rows,sp,meter,'previous-fit-200');del e,c;gc.collect()
        history={'control':[],'eos025':[]}
        for offset in range(0,200,50):
            for arm,factor in [('control',1.),('eos025',.25)]:
                path=s.PROJECT/history[arm][-1]['checkpoint'] if history[arm] else s.SOURCE
                e,c=s.load(path,mode='resume' if history[arm] else 'fresh');_,gfn=loss_functions(e,factor)
                for i in range(offset,offset+50):
                    stats=s.update(e,c,gfn,[('fit',.5,[rows[j] for j in sched[i]])],replay[i],2e-5*min(1,(i+1)/5),meter)
                    with (ROOT/(arm+'-updates.jsonl')).open('a') as f:f.write(json.dumps(stats)+'\n')
                checkpoint=s.checkpoint(e,meter,arm+'-'+str(offset+50));nll=s.foundation(e,meter)
                metrics=s.generate(e,c,rows,sp,16,meter,arm+'-'+str(offset+50))
                item=dict(step=offset+50,narrative_nll=nll,narrative_regression=nll/s.ORIGINAL_NLL-1,fit=metrics,checkpoint=str(checkpoint.relative_to(s.PROJECT)),sha256=s.sha(checkpoint))
                history[arm].append(item);s.save(ROOT/'history.json',history);print(json.dumps(dict(arm=arm,**item)),flush=True)
                assert nll<=s.ORIGINAL_NLL*1.05,'ORIGINAL_NARRATIVE_GUARD'
                if offset==150:inspect(e,c,rows,sp,meter,arm+'-final')
                del e,c,gfn;gc.collect()
        passed={arm:all(history[arm][-1]['fit']['families'][f]['strict']>=15 for f in ['full_name','printed_time']) for arm in history}
        s.save(ROOT/'result.json',dict(status='COMPLETED',passed_fit_gate=passed,history=history,promoted=False,main_study_started=False))
        s.assert_frozen()
    except BaseException as ex:
        s.save(ROOT/'STOP.json',dict(reason=str(ex),type=type(ex).__name__,updates=meter.data['updates'],positions=meter.data['positions']));raise
    finally:meter.close()
if __name__=='__main__':main()
