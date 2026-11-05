from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import sys
REPORT=Path(__file__).resolve().parent
DEST=REPORT.parents[1]/'data/taskmaster2'

def review(usage,salt,n):
    grouped=defaultdict(list)
    for line in (DEST/(usage+'-train.jsonl')).open():
        r=json.loads(line);grouped[r['domain']].append(r)
    for domain,rows in sorted(grouped.items()):
        for r in sorted(rows,key=lambda r:sha256((salt+r['conversation_id']).encode()).digest())[:n]:
            print(domain,r['conversation_id'],' | '.join(m['text'] for m in r['history']))
if __name__=='__main__':review(sys.argv[1],sys.argv[2],int(sys.argv[3]))
