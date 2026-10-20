"""Whole paragraph/one original question candidates, official article holdouts intact."""
# Creator: Navneet Prabhakar
import collections,json,re,time
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.data.tokenized import document_tokens
from slm.data.schema import digest
from slm.data.stream_hash import sha
from slm.data.quality_audit import PATTERNS,predict,top_scores,LIMITS
from slm.data.detector_projection import fasttext_line
from slm.data.prose_screen import windows
ROOT=Path('data/grounded-qa-candidates-v1');SOURCE=Path('data/grounded-qa-intake-v1');TOK=Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
def main():
 if ROOT.exists():raise FileExistsError(ROOT)
 ROOT.mkdir();start=time.monotonic();proof=json.loads((SOURCE/'report-v2.json').read_text());bpe=BPE.load(TOK)
 if not proof['complete'] or not proof['all_answer_offsets_reconstructed']:raise ValueError('Complete pinned source intake required')
 evidence=proof['evidence']
 for e in evidence.values():
  if sha(e['path'])!=e['sha256']:raise ValueError('Source evidence changed')
 descriptor=Path('data/language-detector-v4/detector.json');spec=json.loads(descriptor.read_text())
 for key in ('binary','model'):
  if sha(spec[key])!=spec[key+'_sha256']:raise ValueError('Offline detector differs')
 candidates=[];why=collections.Counter();mapping=[]
 risky=re.compile(r'\b(?:sex\w*|porn\w*|suicid\w*|kill\w*|weapon\w*|bomb\w*|murder\w*|diagnos\w*|treatment|dosage|prescri\w*|investment|taxation)\b',re.I)
 with (ROOT/'detector-input.txt').open('x') as out:
  for split,filename in [('train','train-v1.1.json'),('validation','dev-v1.1.json')]:
   body=json.loads((SOURCE/filename).read_text())
   for ai,article in enumerate(body['data']):
    for pi,paragraph in enumerate(article['paragraphs']):
     if time.monotonic()-start>1800:raise TimeoutError('Finite candidate preparation wall')
     context=paragraph['context'];qas=sorted(paragraph['qas'],key=lambda q:digest(['grounded-qa-original-question-v1',q['id']]))
     # Choose before content screening; never fish among answers to obtain a passing paragraph.
     q=qas[0];answer=q['answers'][0];text=context+'\n'+q['question']
     if len(context)>5000 or len(q['question'])>500 or risky.search(text) or any(p.search(text) for p in PATTERNS.values()):why['initial_scope']+=1;continue
     if '\ufffd' in text or not context[answer['answer_start']:answer['answer_start']+len(answer['text'])]==answer['text']:why['encoding_or_span']+=1;continue
     answer_tokens=len(bpe.encode(answer['text']))
     if not 1<=answer_tokens<=32:why['answer_length']+=1;continue
     messages=[dict(role='user',content='Read the passage and answer the question using only the passage. Give only the answer.\n\nPassage:\n'+context+'\n\nQuestion: '+q['question']),dict(role='assistant',content=answer['text'])]
     result,reason=document_tokens(bpe,dict(messages=messages),'sft',768)
     if reason:why[reason]+=1;continue
     parts=windows(text)
     if not parts:why['no_language_window']+=1;continue
     row=dict(id=q['id'],source='SQuAD-1.1',source_revision=proof['revision'],official_split=split,article=article['title'],article_index=ai,paragraph_index=pi,source_paragraph_sha256=digest(context),paragraph_family=digest(['SQuAD-1.1',context]),article_family=digest(['SQuAD-1.1',article['title']]),context=context,question=q['question'],answer=answer['text'],answer_start=answer['answer_start'],messages=messages,prediction_positions=len(result[0])-1,supervised_positions=sum(result[1][1:]),content_category='unreviewed')
     idx=len(candidates);candidates.append(row)
     for part in parts:mapping.append(idx);out.write(fasttext_line(part['text'])+'\n')
 predict(Path(spec['binary']),Path(spec['model']),ROOT/'detector-input.txt',ROOT/'detector-output.txt',{**LIMITS,'detector_seconds':120,'max_detector_output_bytes':32*1024**2})
 scores=[top_scores(l) for l in (ROOT/'detector-output.txt').open()]
 if len(scores)!=len(mapping):raise ValueError('Complete language coverage differs')
 bad={i for i,s in zip(mapping,scores) if not s or s[0]['language']!='en' or s[0]['score']<.8};kept=[r for i,r in enumerate(candidates) if i not in bad]
 with (ROOT/'candidates.jsonl').open('x') as f:
  for r in kept:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
 report=dict(creator='Navneet Prabhakar',complete=True,training_approved=False,selection='One original question/first original answer per full paragraph selected by fixed hash before screening. No truncated passage, fabricated paraphrase or synthetic answer. Full official dev source remains protected even if candidate screen rejects a row.',candidates=len(kept),by_split=dict(collections.Counter(r['official_split'] for r in kept)),unique_train_articles=len({r['article'] for r in kept if r['official_split']=='train'}),reasons=dict(why),language_window_rejections=len(bad),language_windows=len(mapping),source_intake_sha256=sha(SOURCE/'report-v2.json'),candidate_sha256=sha(ROOT/'candidates.jsonl'),tokenizer_sha256=sha(TOK/'manifest.json'),script_sha256=sha(__file__),max_context=768,max_answer_content_tokens=32,min_answer_content_tokens=1,elapsed_seconds=time.monotonic()-start,scope='Source span integrity/English signals only, not semantic answer quality, article/near family admission or conversation correctness. Shared paragraph is never replayed through its several question variants.')
 (ROOT/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
