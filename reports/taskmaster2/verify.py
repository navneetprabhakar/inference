"""Verify frozen role/goal partitions and count distinct text without opening protected cases."""
import json
from hashlib import sha256
from pathlib import Path
import sys
REPORT=Path(__file__).resolve().parent
ROOT=REPORT.parents[1]
sys.path.insert(0,str(ROOT))
from prepare import norm,merged
from taskmaster_teaching import DEST,examples
from tokenizer import load

def main():
    receipt=json.loads((REPORT/'receipt.json').read_text())
    sources={}
    for meta in json.loads((REPORT/"files.json").read_text()):
        name=Path(meta["path"]).name
        for dialog in json.loads((DEST/name).read_bytes()):
            sources[dialog["conversation_id"]]=(meta["path"],dialog)
    provenance=[]
    goals={'train':set(),'internal-dev':set()}
    ids=set()
    vocab={}
    train_assistant={}
    seen={}
    for name,info in receipt['files'].items():
        f=DEST/name
        assert sha256(f.read_bytes()).hexdigest()==info['sha256']
        for line in f.open():
            r=json.loads(line)
            assert r['conversation_id'] not in ids and name==r['usage']+'-'+r['split']+'.jsonl'
            ids.add(r['conversation_id'])
            source_path,source=sources[r["conversation_id"]]
            turns=merged(source)
            refs=[(m["role"],m["text"]) for m in r["history"]]
            start=next(i for i in range(len(turns)) if [(who,t) for who,t,_ in turns[i:i+len(refs)]]==refs)
            end_index=start+len(refs)
            provenance.append(dict(history_sha256=r["history_sha256"],source_path=source_path,conversation_id=r["conversation_id"],
                               first_utterance=turns[start][2],last_utterance=(turns[end_index][2]-1 if end_index<len(turns) else len(source["utterances"])-1)))
            goals[r['split']].add(r['goal_group'])
            assert r['history_sha256']==sha256(json.dumps(r['history'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if r['usage']=='sft':
                assert [m['role'] for m in r['history']]==['user','assistant']*(len(r['history'])//2)
                assert all(m['text'].endswith('?') for m in r['history'][1::2])
            if r['split']=='train':
                for m in r['history']:
                    vocab[norm(m['text'])]=m['text']
                    if m['role']=='assistant' and r['usage']=='sft':
                        train_assistant[norm(m['text'])]=m['text']
            opening=norm(next(m['text'] for m in r['history'] if m['role']=='user'))
            seen.setdefault(opening,set()).add(r['split'])
    assert not goals['train'] & goals['internal-dev']
    assert all(len(s)==1 for s in seen.values())
    tok=load()
    h=examples(1459)
    verification=dict(goal_groups={k:len(v) for k,v in goals.items()},source_conversation_ids=len(ids),
                      unique_train_utterances=len(vocab),unique_assistant_sft_utterances=len(train_assistant),
                      unique_train_token_positions=sum(len(tok.encode(s).ids) for s in vocab.values()),
                      unique_assistant_sft_text_token_positions=sum(len(tok.encode(s).ids) for s in train_assistant.values()),
                      examples_seed1459_sha256=sha256(json.dumps(h,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    index=DEST/"source-offsets.jsonl"
    index.write_text("".join(json.dumps(r,sort_keys=True)+"\n" for r in provenance))
    verification["source_offsets_sha256"]=sha256(index.read_bytes()).hexdigest()
    print(json.dumps(verification,indent=2))
    (REPORT/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
if __name__=='__main__':main()
