"""Provision the immutable train-only QuAC parquet with a hard network-byte cap."""
from hashlib import sha256
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
REVISION = "768addbf2099da8efabd67d3a669f6483b813c1b"
SHA = "067c94373d1a622339a73f16032d8060bb5dd989cd8ce2b3647363a8bc1d5b5f"
SIZE = 31324530
BASE = "https://huggingface.co/datasets/allenai/quac/resolve/"
URL = BASE + REVISION + "/plain_text/train/0000.parquet"
PATH = ROOT / "data/quac-train-v1/train.parquet"
LIMIT = 150*1024**2


def acquire():
    if PATH.exists():
        if PATH.stat().st_size!=SIZE or sha256(PATH.read_bytes()).hexdigest()!=SHA:
            raise ValueError("Existing train file failed verification")
        return
    PATH.parent.mkdir(parents=True,exist_ok=True)
    ledger=PATH.parent/"network-bytes.json"
    used=json.loads(ledger.read_text())["reserved"] if ledger.exists() else 0
    if used+SIZE+1>LIMIT:
        raise ValueError("Acquisition ceiling exceeded")
    ledger.write_text(json.dumps({"reserved":used+SIZE+1,"limit":LIMIT}))
    temp=PATH.with_suffix(".partial")
    digest=sha256()
    count=0
    with urllib.request.urlopen(URL,timeout=30) as src,temp.open("xb") as dst:
        declared=src.headers.get("Content-Length")
        if declared and int(declared)!=SIZE:
            raise ValueError("Unexpected declared train payload size")
        while count<=SIZE:
            block=src.read(min(1024*1024,SIZE+1-count))
            if not block:break
            count+=len(block)
            digest.update(block)
            dst.write(block)
    if count!=SIZE or digest.hexdigest()!=SHA:
        raise ValueError("Downloaded train payload failed repository LFS pin")
    temp.replace(PATH)
    ledger.write_text(json.dumps({"reserved":used+SIZE+1,"successful_bytes":count,"limit":LIMIT}))
    print("Verified",count,SHA)


if __name__=="__main__":
    acquire()
