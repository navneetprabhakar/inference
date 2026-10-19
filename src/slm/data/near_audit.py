"""Read-only source coverage, feature-index and near-pair checks."""
# Creator: Navneet Prabhakar
import hashlib
import heapq
import json
from pathlib import Path
from slm.data.curation import shingles
from slm.data.prose_screen import word_key
from slm.data.schema import digest


def require_terminal(root):
    path=Path(root)/'report.json'
    if not path.is_file():raise ValueError('Near grouping is not terminal; database audit refused before opening')
    value=json.loads(path.read_text())
    if value.get('complete') is not True:raise ValueError('Complete near report required')
    return value


def verify_source_mappings(source,near):
    records=fields=excluded=0
    for sid,data in source.execute('SELECT sid,data FROM records ORDER BY sid'):
        row=json.loads(data);records+=1;expected={}
        for facet,text in row['texts'].items():
            normalized=word_key(text)
            if len(normalized)>=16 and len(normalized.split())>=4:expected[facet]=text
            else:excluded+=1
        actual=dict(near.execute('''SELECT f.facet,r.data FROM facet_sources f JOIN records r ON r.sid=f.sid
WHERE f.source_sid=? ORDER BY f.facet''',(sid,)))
        if actual!=expected:raise ValueError('Complete original source-facet coverage differs')
        fields+=len(expected)
    if near.execute('SELECT count(*) FROM facet_sources').fetchone()[0]!=fields:raise ValueError('Unexpected source mappings')
    return dict(records=records,facet_references=fields,excluded_short_facets=excluded)


def verify_feature_index(near,*,sample_size=128):
    sample=[];facets=0;expected_features=0
    for sid,text,fingerprint in near.execute('SELECT sid,data,exact FROM records ORDER BY sid'):
        if digest(text)!=fingerprint:raise ValueError('Stored original facet identity differs')
        facets+=1
        score=int(hashlib.sha256(('near-posting-audit-20261019:'+str(sid)).encode()).hexdigest(),16)
        value=(-score,sid,text)
        if len(sample)<sample_size:heapq.heappush(sample,value)
        elif sample and value>sample[0]:heapq.heapreplace(sample,value)
    checked=0
    query='''SELECT c.sid,c.kind,c.n,(SELECT count(*) FROM features f INDEXED BY by_record WHERE f.sid=c.sid AND f.kind=c.kind)
FROM counts c ORDER BY c.sid,c.kind'''
    for sid,kind,n,actual in near.execute(query):
        if kind!=0 or n!=actual or n<1:raise ValueError('Full feature occurrence count differs')
        checked+=1;expected_features+=n
    if checked!=facets:raise ValueError('Every unique facet must have complete feature counts')
    # Both indexes order by shingle ID, allowing bounded-memory frequency audit.
    cursor=iter(near.execute('SELECT fid,count(*) FROM features WHERE kind=0 GROUP BY fid ORDER BY fid'))
    for fid,n,prompt_count in near.execute('SELECT fid,n_full,n_prompt FROM dictionary ORDER BY fid'):
        if next(cursor,None)!=(fid,n) or prompt_count!=0:raise ValueError('Global full-feature frequencies differ')
    if next(cursor,None) is not None:raise ValueError('Feature missing dictionary identity')
    for _,sid,text in sample:
        expected={bytes.fromhex(digest(v)) for v in shingles(text)}
        actual={r[0] for r in near.execute('''SELECT d.feat FROM features f JOIN dictionary d ON d.fid=f.fid
WHERE f.sid=? AND f.kind=0''',(sid,))}
        if expected!=actual:raise ValueError('Sampled complete reference shingles differ')
    return dict(unique_raw_facets=facets,full_feature_occurrences=expected_features,sampled_facet_posting_sets=len(sample))


def verify_prefix_counts(near):
    checked=0
    query='''SELECT c.sid,c.n,(SELECT count(*) FROM prefixes p WHERE p.sid=c.sid AND p.kind=0)
FROM counts c WHERE c.kind=0 ORDER BY c.sid'''
    for sid,n,actual in near.execute(query):
        if actual!=n-(17*n+19)//20+1:raise ValueError('Complete prefix count differs')
        checked+=1
    return checked


def verify_near_pairs(near):
    pairs=0
    for a,b in near.execute('SELECT a,b FROM near_pairs ORDER BY a,b'):
        if a>=b:raise ValueError('Canonical distinct facet pair required')
        rows=near.execute('SELECT sid,data FROM records WHERE sid IN (?,?) ORDER BY sid',(a,b)).fetchall()
        if len(rows)!=2:raise ValueError('Near pair endpoint missing')
        x,y=(shingles(r[1]) for r in rows)
        if 20*len(x&y)<17*len(x|y):raise ValueError('Reported near pair fails full reference Jaccard threshold')
        pairs+=1
    return pairs
