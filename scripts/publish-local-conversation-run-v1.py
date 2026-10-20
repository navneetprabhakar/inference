"""Reconstruct every actual history/token and publish600 raw local SFT replies."""
# Creator: Navneet Prabhakar
import html,json,re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from slm.common.tokenizer import BPE,OFFSET,STRUCTURAL
from slm.inference.greedy import prompt_ids
from slm.data.schema import digest
from slm.data.stream_hash import sha
ROOT=Path('data/local-conversation-run-v1');DOC=Path('docs/local-conversation-run-v1-transcripts')
def save(p,v):Path(p).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def fenced(text):
 f='`'*max(3,1+max([len(x) for x in re.findall(r'`+',text)]+[0]));return f+'text\n'+text+'\n'+f
class Pres(HTMLParser):
 def __init__(self):super().__init__();self.values=[];self.active=False
 def handle_starttag(self,tag,attrs):
  if tag=='pre':self.active=True;self.values.append('')
 def handle_endtag(self,tag):
  if tag=='pre':self.active=False
 def handle_data(self,data):
  if self.active:self.values[-1]+=data

def main():
 if DOC.exists():raise FileExistsError('Preserve prior publication')
 done=json.loads((ROOT/'completion.json').read_text());p=json.loads(Path('configs/local-conversation-run-v1.json').read_text())
 if not done['complete'] or done['raw_student_pairs']!=600:raise ValueError('All actual assessments must complete')
 bpe=BPE.load(p['tokenizer']);allrows={};reports={}
 for name,protocol in p['generation_protocols'].items():
  pp=json.loads(Path(protocol).read_text());rows=[json.loads(x) for x in (ROOT/name/'turns.jsonl').open()];session=json.loads((ROOT/name/'session.json').read_text());c=json.loads((ROOT/name/'completion.json').read_text())
  assert c['complete'] and c['actual_turns']==len(rows)==300 and sha(ROOT/name/'turns.jsonl')==c['turns_sha256']
  assert session['student']['model_manifest_sha256']==sha(ROOT/'terminal/model/manifest.json') and session['protocol_sha256']==sha(protocol)
  for i,case in enumerate(pp['conversations']):
   history=[]
   for turn,request in enumerate(case['turns'],1):
    row=rows[i*3+turn-1];r=row['response'];ids=r['token_ids'];history.append(dict(role='user',content=request['user']))
    assert (row['conversation'],row['turn'],row['user'],row['category'],row['success_criterion'])==(case['id'],turn,request['user'],case['category'],request['success_criterion'])
    assert row['context_sha256']==digest(history) and r['prompt_tokens']==len(prompt_ids(bpe,history))
    assert 0<len(ids)==r['generated_tokens']<=r['max_new_tokens']==pp['max_new_tokens']
    assert r['prompt_tokens']+r['max_new_tokens']<=session['student']['architecture']['max_seq_len']
    assert all(type(t) is int and 0<=t<bpe.vocab_size for t in ids)
    if r['stop_reason']=='length':assert len(ids)==r['max_new_tokens'];content=ids
    else:
     assert ids[-1]<OFFSET;content=ids[:-1]
     if r['stop_reason'] in ('eos','message_end'):assert ids[-1]==STRUCTURAL[r['stop_reason']]
     else:assert r['stop_reason']=='invalid_structural' and ids[-1] not in (STRUCTURAL['eos'],STRUCTURAL['message_end'])
    assert all(t>=OFFSET for t in content) and len(content)==r['content_tokens'] and bpe.decode(content)==r['text']
    history.append(dict(role='assistant',content=r['text']))
  def repeated(t):
   words=re.findall(r'\w+',t.casefold());return max(Counter(tuple(words[j:j+8]) for j in range(len(words)-7)).values(),default=0)>=3
  reports[name]=dict(conversations=100,turns=300,distinct_replies=len({r['response']['text'] for r in rows}),stop_reasons=dict(Counter(r['response']['stop_reason'] for r in rows)),repeated_eightgram_replies=sum(repeated(r['response']['text']) for r in rows),generated_tokens=sum(r['response']['generated_tokens'] for r in rows),turns_sha256=sha(ROOT/name/'turns.jsonl'),model_manifest_sha256=sha(ROOT/'terminal/model/manifest.json'),protocol_sha256=sha(protocol));allrows[name]=rows
 DOC.mkdir();parts=[];sections=[];expected=[]
 for name,rows in allrows.items():
  for part in range(10):
   body=['# Actual local SFT '+name+' conversations '+str(part*10+1)+'–'+str(part*10+10),'','Creator: Navneet Prabhakar','','Raw unedited student replies with actual student history. No teacher/retrieval/repair/tools. Quality judgments are separate. Source-heldout development includes reasoning/maths and differs from the simpler visible regression protocol.','']
   for row in rows[part*30:(part+1)*30]:
    response=row['response']['text'];body+=['## Conversation '+str(row['conversation'])+' · Turn '+str(row['turn']),'','User:',fenced(row['user']),'','Student:',fenced(response),'','Stop: '+row['response']['stop_reason']+'.','']
    sections.append('<article><h2>'+html.escape(name)+' · Conversation '+str(row['conversation'])+' · Turn '+str(row['turn'])+'</h2><p>'+html.escape(row['user'])+'</p><pre>'+html.escape(response)+'</pre></article>');expected.append(response)
   path=DOC/(name+'-'+str(part+1).zfill(2)+'.md');path.write_text('\n'.join(body))
   assert path.stat().st_size<100*1024
   # Parse our variable-backtick fenced publication exactly, including leading/trailing newlines.
   text=path.read_text();actual=[]
   cursor=0
   while match:=re.search(r'(?m)^(`{3,})text\n',text[cursor:]):
    start=cursor+match.end();fence=match.group(1);end=text.index('\n'+fence,start);actual.append(text[start:end]);cursor=end+1+len(fence)
   want=[v for row in rows[part*30:(part+1)*30] for v in (row['user'],row['response']['text'])]
   assert actual==want;parts.append(path)
 page='<!doctype html><meta charset="utf-8"><title>Actual local SFT replies</title><style>body{font:16px system-ui;max-width:1100px;margin:auto;padding:24px}article{padding:24px;border-bottom:1px solid #ddd}pre,p{white-space:pre-wrap;overflow-wrap:anywhere}input{padding:12px;width:80%}</style><h1>Actual local SFT:600 replies</h1><p>Creator: Navneet Prabhakar</p><input id="q" placeholder="Filter protocol, question or response">'+''.join(sections)+'<script>q.oninput=()=>document.querySelectorAll("article").forEach(a=>a.hidden=!a.textContent.toLowerCase().includes(q.value.toLowerCase()))</script>'
 (ROOT/'transcripts.html').write_text(page);parser=Pres();parser.feed(page);assert parser.values==expected
 index=['# Local conversation SFT: all actual replies','','Creator: Navneet Prabhakar','','Two separate100-conversation, three-turn protocols;600actual replies. [Training/data/limitations](local-conversation-recovery.md). Neither set is a random population benchmark. Repeated development is not fresh final testing.','']
 index+=['- ['+part.stem+'](local-conversation-run-v1-transcripts/'+part.name+')' for part in parts]
 Path('docs/local-conversation-run-v1-transcripts.md').write_text('\n'.join(index)+'\n')
 save('reports/local-conversation-run-v1-integrity.json',dict(creator='Navneet Prabhakar',complete=True,passed=True,actual_histories_reconstructed=600,token_decodes_reconstructed=600,published_raw_replies=600,published_raw_user_messages=600,html_reply_roundtrip=600,markdown_user_reply_roundtrips=1200,protocols=reports,training_plan_sha256=sha('configs/local-conversation-run-v1.json'),source_model_unchanged_sha256=sha(Path(p['source_model'])/'manifest.json'),human_attestation=False,semantic_grading_separate=True))
 print(json.dumps(reports,indent=2))
if __name__=='__main__':main()
