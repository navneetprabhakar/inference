"""Longer-context copying probes; v1 preserved. No training corpus changes."""
import collections,csv,hashlib,json,re,sqlite3
from pathlib import Path
from slm.common.tokenizer import BPE
O=Path(__file__).resolve().parent;R=O.parents[2];EXEC=O.parent
MAN=R/'restart/fineweb-salvage-reviewed-v1/accepted-manifest.csv'
EXPECTED='2ad53dc0fc670a7185763f1cfe151e1148933038b8855e55d54a29f84256716d'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rank(label,row):return hashlib.sha256((label+':'+row['family_id']+':'+row['audit_id']).encode()).digest()

def main():
    dest=O/'copy-probes-v2'
    if dest.exists():raise FileExistsError('Preserve existing candidate set')
    assert sha(MAN)==EXPECTED
    tok=BPE.load(EXEC/'tokenizer-8192');rows=list(csv.DictReader(MAN.open()))
    db=sqlite3.connect(f'file:{R}/restart/corpus-audit-v1/audit.sqlite?mode=ro',uri=True)
    cache={};used=set();selected={};pairs={};train_bins=collections.defaultdict(list)
    def load(row):
        key=row['audit_id']
        if key not in cache:
            text=db.execute('SELECT text FROM docs WHERE id=?',(int(key),)).fetchone()[0]
            assert hashlib.sha256(text.encode()).hexdigest()==row['original_text_sha256']
            ids=tok.encode(text);cache[key]=(text,ids)
        return cache[key]
    def base(row):return {k:row[k] for k in ['audit_id','source','split','family_id','original_text_sha256','normalized_sha256']}
    def copy_candidate(row):
        text,ids=load(row)
        if len(ids)<128:return None
        prefix=tok.decode(ids[:64])
        if '\ufffd' in prefix or tok.encode(prefix)!=ids[:64] or not text.startswith(prefix):return None
        tail=text[len(prefix):]
        if prefix[-1].isalnum() and tail and tail[0].isalnum():return None
        return base(row)|{'prefix':prefix,'prefix_token_ids':ids[:64],'expected_next_64_token_ids':ids[64:128],
              'document_content_tokens':len(ids),'prefix_words':len(prefix.split()),'role':'copy_probe_not_added_training'}
    for row in sorted((r for r in rows if r['split']=='train' and r['source']=='TinyStories'),key=lambda r:rank('copy-train-v2',r)):
        candidate=copy_candidate(row)
        if candidate:train_bins[candidate['document_content_tokens']].append(candidate)
    for split,source_split in [('development','development'),('final','test')]:
        eligible=[r for r in rows if r['split']==source_split and r['source']=='TinyStories']
        selected[split]=[];matched=[]
        for row in sorted(eligible,key=lambda r:rank('copy-heldout-v2',r)):
            if row['family_id'] in used:continue
            held=copy_candidate(row)
            if held is None:continue
            candidates=train_bins[held['document_content_tokens']]
            partner=next((x for x in candidates if x['family_id'] not in used and abs(x['prefix_words']-held['prefix_words'])<=2),None)
            if partner is None:continue
            used.update([row['family_id'],partner['family_id']]);pairid=f'{split}:copy:{len(matched):03d}'
            matched.append({'pair_id':pairid,'evaluation_split':split,'training':partner,'heldout':held,'matching':{'source':'TinyStories','prefix_tokens':64,'document_tokens':'exact','maximum_prefix_word_difference':2}})
            if len(matched)==100:break
        assert len(matched)==100
        pairs[split]=matched
    dest.mkdir();files={}
    for split in selected:
        for kind,values in [('copy-pairs',pairs[split])]:
            p=dest/(split+'-'+kind+'.jsonl');p.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in values));files[p.name]=sha(p)
    receipt={'status':'DRAFT_NOT_FROZEN','source_manifest_sha256':sha(MAN),'tokenizer_manifest_sha256':sha(EXEC/'tokenizer-8192/manifest.json'),
      'copy_pairs_per_split':100,'distinct_selected_families':len(used),'files_sha256':files,
      'copy_matching':'64 input content tokens, exact document token length and same source; prefix word count differs by at most two. All 64 reference targets exist.',
      'limitations':['Copying training prefixes intentionally overlap admitted training documents; diagnostic-only exception, never re-added or oversampled.','Heldout copying families are distinct across splits and from training probe families; authored narrative v2 has no source families.','Existing split/family audit preserved; fresh prefix containment/near checks and semantic review still required.','Only the prefix is presented to the model; reference token IDs are evaluator-only.','These are research drafts, not independent human certification or scored model results.']}
    (dest/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
