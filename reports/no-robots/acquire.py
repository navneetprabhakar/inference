"""Provision the immutable train-only No Robots parquet with a hard network-byte cap."""
from hashlib import sha256
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
REVISION = "e6f9a4ac5c37faeb744ba9ecf0473184d7f8105b"
SHA = "76d64120a2ab20eb85d6b22bdced5b1ec638a6213a97004741006745c92489ef"
SIZE = 10474682
BASE = "https://huggingface.co/datasets/HuggingFaceH4/no_robots/resolve/"
URL = BASE + REVISION + "/data/train-00000-of-00001.parquet"
PATH = ROOT / "data/no-robots/train.parquet"
LIMIT = 30*1024**2


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
