"""Synthetic CPU-only tests; no dataset/private-file reads, packing or training."""
import copy
import hashlib
import json
import math

import numpy as np
import torch

import stratified_language_validation as validation


def fixture():
    shards={};documents=[]
    for source in ('dialogue','stories','web'):
        pieces=[];offset=0
        for index,length in enumerate((3,4,6,11,2)):
            # IDs vary by document; terminal EOT is the final and only15.
            a=np.array([(index+q)%14+1 for q in range(length-1)]+[15],dtype='<u2')
            documents.append(dict(source=source,document_id=f'doc-{index}',offset=offset,tokens=length,
                                  document_sha256=validation.token_sha256(a)))
            pieces.append(a);offset+=length
        shards[source]=np.concatenate(pieces)
    pins={s:dict(tokens=a.size,sha256=validation.token_sha256(a)) for s,a in shards.items()}
    return shards,documents,pins


class PredictNext(torch.nn.Module):
    def __init__(self):super().__init__();self.calls=[]
    def forward(self,inputs):
        assert inputs.device.type=='cpu'
        self.calls.append(inputs.clone())
        logits=torch.zeros((1,inputs.shape[1],16),device='cpu',dtype=torch.float32)
        logits.scatter_(-1,((inputs+1)%16).unsqueeze(-1),1.5)
        return logits


def run():
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    shards,docs,pins=fixture()
    args=dict(seed=37,documents_per_source=4,min_targets=2,max_targets=8,vocab_size=16,eot=15,short_boundary_targets=8)
    manifest=validation.select_windows(shards,docs,pins,**args)
    assert manifest==validation.select_windows(dict(reversed(list(shards.items()))),list(reversed(docs)),pins,**args)
    checked=validation.verify_windows(shards,manifest,expected_selection_sha256=manifest['selection_sha256'])
    assert len(checked)==12
    for source,counts in manifest['counts'].items():
        assert counts['selected_short_documents']==3 and counts['excluded_too_short']==1
        assert counts['selected_documents']==4
    for row in checked:
        assert row['start']>=row['document_offset']
        assert row['start']+row['targets']+1<=row['document_offset']+row['document_tokens']
        window=shards[row['source']][row['start']:row['start']+row['targets']+1]
        assert 15 not in window[:-1]
        if row['document_tokens']<=9:assert row['local_start']==0 and window[-1]==15
    # Seeded selection/start is repeatable, but different seeds can change both.
    selected=[];starts=[]
    for seed in range(10):
        m=validation.select_windows(shards,docs,pins,**dict(args,seed=seed,documents_per_source=2))
        selected.append(tuple((w['source'],w['document_id']) for w in m['windows']))
        long=validation.select_windows(shards,docs,pins,**dict(args,seed=seed))
        starts.append(tuple(w['local_start'] for w in long['windows'] if w['document_id']=='doc-3'))
    assert len(set(selected))>1 and len(set(starts))>1
    model=PredictNext();model.train(True)
    result=validation.evaluate_cpu(model,shards,manifest,expected_selection_sha256=manifest['selection_sha256'])
    assert model.training is True and len(model.calls)==12
    for row,inputs in zip(result['documents'],model.calls):
        sequence=shards[row['source']][row['start']:row['start']+row['targets']+1].astype(np.int64)
        assert np.array_equal(inputs.numpy()[0],sequence[:-1])
        # Independent analytic CE: logits have one1.5 and15zeros.
        z=math.log(math.exp(1.5)+15)
        expected=sum(z-(1.5 if int(y)==(int(x)+1)%16 else 0.) for x,y in zip(sequence[:-1],sequence[1:]))
        assert abs(row['nll_sum']-expected)<3e-6
    # Explicit unequal-window example: document mean differs from token mean.
    summary=validation.summarize([dict(source='a',document_id='x',targets=2,nll_sum=2.,length_stratum='short'),
                                  dict(source='a',document_id='y',targets=8,nll_sum=24.,length_stratum='long'),
                                  dict(source='b',document_id='z',targets=4,nll_sum=8.,length_stratum='short')])
    assert summary['by_source']['a']['document_mean_ce']==2
    assert summary['by_source']['a']['token_weighted_ce']==2.6
    assert summary['overall']['document_mean_ce']==2
    assert summary['overall']['token_weighted_ce']==34/14
    assert summary['source_balanced_document_mean_ce']==2
    assert summary['by_source']['a']['by_length_stratum']['short']['document_mean_ce']==1
    assert summary['by_source']['a']['by_length_stratum']['long']['token_weighted_ce']==3
    quotas={source:dict(short=2,long=1) for source in shards}
    quota_args=dict(args,documents_per_source=3,per_source_quotas=quotas)
    quota=validation.select_windows(shards,docs,pins,**quota_args)
    assert quota==validation.select_windows(shards,list(reversed(docs)),pins,**quota_args)
    assert quota['sampling_policy']['population_estimate'] is False
    assert quota['sampling_policy']['mode']=='per-source-length-quotas'
    quota_result=validation.evaluate_cpu(PredictNext(),shards,quota,expected_selection_sha256=quota['selection_sha256'])
    for source in shards:
        strata=quota_result['summary']['by_source'][source]['by_length_stratum']
        assert strata['short']['documents']==2 and strata['long']['documents']==1
    failures=0
    for bad in [{source:dict(short=1,long=2) for source in shards},
                {source:dict(short=2,long=2) for source in shards},
                {'web':dict(short=2,long=1)}]:
        try:validation.select_windows(shards,docs,pins,**dict(quota_args,per_source_quotas=bad))
        except ValueError:failures+=1
        else:raise AssertionError('invalid/unsatisfiable quotas accepted')
    for name in ('duplicate','overlap','source_hash','document_hash','bounds','interior_eot','missing_eot',
                 'vocab','insufficient','bad_window_size','bad_dtype','noncontiguous'):
        ss={s:a.copy() for s,a in shards.items()};dd=copy.deepcopy(docs);pp=copy.deepcopy(pins);aa=dict(args)
        if name=='duplicate':dd.append(dict(dd[0]))
        elif name=='overlap':dd.append(dict(dd[0],document_id='different-id'))
        elif name=='source_hash':pp['web']['sha256']='0'*64
        elif name=='document_hash':dd[0]['document_sha256']='0'*64
        elif name=='bounds':dd[0]['offset']=-1
        elif name in ('interior_eot','missing_eot','vocab'):
            pos=0 if name!='missing_eot' else 2
            ss['dialogue'][pos]=15 if name=='interior_eot' else 16 if name=='vocab' else 1
            pp['dialogue']['sha256']=validation.token_sha256(ss['dialogue'])
            dd[0]['document_sha256']=validation.token_sha256(ss['dialogue'][:3])
        elif name=='insufficient':aa['documents_per_source']=5
        elif name=='bad_window_size':aa['max_targets']=1
        elif name=='bad_dtype':ss['dialogue']=ss['dialogue'].astype(np.int64)
        elif name=='noncontiguous':ss['dialogue']=np.repeat(ss['dialogue'],2)[::2]
        try:validation.select_windows(ss,dd,pp,**aa)
        except ValueError:failures+=1
        else:raise AssertionError('invalid input accepted: '+name)
    # Entire manifest/source/doc validation must finish before any model call.
    for mode in ('manifest_change','source_change','bad_document_with_valid_manifest_hash'):
        model=PredictNext();mm=copy.deepcopy(manifest);ss={s:a.copy() for s,a in shards.items()}
        expected=manifest['selection_sha256']
        if mode=='manifest_change':mm['windows'][0]['start']+=1
        elif mode=='source_change':ss['web'][0]=8
        else:
            mm['windows'][-1]['document_sha256']='0'*64
            plain={k:v for k,v in mm.items() if k!='selection_sha256'}
            expected=hashlib.sha256(validation.canonical(plain)).hexdigest();mm['selection_sha256']=expected
        try:validation.evaluate_cpu(model,ss,mm,expected_selection_sha256=expected)
        except ValueError:failures+=1
        else:raise AssertionError('bad validation identity accepted')
        assert not model.calls
    class WrongDtype(PredictNext):
        def __init__(self):
            super().__init__();self.weight=torch.nn.Parameter(torch.ones(1,dtype=torch.float64))
    wrong=WrongDtype()
    try:validation.evaluate_cpu(wrong,shards,manifest,expected_selection_sha256=manifest['selection_sha256'])
    except ValueError:failures+=1
    else:raise AssertionError('non-FP32 parameters accepted')
    assert not wrong.calls
    # Model state restored on interruption, and explicit budget hook is honored.
    model=PredictNext();model.train(True)
    def stop():raise InterruptedError('synthetic STOP')
    try:validation.evaluate_cpu(model,shards,manifest,expected_selection_sha256=manifest['selection_sha256'],check=stop)
    except InterruptedError:pass
    else:raise AssertionError('budget hook ignored')
    assert model.training and not model.calls
    # The production default is128distinct docs/source; prove short windows fit.
    many=np.tile(np.array([1,2,15],dtype='<u2'),128)
    records=[dict(source='short',document_id=str(i),offset=i*3,tokens=3,
                  document_sha256=validation.token_sha256(many[i*3:i*3+3])) for i in range(128)]
    selected=validation.select_windows({'short':many},records,{'short':dict(tokens=many.size,sha256=validation.token_sha256(many))},
                                        seed=0,min_targets=2,max_targets=8,vocab_size=16,eot=15,short_boundary_targets=8)
    assert len(selected['windows'])==128 and all(w['targets']==2 for w in selected['windows'])
    print(json.dumps(dict(state='passed',sources=3,scored_documents=12,default_selection_documents=128,
                         rejected_cases=failures,boundary_shift_and_terminal_eot=True,short_documents_retained=True,
                         stable_input_order=True,seed_variation=True,unequal_weighting=True,quota_strata=True,
                         population_mean_claim=False,device='cpu',
                         actual_data_read=False,gpu_operations=False)))

if __name__=='__main__':run()
