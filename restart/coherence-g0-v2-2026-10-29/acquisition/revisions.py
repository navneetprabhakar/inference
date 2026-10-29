"""Resolve contributor history for selected primary components, within shared cap."""
import hashlib,json,time,urllib.request,urllib.parse,collections
from pathlib import Path
P=Path(__file__).resolve().parent
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def main():
    policy=json.loads((P/'primary-policy.json').read_text());receipt=P/'primary-receipts.json';log=json.loads(receipt.read_text());selected=json.loads((P/'private/selected-primary.json').read_text())
    fid=json.loads((P.parent/'reviews/evidence/repair-filter.json').read_text())['items'][0]['filter']
    out=P/'private/revisions';out.mkdir(exist_ok=True);index={};stop=None
    for site in sorted({r['site'] for r in selected}):
        ids=sorted({x for r in selected if r['site']==site for x in [r['question_id'],r['answer_id']]})
        for start in range(0,len(ids),100):
            batch=ids[start:start+100];events=[];complete=False
            for page in range(1,21):
                key=f'{site}-revisions-{start//100}-{page}';dest=out/(key+'.json')
                if dest.exists():
                    raw=dest.read_bytes();assert any(r.get('key')==key and r.get('sha256')==hashlib.sha256(raw).hexdigest() for r in log);d=json.loads(raw)
                else:
                    used=sum(r.get('bytes',r.get('reserved_bytes',0)) for r in log)
                    if len(log)>=policy['max_requests'] or used+policy['max_response_bytes']+1>policy['max_total_bytes']:
                        stop='PRIMARY_ACQUISITION_CAP';break
                    url='https://api.stackexchange.com/2.3/posts/'+';'.join(map(str,batch))+'/revisions?'+urllib.parse.urlencode(dict(site=site,pagesize=100,page=page,filter=fid))
                    row=dict(key=key,url=url,status='STARTED',reserved_bytes=policy['max_response_bytes']+1);log.append(row);save(receipt,log)
                    try:
                        with urllib.request.urlopen(url,timeout=40) as response:raw=response.read(policy['max_response_bytes']+1)
                        row['bytes']=len(raw);assert len(raw)<=policy['max_response_bytes'];d=json.loads(raw);assert 'error_id' not in d,d
                        dest.write_bytes(raw);row.update(status='COMPLETE',sha256=hashlib.sha256(raw).hexdigest(),items=len(d['items']),quota_remaining=d.get('quota_remaining'));save(receipt,log)
                        remaining=d.get('backoff',0)
                        while remaining>0:pause=min(remaining,30);time.sleep(pause);remaining-=pause
                        time.sleep(.3)
                    except BaseException as e:
                        row.update(status='FAILED',error=str(e));save(receipt,log);stop='REVISION_FETCH_FAILED';break
                events.extend(d['items'])
                if not d.get('has_more'):complete=True;break
            if complete:
                for post in batch:index[site+':'+str(post)]=[e for e in events if e['post_id']==post]
            else:stop=stop or 'REVISION_PAGINATION_INCOMPLETE'
            save(P/'private/revision-index.json',index)
            print(site,start,'complete',complete,'events',len(events),'requests',len(log),flush=True)
            if stop:break
        if stop:break
    valid=[];holds=collections.Counter()
    for r in selected:
        histories=[index.get(r['site']+':'+str(x)) for x in [r['question_id'],r['answer_id']]]
        if not all(histories):holds['missing_complete_history']+=1;continue
        content=[[e for e in h if e.get('revision_type')=='single_user'] for h in histories]
        if not all(content):holds['no_content_revision']+=1;continue
        if any(e.get('content_license')!='CC BY-SA 4.0' or not e.get('user',{}).get('display_name') for h in content for e in h):holds['unresolved_revision_license_or_contributor']+=1;continue
        latest=[max([e for e in h if 'body' in e],key=lambda e:e['creation_date'],default={}) for h in content]
        if any('body' not in e or hashlib.sha256(e['body'].encode()).hexdigest()!=r['component_body_sha256'][i] for i,e in enumerate(latest)):holds['current_body_revision_mismatch']+=1;continue
        valid.append({**r,'status':'PROVENANCE_CANDIDATE_NOT_SEMANTICALLY_ADMITTED','revision_contributors':[[{'revision_guid':e['revision_guid'],'revision_number':e.get('revision_number'),'user':e['user'],'license':e['content_license']} for e in h] for h in content]})
    save(P/'private/provenance-candidates.json',valid)
    result=dict(status='CAPTURE_COMPLETE' if not stop else stop,candidate_documents=len(valid),candidate_tokens=sum(r['tokens'] for r in valid),holds=dict(holds),shared_requests=len(log),admitted_tokens=0)
    save(P/'revision-result.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
