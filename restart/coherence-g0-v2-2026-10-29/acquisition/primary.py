"""Primary API question/accepted-answer capture with per-component attribution."""
import hashlib,json,time,urllib.request,urllib.parse,gzip,html
from pathlib import Path
P=Path(__file__).resolve().parent
SITES=['lifehacks','interpersonal','workplace','crafts','cooking']
POLICY={'sites':SITES,'pages_per_site':12,'page_size':100,'question_creation_min':1525305600,'sort':'votes descending','answer_selection':'accepted answer only; include question context','required_component_license':'CC BY-SA 4.0','required_component_owner':['display_name','link'],'max_requests':180,'max_response_bytes':2000000,'max_total_bytes':120000000,'max_retries_per_request':1,'comments_included':False,'archive_metadata_reused':False,'admitted_tokens':0}
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def main():
    policy=P/'primary-policy.json'
    if policy.exists():assert json.loads(policy.read_text())==POLICY
    else:save(policy,POLICY)
    receipts=P/'primary-receipts.json';rows=json.loads(receipts.read_text()) if receipts.exists() else []
    out=P/'private/primary';out.mkdir(exist_ok=True)
    def fetch(key,endpoint,params):
        dest=out/(key+'.json')
        if dest.exists():
            raw=dest.read_bytes();assert any(r.get('key')==key and r.get('sha256')==hashlib.sha256(raw).hexdigest() for r in rows)
            return json.loads(raw)
        for attempt in range(2):
            assert len(rows)<POLICY['max_requests'] and sum(r.get('bytes',r.get('reserved_bytes',0)) for r in rows)+POLICY['max_response_bytes']+1<=POLICY['max_total_bytes']
            url='https://api.stackexchange.com/2.3/'+endpoint+'?'+urllib.parse.urlencode(params)
            receipt={'key':key,'url':url,'status':'STARTED','attempt':attempt+1,'reserved_bytes':POLICY['max_response_bytes']+1};rows.append(receipt);save(receipts,rows)
            try:
                with urllib.request.urlopen(url,timeout=40) as response:raw=response.read(POLICY['max_response_bytes']+1)
                receipt['bytes']=len(raw);assert len(raw)<=POLICY['max_response_bytes']
                data=json.loads(raw)
                if data.get('error_id'):raise RuntimeError(str(data))
                dest.write_bytes(raw);receipt.update(status='COMPLETE',sha256=hashlib.sha256(raw).hexdigest(),quota_remaining=data.get('quota_remaining'),items=len(data['items']));save(receipts,rows)
                if data.get('backoff'):
                    remaining=data['backoff']
                    while remaining>0:
                        pause=min(remaining,30);time.sleep(pause);remaining-=pause
                time.sleep(.3)
                return data
            except Exception as e:
                receipt.update(status='FAILED',error=str(e));save(receipts,rows)
                if attempt:raise
                time.sleep(2)
    for site in SITES:
        questions=[]
        for page in range(1,POLICY['pages_per_site']+1):
            d=fetch(f'{site}-questions-{page}','questions',dict(site=site,pagesize=100,page=page,sort='votes',order='desc',fromdate=POLICY['question_creation_min'],filter='withbody'))
            questions.extend(d['items'])
            if not d.get('has_more'):break
        selected=[q for q in questions if q.get('content_license')=='CC BY-SA 4.0' and q.get('accepted_answer_id') and all(q.get('owner',{}).get(k) for k in POLICY['required_component_owner'])]
        ids=sorted(set(q['accepted_answer_id'] for q in selected));answers={}
        for start in range(0,len(ids),100):
            batch=ids[start:start+100];d=fetch(f'{site}-answers-{start//100}','answers/'+';'.join(map(str,batch)),dict(site=site,pagesize=100,filter='withbody'))
            answers.update({a['answer_id']:a for a in d['items']})
        pairs=[{'site':site,'question':q,'answer':answers[q['accepted_answer_id']]} for q in selected if q['accepted_answer_id'] in answers and answers[q['accepted_answer_id']].get('question_id')==q['question_id'] and answers[q['accepted_answer_id']].get('content_license')=='CC BY-SA 4.0' and all(answers[q['accepted_answer_id']].get('owner',{}).get(k) for k in POLICY['required_component_owner'])]
        with gzip.open(out/(site+'-pairs.jsonl.gz'),'wt') as f:
            for pair in pairs:f.write(json.dumps(pair)+'\n')
        print(site,'questions',len(questions),'attributed_cc4_pairs',len(pairs),flush=True)
    print('Primary capture complete, candidates only',flush=True)
if __name__=='__main__':main()
