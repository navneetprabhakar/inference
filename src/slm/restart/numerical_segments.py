"""Six numerical-suite data/segmentation checks; no model computation."""
import hashlib,json
from pathlib import Path
import tempfile
import numpy as np
from .segments import segments,collate
from .token_store import TrainingTokens


def run(long_documents,output_root,*,segmenter=segments,collator=collate):
    conditions={k:True for k in ('bos_target_shift','single_document_eos','long_document_unique_targets','one_predecessor_context','family_split_identity_retained','padding_not_counted')}
    groups={}
    for key,content in long_documents.items():
        if len(content)!=int(key):raise ValueError('Changed long-document fixture')
        doc='fixture:'+key;parts=list(segmenter(doc,content,512));groups[doc]=parts
        x=[t for p in parts for t in p.inputs];y=[t for p in parts for t in p.targets]
        conditions['bos_target_shift'] &= x==[0]+content and y==content+[1]
        conditions['single_document_eos'] &= y.count(1)==1 and y[-1:]==[1]
        positions=[i for p in parts for i in range(p.first,p.last)]
        conditions['long_document_unique_targets'] &= positions==list(range(len(content)+1))
        stream=[0]+content
        conditions['one_predecessor_context'] &= all(p.inputs and p.inputs[0]==stream[p.first] and len(p.inputs)<=512 for p in parts)
        conditions['family_split_identity_retained'] &= all(p.document==doc for p in parts)
    # Different-length rows preserve separate sequences and exclude padding targets.
    rows=[groups['fixture:1'][0],groups['fixture:513'][0],groups['fixture:0'][0]]
    x,y,mask,spans=collator(rows)
    conditions['padding_not_counted'] &= int(mask.sum())==sum(len(p.targets) for p in rows)
    for i,p in enumerate(rows):
        n=len(p.targets)
        conditions['padding_not_counted'] &= (x[i,:n].tolist()==list(p.inputs) and y[i,:n].tolist()==list(p.targets)
            and mask[i,:n].tolist()==[1.]*n and np.all(mask[i,n:]==0)
            and np.all(x[i,n:]==2) and np.all(y[i,n:]==2))
        conditions['family_split_identity_retained'] &= spans[i]==(p.document,p.first,p.last)
    # Exercise actual train-only reader lineage checks with hash-valid synthetic files.
    with tempfile.TemporaryDirectory(prefix='numeric-lineage-',dir=output_root) as temp:
        root=Path(temp);content=[10,11,1];(root/'tokens.u16').write_bytes(np.asarray(content,dtype='<u2').tobytes())
        row={'audit_id':'fixture:source','family_id':'fixture:family','split':'train','partial':False,'offset':0,'targets':3,'full_document_targets':3}
        def publish():
            (root/'index.jsonl').write_text(json.dumps(row)+'\n')
            manifest={'split':'train','targets':3,'documents':1,'families':1,'files':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ('tokens.u16','index.jsonl')}}
            (root/'manifest.json').write_text(json.dumps(manifest))
            return hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()
        reader=TrainingTokens(root,manifest_sha256=publish(),vocab_size=16)
        returned=reader.segment('fixture:source',0,3)
        conditions['family_split_identity_retained'] &= (returned.document==row['audit_id']
            and reader._index[returned.document]['family_id']==row['family_id']
            and reader._index[returned.document]['split']=='train')
        try:reader.segment('wrong-source',0,3)
        except ValueError:pass
        else:conditions['family_split_identity_retained']=False
        row['split']='test'
        try:TrainingTokens(root,manifest_sha256=publish(),vocab_size=16)
        except ValueError:pass
        else:conditions['family_split_identity_retained']=False
    cases={'segmentation:'+k:{'passed':bool(v),'comparison':'exact discrete identity/counts'} for k,v in conditions.items()}
    return {'cases':cases,'passed':all(v['passed'] for v in cases.values()),'fixture_documents':len(long_documents),'neural_work_positions':0}
