"""Read-only admitted token spans. No downloading, packing, source repair or admission."""
import hashlib
import json
from pathlib import Path
import numpy as np
from own_base_language_data import require, integer, MixedSchedule, validation_manifest


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def pinned(pin):
    require(set(pin)=={'path','sha256'},'exact artifact pin required')
    p=Path(pin['path']);require(p.is_absolute() and p==p.resolve() and not p.is_symlink(),'canonical artifact path required')
    require(sha(p)==pin['sha256'],'artifact checksum mismatch')
    return json.loads(p.read_text())


def verify_custody(receipts, candidate_sha256):
    """Read actual root receipt schemas without relabeling them as admission."""
    scopes=set();excluded=set()
    for item in receipts:
        proof=pinned(item['pin']);kind=item['kind']
        if kind=='language_legacy_v1':
            require(proof.get('state')=='cleared' and proof.get('candidate_database_sha256')==candidate_sha256,'legacy custody identity')
            scopes.add('legacy');excluded.update(proof['excluded_doc_ids'])
        elif kind=='language_public_v1':
            require(proof.get('state')=='screened_not_admitted' and proof.get('training_admitted') is False and proof['pins']['candidates.sqlite']==candidate_sha256,'public custody identity')
            scopes.add('public-development');excluded.update(proof['excluded_doc_ids'])
        elif kind=='cosmopedia_combined_v1':
            require(proof.get('state')=='screened_not_admitted' and proof.get('training_admitted') is False and proof['candidate_pins']['candidates.sqlite']==candidate_sha256,'combined custody identity')
            require('historical_chat_holdouts' in proof and proof.get('inventory') and 'protect_cosmopedia_candidates.py' in proof['code_sha256'],'combined historical/public coverage proof')
            scopes.update(('legacy','public-development'));excluded.update(proof['excluded_doc_ids'])
        elif kind=='narrative_projection_union_v1':
            require(proof.get('state')=='PASS_projection_root_custody_union_bound_not_admitted' and proof.get('training_admitted') is False and proof.get('database_sha256')==candidate_sha256 and proof.get('failures')==[],'narrative projection union identity')
            links=item['underlying']
            for key,field in [('legacy','legacy_custody_sha256'),('public','public_custody_sha256'),('projection','projection_verification_sha256'),('quality','quality_exclusions_sha256')]:
                require(links[key]['sha256']==proof[field],'projection underlying receipt binding');pinned(links[key])
            original=proof['original_database_sha256']
            denied=verify_custody([dict(kind='language_legacy_v1',pin=links['legacy']),dict(kind='language_public_v1',pin=links['public'])],original)
            projection=pinned(links['projection']);require(projection.get('state')=='PASS_independent_exact_projection_not_admitted' and projection.get('database_sha256')==candidate_sha256 and projection.get('manifest_sha256')==proof['manifest_sha256'] and projection.get('failures')==[],'independent projection proof differs')
            require(projection.get('source_database_sha256')==original,'projection original source differs')
            quality=pinned(links['quality']);require(isinstance(quality,list) and all(isinstance(x,dict) and isinstance(x.get('doc_id'),str) for x in quality),'quality exclusion schema')
            scopes.update(('legacy','public-development'));excluded.update(denied);excluded.update(x['doc_id'] for x in quality)
        else:raise ValueError('unknown custody schema; explicit adapter required')
    require(scopes=={'legacy','public-development'},'complete historical/public custody coverage required')
    return excluded


class AdmittedStreams:
    def __init__(self, spec, *, check=lambda:None):
        self.arrays={};self.docs={};sources=[];held=[];families={'train':set(),'validation':set()};fingerprints={'train':set(),'validation':set()}
        require(spec['tokenizer']=={'vocabulary':50257,'eot':50256,'identity':spec['tokenizer']['identity']},'explicit GPT2 tokenizer identity')
        names=set()
        for descriptor in spec['sources']:
            check();name=descriptor['name'];require(name not in names and isinstance(name,str),'unique source');names.add(name)
            manifest=pinned(descriptor['manifest']);admission=pinned(descriptor['admission']);verification=pinned(descriptor['verification'])
            require(manifest.get('schema')==1 and manifest.get('state')=='packed_pending_training_admission','packed stream contract required')
            require(manifest['name']==name and manifest['tokenizer']==spec['tokenizer'],'source/tokenizer identity')
            require(admission.get('training_admitted') is True and admission.get('manifest_sha256')==descriptor['manifest']['sha256'],'root training admission required')
            require(verification.get('state')=='PASS_canonical_manifest_projection' and verification.get('manifest_sha256')==descriptor['manifest']['sha256'] and verification.get('failures')==[],'canonical projection proof required')
            original_proof=pinned(verification['underlying_packing_proof']);original_manifest=pinned(verification['underlying_packing_manifest'])
            original_states={'PASS_independent_narrative_packing_not_admitted':'manifest_sha256','PASS_separate_full_replay_not_admitted':'dataset_sha256'}
            require(original_proof.get('state') in original_states and original_proof.get('failures')==[],'actual underlying packing verification required')
            require(original_proof[original_states[original_proof['state']]]==verification['underlying_packing_manifest']['sha256'],'underlying proof/manifest binding')
            require(original_manifest.get('state')=='packed_pending_independent_verification' and original_manifest.get('failure') is None and verification.get('mapping_scope'),'actual complete packing and explicit projection scope')
            require(admission['verification_sha256']==descriptor['verification']['sha256'],'admission must bind independent proof')
            require(admission['custody_receipts']==manifest['custody_receipts'],'admission custody pins differ')
            excluded=verify_custody(manifest['custody_receipts'],manifest['candidate_sha256'])
            require(admission['quality_policy']==manifest['quality_policy'],'quality policy admission binding');pinned(manifest['quality_policy'])
            require(verification.get('excluded_ids_absent') is True and verification.get('full_document_tokens_verified') is True,'independent exclusion/token checks required')
            directory=Path(descriptor['manifest']['path']).parent;files={}
            for f in manifest['files']:
                check();require(f['split'] in ('train','validation') and Path(f['file']).name==f['file'],'explicit local split file')
                p=directory/f['file'];require(not p.is_symlink() and p.stat().st_size==2*f['tokens'] and sha(p)==f['sha256'],'packed token file integrity')
                a=np.memmap(p,dtype='<u2',mode='r');require(f['file'] not in files,'unique file');files[f['file']]=dict(array=a,split=f['split'],ranges=[])
                for start in range(0,len(a),1048576):check();require(bool(np.all(a[start:start+1048576]<50257)),'token outside vocabulary')
                self.arrays[(name,f['file'])]=a
            training=[]
            for d in manifest['documents']:
                check();require(isinstance(d.get('original_id'),str) and d['original_id'] not in excluded,'original candidate ID excluded or missing')
                require(d['file'] in files and d['split']==files[d['file']]['split'],'document split/file binding')
                require(integer(d['offset']) and integer(d['tokens'],2),'document range')
                a=files[d['file']]['array'];require(d['offset']+d['tokens']<=len(a) and int(a[d['offset']+d['tokens']-1])==50256,'document range/EOT')
                key=(name,d['id']);require(key not in self.docs,'unique source document ID');self.docs[key]=d
                files[d['file']]['ranges'].append((d['offset'],d['offset']+d['tokens']))
                require(isinstance(d['family'],str) and d['family'],'global family identity required')
                require(isinstance(d['text_sha256'],str) and len(d['text_sha256'])==64,'original text fingerprint')
                families[d['split']].add(d['family']);fingerprints[d['split']].add(d['text_sha256'])
                small={k:d[k] for k in ('id','tokens','family','split','sha256')}
                if d['split']=='train':training.append(small)
                else:held.append(dict(small,source=name))
            for f in files.values():
                position=0
                for start,end in sorted(f['ranges']):require(start==position,'overlapping/gapped document index');position=end
                require(position==len(f['array']),'unindexed token tail')
            sources.append(dict(name=name,passes=descriptor['passes'],documents=training))
        require(not families['train']&families['validation'] and not fingerprints['train']&fingerprints['validation'],'cross-source train/validation leakage')
        self.schedule=MixedSchedule(dict(schema=1,seed=spec['seed'],length=spec['length'],sources=sources,row_source_cycle=spec['row_source_cycle']))
        selected=pinned(spec['validation_selection']);self.validation=validation_manifest(held,selected['windows'],maximum_targets=512)
        require(selected['manifest']==self.validation,'frozen validation selection differs from admitted documents')

    def row(self, row):
        pieces=[]
        for span in row['input_spans']:
            d=self.docs[(row['source'],span['document'])];require(0<=span['offset'] and span['offset']+span['count']<=d['tokens'],'span outside admitted document')
            start=d['offset']+span['offset'];pieces.append(self.arrays[(row['source'],d['file'])][start:start+span['count']])
        result=np.concatenate(pieces).astype(np.int64);require(len(result)==row['targets']+1,'shifted row targets');return result

    def validation_row(self, window):
        d=self.docs[(window['source'],window['id'])];require(d['split']=='validation' and window['offset']+window['targets']<d['tokens'],'heldout window only')
        start=d['offset']+window['offset'];return self.arrays[(window['source'],d['file'])][start:start+window['targets']+1].astype(np.int64)
