"""Prospective extraction/domain filter, before fresh semantic sampling."""
import collections,gzip,hashlib,html,json,re,sys
from html.parser import HTMLParser
from pathlib import Path
import sentencepiece as spm
P=Path(__file__).resolve().parent
ROOT=P.parents[2]
class Prose(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag in ['p','li','br','h1','h2','h3']:self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ['p','li','h1','h2','h3']:self.parts.append('\n')
    def handle_data(self,data):self.parts.append(data)
def clean(body):
    p=Prose();p.feed(body);return '\n'.join(line.strip() for line in ''.join(p.parts).splitlines() if line.strip())
def main():
    sp=spm.SentencePieceProcessor(model_file=str(ROOT/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
    policy={'source_unit':'primary question plus accepted answer, explicit speaker labels; no comments','min_tokens':150,'max_tokens':4096,'hold_html_regex':'<(?:img|pre|code|blockquote)\\b','hold_title_regex':r'\b(?:legal|lawyer|lawsuit|laws|salary|paycheck|tax|visa|passport|immigration|medical|diagnos\w*|medication|depress\w*|suicid\w*|anxiety|allerg\w*|pregnan\w*|disease|sick|vaccin\w*|therapy|abuse|harassment|discriminat\w*|firearm|gun|electrical|electricity|mains|mold|mould|food safety|safe to eat|poison\w*)\b','hold_dependency_regex':r'\b(?:see (?:the )?(?:picture|image|photo|video)|shown (?:below|above|in)|as (?:pictured|shown)|attached (?:image|photo)|this (?:picture|image|photo|video)|other answers?|comments? (?:above|below)|according to (?:this|the) (?:article|link)|read (?:this|the) (?:article|link))\b','domain':'everyday','admission':'Requires complete contributor evidence, whole-family split, exact/near-duplicate audit and fresh semantic sample; accepted status is not correctness certification.'}
    (P/'selection-policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    rows=[];counts=collections.Counter()
    for f in sorted((P/'private/primary').glob('*-pairs.jsonl.gz')):
        for line in gzip.open(f,'rt'):
            r=json.loads(line);q,a=r['question'],r['answer'];counts['captured_pairs']+=1
            assert a['question_id']==q['question_id'] and a['answer_id']==q['accepted_answer_id']
            body=q['body']+'\n'+a['body'];title=html.unescape(q['title']);text='Question: '+title+'\n'+clean(q['body'])+'\n\nAccepted answer:\n'+clean(a['body'])
            reason=None
            if re.search(policy['hold_html_regex'],body,re.I):reason='media_code_or_third_party_quote'
            elif re.search(policy['hold_title_regex'],title,re.I):reason='specialist_or_high_stakes_title'
            elif re.search(policy['hold_dependency_regex'],text,re.I):reason='external_or_omitted_component_dependency'
            ids=sp.encode(text);n=len(ids)
            if reason is None and not 150<=n<=4096:reason='length'
            if reason:counts[reason]+=1;continue
            h=hashlib.sha256(text.encode()).hexdigest();rows.append(dict(h=h,text=text,tokens=n,domain='everyday',family=r['site']+':question:'+str(q['question_id']),site=r['site'],question_id=q['question_id'],answer_id=a['answer_id'],title=title,component_owners=[q['owner'],a['owner']],component_license=[q['content_license'],a['content_license']],source_urls=[q['link'],'https://'+r['site']+'.stackexchange.com/a/'+str(a['answer_id'])],component_body_sha256=[hashlib.sha256(x['body'].encode()).hexdigest() for x in [q,a]],transformation='HTML tags removed; paragraph/list boundaries retained; explicit Q/A labels added',status='AWAITING_REVISION_PROVENANCE'))
    (P/'private/selected-primary.json').write_text(json.dumps(rows,indent=2)+'\n')
    result=dict(status='CANDIDATE_NOT_ADMITTED',counts=dict(counts),candidate_documents=len(rows),candidate_tokens=sum(r['tokens'] for r in rows),tokens_by_site={s:sum(r['tokens'] for r in rows if r['site']==s) for s in sorted({r['site'] for r in rows})},admitted_tokens=0)
    (P/'selection-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
