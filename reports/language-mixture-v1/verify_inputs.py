"""Read-only source validation after candidate build; writes one supplemental receipt."""
import os
os.environ['TOKENIZERS_PARALLELISM']='false'
os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time
import unicodedata
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tokenizer import ASSETS, load
DATA=ROOT/'data/language-mixture-v1'


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def norm(text):
    return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())


def verify(manifest_name):
    started=time.monotonic()
    result={'state':'pending','checks':{},'prior_corpora':{},'failures':[]}
    output=DATA/'input-verification.json'
    if output.exists():raise FileExistsError(output)
    try:
        if manifest_name not in ('candidate-manifest.json','partial-candidate-manifest.json'):raise ValueError('explicit known candidate manifest required')
        manifest_path=DATA/manifest_name
        candidate=json.loads(manifest_path.read_text())
        result['candidate_manifest_name']=manifest_name
        result['candidate_state']=candidate['state']
        if digest(DATA/'candidates.sqlite')!=candidate['candidate_database_sha256']:
            raise ValueError('candidate SQL changed after freeze')
        result['candidate_database_sha256']=candidate['candidate_database_sha256']
        result['candidate_manifest_sha256']=digest(manifest_path)
        budget=json.loads((ROOT/'reports/base-foundation-100m/budget.json').read_text())
        foundation=ROOT/'data/base-foundation-100m'
        if digest(foundation/'manifest.json')!=budget['manifest_sha256']:
            raise ValueError('foundation corpus manifest differs from frozen budget')
        fm=json.loads((foundation/'manifest.json').read_text())
        psl=ROOT/'reports/base-foundation-100m/public_suffix_list.dat'
        if digest(psl)!=fm['source']['psl_sha256']:raise ValueError('PSL differs from frozen foundation source')
        result['checks']['public_suffix_list_sha256']=digest(psl)
        if digest(ROOT/'tokenizer.py')!=budget['code_sha256']['tokenizer.py']:
            raise ValueError('tokenizer code differs from frozen budget')
        result['checks']['tokenizer_code_sha256']=digest(ROOT/'tokenizer.py')
        for name,expected in ASSETS.items():
            actual=digest(ROOT/'data/tokenizer'/name)
            if actual!=expected:raise ValueError('tokenizer asset changed: '+name)
        result['checks']['tokenizer_assets']=ASSETS
        helper=ROOT/'reports/base-foundation-100m/build.py'
        committed=subprocess.check_output(['git','show','ac54b56:reports/base-foundation-100m/build.py'],cwd=ROOT)
        expected=hashlib.sha256(committed).hexdigest()
        if digest(helper)!=expected:raise ValueError('imported helper differs from original foundation commit')
        result['checks']['imported_helper']={'sha256':expected,'git_reference':'ac54b56:reports/base-foundation-100m/build.py'}
        tok=load()
        for relative,pinned in candidate['prior_indexes'].items():
            path=ROOT/relative
            if digest(path)!=pinned:raise ValueError('prior document index changed: '+relative)
            manifest_path=path.parent/'manifest.json'
            manifest=json.loads(manifest_path.read_text())
            if digest(path)!=manifest['documents_sha256']:raise ValueError('prior index/manifest disagreement: '+relative)
            record={'manifest_sha256':digest(manifest_path),'documents_sha256':pinned,'shards':{},'decoded_rows_checked':0}
            arrays={}
            with path.open() as stream:
                for count,line in enumerate(stream):
                    if count%1000==0:
                        if time.monotonic()-started>600:raise RuntimeError('10minute independent verification cap')
                        if (ROOT/'runs/STOP').exists() or (DATA/'STOP').exists():raise RuntimeError('explicit STOP')
                    row=json.loads(line)
                    if row['source']!='stories' and row['split']!='validation':continue
                    source='fineweb' if row['source']=='fineweb' else row['source']
                    key=source+'-'+row['split']
                    binary=path.parent/(key+'.u16')
                    if key not in arrays:
                        info=manifest['shards'][key]
                        actual=digest(binary)
                        if actual!=info['sha256'] or binary.stat().st_size!=info['tokens']*2:
                            raise ValueError('prior shard digest/length mismatch: '+str(binary))
                        a=np.memmap(binary,mode='r',dtype='<u2')
                        if bool(np.any(a>50256)):raise ValueError('prior shard out-of-range token')
                        arrays[key]=a
                        record['shards'][key]={'sha256':actual,'tokens':len(a)}
                    offset,length=row['offset'],row['tokens']
                    if type(offset) is not int or type(length) is not int or offset<0 or length<1 or offset+length>len(arrays[key]):
                        raise ValueError('prior document cursor outside source')
                    ids=arrays[key][offset:offset+length]
                    if ids[-1]!=50256 or bool(np.any(ids[:-1]==50256)):
                        raise ValueError('prior document EOT boundary mismatch')
                    decoded=tok.decode(ids[:-1].tolist())
                    if hashlib.sha256(norm(decoded).encode()).hexdigest()!=row['normalized_sha256']:
                        raise ValueError('decoded document normalized hash mismatch: '+str(row['document_id']))
                    record['decoded_rows_checked']+=1
            result['prior_corpora'][relative]=record
            arrays.clear()
        if digest(DATA/'candidates.sqlite')!=candidate['candidate_database_sha256']:
            raise ValueError('candidate changed during verification')
        result['state']='passed_input_integrity_only'
        result['not_admitted']=True
        result['pending']='Root protected-case custody, quality review and target shortfall resolution; no packing or training.'
    except Exception as error:
        result['state']='rejected_input_verification'
        result['failures'].append(f'{type(error).__name__}: {error}')
    result['seconds']=time.monotonic()-started
    result['verifier_sha256']=digest(__file__)
    temp=output.with_suffix('.tmp')
    temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(output)
    print(json.dumps({'state':result['state'],'failures':result['failures'],'seconds':result['seconds']}))
    return 0 if result['state']=='passed_input_integrity_only' else 1


if __name__=='__main__':
    from argparse import ArgumentParser
    parser=ArgumentParser();parser.add_argument('--manifest',required=True)
    args=parser.parse_args();sys.exit(verify(args.manifest))
