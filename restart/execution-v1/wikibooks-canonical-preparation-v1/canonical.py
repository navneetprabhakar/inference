"""Freeze parent-approved canonical candidates from complete identity frame.

Metadata only: no rendering, license relabeling, admission or sampling.
"""
import argparse
import hashlib
import json
import sqlite3
import unicodedata
from collections import Counter,defaultdict
from pathlib import Path

SOURCE_FRAME_SHA='a27a5c6f2fe085e19968bde850fd45ace824e141be45e595037c6278ae5bd1f3'
ARCHIVE_SHA='361fb441fe35d13be56c4eca22a09df6868a663e5d7f3b1ed2a665e332a4d263'

def sha(b):return hashlib.sha256(b).hexdigest()
def file_sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def root(title):return unicodedata.normalize('NFC',title.replace('_',' ')).split('/',1)[0]
def exact_four(r):
    a=r.get('license_original_metadata')
    return isinstance(a,list) and len(a)==1 and a[0].get('identifier')=='CC-BY-SA-4.0' and a[0].get('url')=='https://creativecommons.org/licenses/by-sa/4.0/'
def signature(r):return json.dumps([r.get(k) for k in ['url','title','html_sha256','wikitext_sha256','license_original_metadata']],sort_keys=True,separators=(',',':'))

def resolve_group(rows):
    """Return selected ordinal or None and exact occurrence disposition list."""
    valid=[r for r in rows if type(r.get('revision_id')) is int and r['revision_id']>0]
    maximal=max((r['revision_id'] for r in valid),default=None)
    maxima=[r for r in valid if r['revision_id']==maximal]
    conflict=len({signature(r) for r in maxima})!=1
    eligible_max=[r for r in maxima if not r.get('identity_holds') and exact_four(r)]
    chosen=min((r['source_ordinal'] for r in eligible_max),default=None) if not conflict else None
    dispositions=[]
    for r in rows:
        reasons=[]
        if r.get('identity_holds'):reasons+=['identity_hold:'+str(x) for x in r['identity_holds']]
        if not exact_four(r):reasons.append('captured_license_not_exact_CC_BY_SA_4_0')
        if conflict:reasons.append('maximal_revision_identity_ambiguous_group_hold')
        elif chosen is None:reasons.append('maximal_revision_ineligible_no_older_fallback')
        elif r['source_ordinal']==chosen:reasons.append('selected_unambiguous_maximal_revision')
        elif r.get('revision_id')==maximal:reasons.append('equivalent_maximal_revision_repeat')
        else:reasons.append('superseded_historical_revision')
        dispositions.append({'source_ordinal':r['source_ordinal'],'canonical_source_ordinal':chosen,
                             'selected':r['source_ordinal']==chosen,'maximal_revision':maximal,'reasons':reasons})
    return chosen,dispositions

def freeze(frame,output,expected=SOURCE_FRAME_SHA):
    if file_sha(frame)!=expected:raise ValueError('complete_identity_frame_hash_mismatch')
    output.mkdir(parents=True,exist_ok=False)
    source=sqlite3.connect('file:'+str(frame.resolve())+'?mode=ro',uri=True)
    groups=defaultdict(list);unidentified=[];all_rows=[]
    for ordinal,data in source.execute('select ordinal,data from records order by ordinal'):
        r=json.loads(data);r['source_ordinal']=ordinal;all_rows.append(r)
        if type(r.get('page_id')) is int and r['page_id']>0:groups[r['page_id']].append(r)
        else:unidentified.append(r)
    source.close()
    parents={};edges=[]
    def find(x):
        parents.setdefault(x,x)
        while parents[x]!=x:parents[x]=parents[parents[x]];x=parents[x]
        return x
    def union(a,b):
        a,b=find(a),find(b);parents[max(a,b)]=min(a,b)
    chosen_rows=[];mapping=[]
    for page,rows in sorted(groups.items()):
        # Every historical alias remains evidence, including ineligible rows.
        aliases=[r for r in rows if isinstance(r.get('title'),str) and r['title']]
        for r in aliases:find(root(r['title']))
        if aliases:
            anchor=min(aliases,key=lambda r:r['source_ordinal'])
            for r in aliases:
                if r['source_ordinal']==anchor['source_ordinal']:continue
                if (r.get('title'),r.get('url'))!=(anchor.get('title'),anchor.get('url')):
                    edges.append({'page_id':page,'first_source_ordinal':anchor['source_ordinal'],'other_source_ordinal':r['source_ordinal'],'first_title':anchor['title'],'other_title':r['title'],'first_url':anchor.get('url'),'other_url':r.get('url'),'first_book_root':root(anchor['title']),'other_book_root':root(r['title']),'evidence':'same_page_id_historical_title_URL_alias','provisional_identity_holds_preserved':bool(anchor.get('identity_holds') or r.get('identity_holds'))})
                    union(root(anchor['title']),root(r['title']))
        chosen,dispositions=resolve_group(rows);mapping+=dispositions
        if chosen is not None:chosen_rows.append(next(r for r in rows if r['source_ordinal']==chosen))
    for r in unidentified:
        reasons=['identity_hold:'+str(x) for x in r.get('identity_holds',[])]
        if not exact_four(r):reasons.append('captured_license_not_exact_CC_BY_SA_4_0')
        reasons.append('missing_valid_page_id')
        mapping.append({'source_ordinal':r['source_ordinal'],'canonical_source_ordinal':None,'selected':False,'maximal_revision':None,'reasons':reasons})
    families={x:'wikibooks:family:'+sha(find(x).encode()) for x in sorted(parents)}
    db=sqlite3.connect(output/'canonical.sqlite3');db.execute('pragma journal_mode=DELETE')
    db.execute('create table candidates (source_ordinal integer primary key,page_id integer unique,revision_id integer,family text,data text)')
    db.execute('create table occurrences (source_ordinal integer primary key,canonical_source_ordinal integer,selected integer,data text)')
    db.execute('create table family_edges (ordinal integer primary key,data text)')
    db.execute('create table aliases (source_ordinal integer primary key,page_id integer,title text,url text,book_root text,family text,data text)')
    byord={r['source_ordinal']:r for r in all_rows};why=Counter()
    for m in sorted(mapping,key=lambda m:m['source_ordinal']):
        r=byord[m['source_ordinal']];m.update({'source_frame_sha256':expected,'source_record_sha256':r['record_sha256'],'archive_sha256':r['archive_sha256'],'member_ordinal':r['member_ordinal'],'line':r['line'],'page_id':r.get('page_id'),'revision_id':r.get('revision_id'),'title':r.get('title'),'url':r.get('url'),'license_original_metadata':r.get('license_original_metadata'),'identity_holds':r.get('identity_holds',[]),'training_admitted':False})
        db.execute('insert into occurrences values (?,?,?,?)',(m['source_ordinal'],m['canonical_source_ordinal'],int(m['selected']),json.dumps(m,sort_keys=True)))
        if not m['selected']:
            for reason in m['reasons']:why[reason]+=1
        if isinstance(r.get('title'),str) and r['title']:
            rt=root(r['title']);family=families.get(rt,'wikibooks:family:'+sha(rt.encode()))
            db.execute('insert into aliases values (?,?,?,?,?,?,?)',(r['source_ordinal'],r.get('page_id'),r['title'],r.get('url'),rt,family,json.dumps({'source_record_sha256':r['record_sha256'],'revision_id':r.get('revision_id'),'license_original_metadata':r.get('license_original_metadata'),'identity_holds':r.get('identity_holds',[])},sort_keys=True)))
    for r in sorted(chosen_rows,key=lambda r:r['source_ordinal']):
        rt=root(r['title']);c=dict(r,source_frame_sha256=expected,book_root_title=rt,family_id=families[rt],canonical_rule='highest_unambiguous_maximal_revision_exact_captured4_no_identity_holds_first_equivalent_ordinal',canonical_selection_is_not_admission=True,training_admitted=False)
        db.execute('insert into candidates values (?,?,?,?,?)',(r['source_ordinal'],r['page_id'],r['revision_id'],c['family_id'],json.dumps(c,sort_keys=True)))
    for i,e in enumerate(edges,1):db.execute('insert into family_edges values (?,?)',(i,json.dumps(e,sort_keys=True)))
    db.commit();assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
    counts={'source_occurrences':len(all_rows),'canonical_candidates':len(chosen_rows),'excluded_occurrences':len(all_rows)-len(chosen_rows),'duplicate_page_id_groups':sum(len(v)>1 for v in groups.values()),'historical_alias_occurrences':db.execute('select count(*) from aliases').fetchone()[0],'historical_alias_edges':len(edges),'candidate_families':db.execute('select count(distinct family) from candidates').fetchone()[0]};db.close()
    receipt={'status':'FROZEN_CANONICAL_METADATA_CANDIDATES_NO_RENDERING_NO_ADMISSION','source_frame_sha256':expected,'archive_sha256':ARCHIVE_SHA,'counts':counts,'exclusion_reason_occurrence_counts':dict(why),'canonical_sqlite_sha256':file_sha(output/'canonical.sqlite3'),'code_sha256':file_sha(Path(__file__)),'rule':'All occurrences considered for maximal revision. Ambiguous maximal URL/title/HTML/wikitext/license identity holds whole group. No older fallback when maximum is ineligible. Equivalent eligible maxima keep first ordinal. All historical roots/aliases remain family edges.','new_admitted_documents':0,'new_admitted_tokens':0};(output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt

def main():
    p=argparse.ArgumentParser();p.add_argument('--frame',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();print(json.dumps(freeze(a.frame,a.output),indent=2))

if __name__=='__main__':main()
