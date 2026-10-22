"""Revalidate existing tokenizer, split and baseline preparation before toy launch."""
import hashlib,json
from pathlib import Path
from .evaluation_snapshot import verify as verify_evaluation,_file

PINS={'tokenizer-receipt.json': 'a0b67529e2a0310556d0cc2c0dbc09fc6f7dd8611f7b367f22c77e47503917c2', 'tokenizer-8192/manifest.json': '577c0f59ffc594931650de802c4630f3171ebde139cc32c742f5f264e7f98812', 'loss-data-receipt.json': 'dea09e5dc61b5b9a248164a4599dec01a24f815dac5244abf4f767b282712e4f', 'loss-data-verification.json': 'c966c339ed60023fc32ffc486700b7a197111f3e24b7a2878cd38d2e9a653436', 'data-train/manifest.json': '05bbbe88fa29b9a18f0ad1d5b275cc92a1a08d4acb183b6cba921ff7ee88d803', 'data-dev/manifest.json': 'df70193044cdad381730573ce300b03c73fe28d7c3122f6a16c85ad0074f2251', 'data-final/manifest.json': 'd37309d9ac37cbe1d7b2da5c0b0a79d9bd7faa95d3f56f20d64baa6407522cef', 'unigram-receipt.json': '2913b668025457e29434492d320c8fd6ca9580ba4d8d8a81a05c70893ce0dcc1', 'kn-preparation/model/receipt.json': '891c4983c5e5de6e2e103ec08da7ca50a2c319db7222ac4eadd28d7412289e6f'}


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def verify(project):
    project=Path(project).resolve(strict=True);root=project/'restart/execution-v1'
    evaluation=verify_evaluation(project)
    for relative,pin in PINS.items():
        if digest(_file(root,relative))!=pin:raise ValueError('Changed preparation evidence: '+relative)
        data=json.loads(_file(root,relative).read_bytes())
        for name,expected in data.get('files',{}).items():
            if digest(_file(root,str(Path(relative).parent/name)))!=expected:
                raise ValueError('Changed preparation data: '+relative+':'+name)
    return {'status':'PREREQUISITE_BYTES_VERIFIED','pinned_files':PINS,
            'evaluation_manifest_sha256':evaluation['manifest_sha256'],
            'final_paths':evaluation['final_files'],'training_authorized_by_this_check':False}
