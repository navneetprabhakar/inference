"""Temporary synthetic stream/custody fixtures only, never real corpus admission."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
from own_base_language_streams import AdmittedStreams,verify_custody,sha
from own_base_language_data import validation_manifest

class Tests(unittest.TestCase):
    def fixture(self,root,combined=False):
        root=root.resolve()
        def write(name,value):
            path=root/name;path.write_text(json.dumps(value));return dict(path=str(path),sha256=sha(path))
        self.write=write;candidate='a'*64
        if combined:
            receipts=[dict(kind='cosmopedia_combined_v1',pin=write('combined.json',dict(state='screened_not_admitted',training_admitted=False,candidate_pins={'candidates.sqlite':candidate},historical_chat_holdouts={'count':6},inventory={'sessions':442},code_sha256={'protect_cosmopedia_candidates.py':'a'*64},excluded_doc_ids=['denied'])))]
        else:
            receipts=[dict(kind='language_legacy_v1',pin=write('legacy.json',dict(state='cleared',candidate_database_sha256=candidate,excluded_doc_ids=['denied']))),dict(kind='language_public_v1',pin=write('public.json',dict(state='screened_not_admitted',training_admitted=False,pins={'candidates.sqlite':candidate},excluded_doc_ids=[])))]
        tokenizer=dict(vocabulary=50257,eot=50256,identity={'fixture':True});docs=[];files=[]
        for split,lengths in [('train',[8193,8193]),('validation',[33,129])]:
            pieces=[];offset=0
            for i,length in enumerate(lengths):
                tokens=np.arange(length,dtype=np.uint16)%32;tokens[-1]=50256;pieces.append(tokens)
                docs.append(dict(id=split+str(i),original_id=split+str(i),file=split+'.u16',offset=offset,tokens=length,family=split+str(i),split=split,sha256='c'*64,text_sha256=('d' if split=='train' else 'e')*64));offset+=length
            path=root/(split+'.u16');np.concatenate(pieces).astype('<u2').tofile(path);files.append(dict(file=path.name,split=split,tokens=offset,sha256=sha(path)))
        policy=write('quality.json',{'fixture':True})
        manifest=dict(schema=1,state='packed_pending_training_admission',name='fixture',tokenizer=tokenizer,candidate_sha256=candidate,custody_receipts=receipts,quality_policy=policy,files=files,documents=docs)
        mp=write('manifest.json',manifest)
        original=write('original-manifest.json',dict(state='packed_pending_independent_verification',failure=None))
        originalproof=write('original-proof.json',dict(state='PASS_independent_narrative_packing_not_admitted',manifest_sha256=original['sha256'],failures=[]))
        proof=write('independent.json',dict(state='PASS_canonical_manifest_projection',manifest_sha256=mp['sha256'],failures=[],excluded_ids_absent=True,full_document_tokens_verified=True,underlying_packing_manifest=original,underlying_packing_proof=originalproof,mapping_scope='synthetic fixture projection'))
        admission=write('admission.json',dict(training_admitted=True,manifest_sha256=mp['sha256'],verification_sha256=proof['sha256'],custody_receipts=receipts,quality_policy=policy))
        windows=[dict(source='fixture',id=d['id'],offset=0,targets=d['tokens']-1) for d in docs if d['split']=='validation']
        held=[dict(source='fixture',**{k:d[k] for k in ('id','tokens','split','sha256')}) for d in docs if d['split']=='validation']
        selection=write('selection.json',dict(windows=windows,manifest=validation_manifest(held,windows)))
        return dict(tokenizer=tokenizer,seed=7,length=512,row_source_cycle=['fixture']*16,sources=[dict(name='fixture',passes=1,manifest=mp,verification=proof,admission=admission)],validation_selection=selection),manifest
    def test_real_schema_shapes_and_row_assembly(self):
        for combined in (False,True):
            with tempfile.TemporaryDirectory() as td:
                spec,m=self.fixture(Path(td),combined);data=AdmittedStreams(spec);rows,state=data.schedule.next_update(data.schedule.initial())
                for row in rows:
                    actual=data.row(row);self.assertEqual(len(actual),513)
                    expected=[]
                    for span in row['input_spans']:
                        d=data.docs[('fixture',span['document'])];a=data.arrays[('fixture',d['file'])];expected.extend(a[d['offset']+span['offset']:d['offset']+span['offset']+span['count']].tolist())
                    self.assertEqual(actual.tolist(),expected)
                self.assertEqual(len(data.validation_row(data.validation['windows'][0])),33)
    def test_missing_scope_candidate_mismatch_and_hash_tamper(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);spec,m=self.fixture(root)
            with self.assertRaises(ValueError):verify_custody(m['custody_receipts'][:1],m['candidate_sha256'])
            with self.assertRaises(ValueError):verify_custody(m['custody_receipts'],'f'*64)
            (root/'train.u16').write_bytes(b'bad')
            with self.assertRaises(ValueError):AdmittedStreams(spec)
    def test_excluded_original_id_and_gap_refused_even_with_fresh_pins(self):
        for key,value in [('original_id','denied'),('offset',1)]:
            with tempfile.TemporaryDirectory() as td:
                spec,m=self.fixture(Path(td));m['documents'][0][key]=value
                descriptor=spec['sources'][0];descriptor['manifest']=self.write('manifest.json',m)
                proof=json.loads(Path(descriptor['verification']['path']).read_text());proof['manifest_sha256']=descriptor['manifest']['sha256'];descriptor['verification']=self.write('independent.json',proof)
                admission=json.loads(Path(descriptor['admission']['path']).read_text());admission.update(manifest_sha256=descriptor['manifest']['sha256'],verification_sha256=descriptor['verification']['sha256']);descriptor['admission']=self.write('admission.json',admission)
                with self.assertRaises(ValueError):AdmittedStreams(spec)
    def test_receipt_not_relabelled_and_unadmitted_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);spec,m=self.fixture(root,True);pin=m['custody_receipts'][0]['pin'];original=Path(pin['path']).read_bytes()
            AdmittedStreams(spec);self.assertEqual(Path(pin['path']).read_bytes(),original)
            admission=json.loads(Path(spec['sources'][0]['admission']['path']).read_text());admission['training_admitted']=False;spec['sources'][0]['admission']=self.write('admission.json',admission)
            with self.assertRaisesRegex(ValueError,'admission'):AdmittedStreams(spec)

if __name__=='__main__':unittest.main(verbosity=2)
