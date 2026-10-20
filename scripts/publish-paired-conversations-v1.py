"""Audit actual paired histories/tokens and publish all unedited student replies."""
# Creator: Navneet Prabhakar
import html,json,re
from collections import Counter
from pathlib import Path
from slm.common.tokenizer import BPE,OFFSET,STRUCTURAL
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.inference.greedy import prompt_ids
ROOT=Path('data/balanced-versus-foundation-assessment-v1')
DOC=Path('docs/balanced-versus-foundation-transcripts')

def save(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False,sort_keys=True)+'\n')
def audit():
 p=json.loads((ROOT/'plan.json').read_text());protocol=json.loads(Path(p['protocol']).read_text());done=json.loads((ROOT/'completion.json').read_text())
 if not done['complete'] or done['raw_message_reply_pairs']!=600:raise ValueError('Both actual complete endpoints required')
 if done['plan_sha256']!=sha(ROOT/'plan.json') or sha(ROOT/'plan.json')!=sha('configs/balanced-versus-foundation-assessment-v1.json'):raise ValueError('Frozen paired plan changed')
 for name,h in p['inputs'].items():
  if sha(name)!=h:raise ValueError('Bound paired input changed: '+name)
 bpe=BPE.load(p['tokenizer']);allrows={};reports={}
 for model,binding in p['models'].items():
  folder=ROOT/model;session=json.loads((folder/'session.json').read_text());c=json.loads((folder/'completion.json').read_text());rows=[json.loads(x) for x in (folder/'turns.jsonl').read_text().splitlines()]
  assert c['complete'] and c['turns']==len(rows)==300 and c['turns_sha256']==sha(folder/'turns.jsonl')
  assert session['student']['model_manifest_sha256']==binding['model_manifest_sha256']==sha(Path(binding['path'])/'manifest.json')
  assert session['protocol_sha256']==sha(p['protocol'])
  for i,case in enumerate(protocol['conversations']):
   history=[]
   for turn,request in enumerate(case['turns'],1):
    row=rows[i*3+turn-1];r=row['response'];ids=r['token_ids']
    assert (row['conversation'],row['turn'],row['category'],row['user'],row['success_criterion'])==(case['id'],turn,case['category'],request['user'],request['success_criterion'])
    history.append(dict(role='user',content=row['user']))
    assert row['context_sha256']==digest(history) and r['prompt_tokens']==len(prompt_ids(bpe,history))
    assert 0<len(ids)==r['generated_tokens']<=r['max_new_tokens']==protocol['max_new_tokens']
    assert r['prompt_tokens']+r['max_new_tokens']<=session['student']['architecture']['max_seq_len']
    assert all(type(t) is int and 0<=t<bpe.vocab_size for t in ids)
    if r['stop_reason']=='length':assert len(ids)==r['max_new_tokens'];content=ids
    else:
     assert ids[-1]<OFFSET
     if r['stop_reason'] in ('eos','message_end'):assert ids[-1]==STRUCTURAL[r['stop_reason']]
     else:assert r['stop_reason']=='invalid_structural' and ids[-1] not in (STRUCTURAL['eos'],STRUCTURAL['message_end'])
     content=ids[:-1]
    assert all(t>=OFFSET for t in content) and len(content)==r['content_tokens'] and bpe.decode(content)==r['text']
    history.append(dict(role='assistant',content=r['text']))
  reports[model]=dict(turns=300,conversations=100,distinct_replies=len({r['response']['text'] for r in rows}),stop_reasons=dict(Counter(r['response']['stop_reason'] for r in rows)),generated_tokens=sum(r['response']['generated_tokens'] for r in rows),generation_seconds=sum(r['response']['seconds'] for r in rows),turns_sha256=sha(folder/'turns.jsonl'),model_manifest_sha256=binding['model_manifest_sha256'],session_sha256=sha(folder/'session.json'))
  allrows[model]=rows
 return p,protocol,allrows,reports

def fenced(text):
 longest=max([len(x) for x in re.findall(r'`+',text)]+[0]);fence='`'*max(3,longest+1)
 return fence+'text\n'+text+'\n'+fence

def main():
 p,protocol,rows,reports=audit()
 if DOC.exists():raise FileExistsError('Preserve earlier published transcript')
 DOC.mkdir();parts=[];htmlrows=[]
 for group in range(10):
  first=group*10;last=first+10;body=['# Actual paired conversations '+str(first+1)+'–'+str(last),'','Creator: Navneet Prabhakar','','Unedited actual MLX greedy replies. Each model uses its own prior generated replies. Same visible development suite; no training, teacher or cloud. Direct quality judgments are published separately.','']
  for i,case in enumerate(protocol['conversations'][first:last],first):
   body+=['## Conversation '+str(case['id'])+' — '+case['category'],'']
   for t,request in enumerate(case['turns']):
    f=rows['foundation'][i*3+t]['response'];c=rows['corrected'][i*3+t]['response']
    body+=['### Turn '+str(t+1),'','User: '+request['user'],'','Foundation:',fenced(f['text']),'','Corrected:',fenced(c['text']),'',f"Stops: foundation={f['stop_reason']}; corrected={c['stop_reason']}.",'']
    htmlrows.append('<article data-category="'+html.escape(case['category'])+'"><h2>Conversation '+str(case['id'])+' · Turn '+str(t+1)+' · '+html.escape(case['category'])+'</h2><p><b>User:</b> '+html.escape(request['user'])+'</p><div class="pair"><section><h3>Foundation</h3><pre>'+html.escape(f['text'])+'</pre><small>'+html.escape(f['stop_reason'])+'</small></section><section><h3>Corrected</h3><pre>'+html.escape(c['text'])+'</pre><small>'+html.escape(c['stop_reason'])+'</small></section></div></article>')
  target=DOC/('part-'+str(group+1).zfill(2)+'.md');target.write_text('\n'.join(body));assert target.stat().st_size<100*1024;parts.append(target)
 page='''<!doctype html><meta charset="utf-8"><title>Actual foundation vs corrected responses</title><style>body{font:16px system-ui;background:#f3f5f7;color:#14202e;margin:28px auto;max-width:1400px;padding:0 20px}article{background:white;padding:22px;margin:18px 0;border-radius:12px}h2{font-size:18px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 ui-monospace,monospace}small{color:#526373}input{padding:12px;width:70%;font-size:16px}@media(max-width:700px){.pair{grid-template-columns:1fr}}</style><h1>Foundation vs corrected: all 100 conversations</h1><p>Creator: Navneet Prabhakar</p><p>600 unedited actual student replies · MLX · greedy, 128-token limit · separate actual history per model · no teacher, training or cloud. Visible development comparison, not a fresh held-out benchmark.</p><input id="filter" placeholder="Filter by category or text"><main>'''+''.join(htmlrows)+'''</main><script>document.getElementById('filter').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('article').forEach(a=>a.hidden=!a.textContent.toLowerCase().includes(q))})</script>'''
 (ROOT/'comparison.html').write_text(page)
 index=['# Foundation versus corrected: all actual responses','','Creator: Navneet Prabhakar','','100 three-turn conversations per endpoint; 600 unedited replies. Direct grading is separate from these transcripts. Each endpoint uses its own actual generated history.','']
 for i,path in enumerate(parts):index.append('- [Conversations '+str(i*10+1)+'–'+str(i*10+10)+'](balanced-versus-foundation-transcripts/'+path.name+')')
 Path('docs/balanced-versus-foundation-transcripts.md').write_text('\n'.join(index)+'\n')
 report=dict(creator='Navneet Prabhakar',complete=True,scope='All600raw histories/token decoding and requested protocol integrity; no automated semantic grading',models=reports,paired_plan_sha256=sha(ROOT/'plan.json'),publisher_sha256=sha(__file__),published_files={str(x):sha(x) for x in parts},html_sha256=sha(ROOT/'comparison.html'),model_updates=0,teacher_calls=0,cloud_commands=0)
 save('reports/balanced-versus-foundation-integrity-v1.json',report);print(json.dumps(report,indent=2))

if __name__=='__main__':main()
