"""Score immutable development-selected references; never fit or tune on final data.

Scoped final evaluator owns holdout access, checkpoint selection and time budget.
This module loads counts and the selected smoothing values from pinned receipts.
"""
import hashlib,io,json
from pathlib import Path
import numpy as np
from .baselines import Unigram
from .kneser_ney import Model,windows
from .numerical_prerequisites import PINS,digest
from .evaluation_snapshot import _file
from .development_loss import summarize


class FrozenBaselines:
    def __init__(self,project):
        self.root=Path(project).resolve(strict=True)/'restart/execution-v1'
        self.pins={}
        def checked(relative,pin):
            path=_file(self.root,relative)
            if digest(path)!=pin:raise ValueError('Changed frozen baseline artifact: '+relative)
            self.pins[relative]=pin;return path.read_bytes()
        train=json.loads(checked('data-train/manifest.json',PINS['data-train/manifest.json']))
        unigram=json.loads(checked('unigram-receipt.json',PINS['unigram-receipt.json']))
        kn=json.loads(checked('kn-preparation/model/receipt.json',PINS['kn-preparation/model/receipt.json']))
        if train['split']!='train' or unigram['status']!='PASS' or kn['status']!='PASS':raise ValueError('Invalid frozen baseline status')
        if unigram['train_manifest_sha256']!=PINS['data-train/manifest.json']:raise ValueError('Unbound unigram training data')
        for receipt in (unigram,kn):
            if receipt['selected']!=min(receipt['trials'],key=lambda row:row['development_nll']):
                raise ValueError('Baseline smoothing was not selected on development')
            if receipt['training_targets']!=train['targets']:raise ValueError('Baseline training counts differ')
        raw=checked('data-train/unigram-counts.npy',train['files']['unigram-counts.npy'])
        counts=np.load(io.BytesIO(raw),allow_pickle=False)
        if counts.shape!=(8192,) or int(counts.sum())!=train['targets']:raise ValueError('Invalid frozen unigram counts')
        expected={'manifest.json'}|{f'{kind}-{n}.npy' for kind in ('grams','counts') for n in range(1,6)}
        if set(kn['files'])!=expected:raise ValueError('Incomplete frozen Kneser-Ney inventory')
        for name,pin in kn['files'].items():checked('kn-preparation/model/'+name,pin)
        self.unigram=Unigram(counts,unigram['selected']['alpha'])
        self.kn=Model(self.root/'kn-preparation/model',scale=kn['selected']['scale'])
        self.selection={'unigram_alpha':self.unigram.alpha,'modified_kneser_ney_scale':self.kn.scale}

    def verify(self):
        for relative,pin in self.pins.items():
            if digest(_file(self.root,relative))!=pin:raise ValueError('Frozen baseline changed during scoring')

    def score(self,store,*,context,heartbeat):
        if context.get('event')!='final_research_evaluation':raise ValueError('Final evaluation context required')
        self.verify();heartbeat()
        unigram=-self.unigram.logp[store.tokens]
        # One query pass avoids rebuilding the large n-gram lookup per segment.
        probabilities=self.kn.probabilities(windows(store.tokens,store.rows))
        heartbeat()
        if probabilities.shape!=(store.targets,) or not np.isfinite(probabilities).all() or np.any(probabilities<=0) or np.any(probabilities>1):
            raise ValueError('Invalid/zero frozen baseline target probability')
        values={'unigram':unigram,'modified_kneser_ney':-np.log(probabilities)}
        offsets={row['audit_id']:row['offset'] for row in store.rows}
        results={}
        for name,losses in values.items():
            if losses.shape!=(store.targets,) or not np.isfinite(losses).all() or np.any(losses<0):raise ValueError('Invalid baseline losses')
            records=[]
            for part in store.segments():
                offset=offsets[part.document]
                records.append(dict(document=part.document,first=part.first,last=part.last,target_ids=list(part.targets),
                    nll=losses[offset+part.first:offset+part.last].tolist()))
            payload={'context':dict(context),'manifest_sha256':store.manifest_sha256,'records':records}
            payload['metrics']=summarize(store,payload);results[name]=payload
            heartbeat()
        self.verify()
        return results,{'selection':self.selection,'artifact_sha256':dict(self.pins),'refitted':False,
                        'selection_basis':'Frozen development receipts; no final-data smoothing search'}
