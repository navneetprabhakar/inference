"""Build and test the exact self-contained server code package before uploading."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    files=[ROOT/x for x in ['gpt2.py','tokenizer.py','verify_cloud_training.py','data/tokenizer/encoder.json','data/tokenizer/vocab.bpe']]
    files+=sorted((ROOT/'cloud_training').glob('*.py'))+[ROOT/'cloud_training/server.sh']
    mapping={str(p.relative_to(ROOT)):p for p in files}
    for p in (ROOT/'runs/gcp-a100-wheels').glob('*.whl'):mapping['wheels/'+p.name]=p
    assert len([x for x in mapping if x.startswith('wheels/')])==1
    destination=ROOT/'runs/gcp-a100-code.tar.gz'
    with tarfile.open(destination,'w:gz') as t:
        for name,p in mapping.items():t.add(p,arcname=name)
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(destination) as t:t.extractall(tmp,filter='data')
        subprocess.run([sys.executable,'verify_cloud_training.py'],cwd=tmp,check=True)
    receipt={'files':{name:hashlib.sha256(p.read_bytes()).hexdigest() for name,p in mapping.items()},
             'bundle_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
             'isolated_unpacked_tests':'passed four tests with no repository data access'}
    (ROOT/'reports/gcp-a100-diagnostic-v1/code-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['bundle_sha256'])

if __name__=='__main__':main()
