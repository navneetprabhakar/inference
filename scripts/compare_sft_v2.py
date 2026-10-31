"""Compare completed frozen evaluations without generating or training anything."""
import json,html,collections
from pathlib import Path
from sft_common import ROOT
from evaluate_sft_v3 import evaluate_case,summarize
OUT=ROOT/'reports/sft-v3';names=['100m-lr1e-5','100m-lr3e-5'];reports={};outputs={};diagnostics={};test={r['id']:r for r in map(json.loads,(ROOT/'data/sft-v2/test.jsonl').read_text().splitlines())}
for n in names:
 p=ROOT/f'reports/sft-v2/{n}/final';assert json.loads((p/'completed.json').read_text())['complete'];reports[n]=json.loads((p/'metrics.json').read_text());outputs[n]={r['id']:r for r in json.loads((p/'generations.json').read_text())}
 # Offline diagnostics preserve the original early-stop protocol; do not fabricate missing rollout steps.
 counts=collections.Counter();args=collections.defaultdict(collections.Counter)
 for r in outputs[n].values():
  if r['kind'] in ['single','chain']:
   from sft_common import parse_call
   gold=test[r['id']]['calls'];exact_prefix=True
   for i,c in enumerate(gold):
    if not exact_prefix or i>=len(r['generations']):break
    counts[f'step_{i+1}_reached']+=1
    try:pred=parse_call(r['generations'][i]['output'])
    except (ValueError,TypeError):exact_prefix=False;continue
    for k,v in c['arguments'].items():args[k]['cases']+=1;args[k]['correct']+=isinstance(pred.get('arguments'),dict) and pred['arguments'].get(k)==v
    exact_prefix=pred==c;counts[f'step_{i+1}_exact']+=exact_prefix
   if r['kind']=='single' and r['call_exact']:counts['single_exact_calls']+=1;counts['single_correct_answers_after_exact_calls']+=r['success']
 diagnostics[n]={'observed_counts':dict(counts),'argument_accuracy_on_parseable_reached_calls':{k:dict(v) for k,v in args.items()},'limitation':'V2 stopped after wrong calls; later steps are unobserved, not newly evaluated.'}
rows=[]
for label,fn in [('Grounded exact /100',lambda d:d['metrics']['grounded']['successes']),('Single schema-valid /143',lambda d:round(d['metrics']['single']['raw_schema_valid_fraction']*143)),('Single exact calls /143',lambda d:round(d['metrics']['single']['exact_call_sequence_fraction']*143)),('Single full success /143',lambda d:d['metrics']['single']['successes']),('Full chains /100',lambda d:d['metrics']['chain']['successes']),('Clarification exact /100',lambda d:d['metrics']['clarify']['successes']),('No-tool abstention /68',lambda d:round(d['metrics']['none']['tool_abstention_fraction']*68)),('Error response exact /45',lambda d:d['metrics']['error']['successes']),('Chat repetition %',lambda d:round(d['metrics']['chat']['mean_repeated_4gram_fraction']*100,2)),('Chat EOS %',lambda d:round(d['metrics']['chat']['eos_fraction']*100,2)),('FineWeb perplexity',lambda d:round(d['language_retention']['fineweb_validation']['perplexity'],2)),('TinyStories perplexity',lambda d:round(d['language_retention']['tinystories_unseen_shard']['perplexity'],2))]:rows.append([label,*[fn(reports[n]) for n in names]])
paired={}
for kind in ['grounded','single','chain','clarify','error']:
 ids=[i for i,r in outputs[names[0]].items() if r['kind']==kind];paired[kind]=dict(collections.Counter('both_correct' if outputs[names[0]][i]['success'] and outputs[names[1]][i]['success'] else 'lr1_only' if outputs[names[0]][i]['success'] else 'lr3_only' if outputs[names[1]][i]['success'] else 'both_wrong' for i in ids))
examples=[]
for kind in ['single','chain','clarify','grounded','chat']:
 ids=[i for i,r in outputs[names[0]].items() if r['kind']==kind]
 for i in ids[:2]:examples.append({'id':i,'kind':kind,'prompt':outputs[names[0]][i]['prompt'],'reference':outputs[names[0]][i]['reference'],**{n:[g['output'] for g in outputs[n][i]['generations']] for n in names}})
result={'status':'both 100M arms fully evaluated; both 200M arms unstarted and blocked','table':rows,'paired_outcomes':paired,'diagnostics':diagnostics,'examples':examples,'source_reports':{n:str(ROOT/f'reports/sft-v2/{n}/final/metrics.json') for n in names},'recommendation':'Keep LR3 as tool-repair candidate, LR1 as conservative retention/grounding fallback. Neither dominates; no production-ready or four-way-winner claim.'}
(OUT/'comparison.json').write_text(json.dumps(result,indent=2))
body='<!doctype html><meta charset="utf-8"><title>Completed SFT comparison</title><style>body{font:16px/1.6 system-ui;max-width:1000px;margin:40px auto;padding:20px}table{border-collapse:collapse}td,th{border:1px solid #bbb;padding:9px}pre{white-space:pre-wrap;background:#eee;padding:14px}</style><h1>Completed 100M-base SFT comparison</h1><p>Both models trained exactly 5M input slots and were evaluated on the same 756 cases using greedy decoding, repetition penalty 1.2. Both 200M-base arms remain unstarted. No new training was run.</p><table><tr><th>Metric</th><th>LR 1e-5</th><th>LR 3e-5</th></tr>'
body+=''.join('<tr>'+''.join('<td>'+html.escape(str(c))+'</td>' for c in r)+'</tr>' for r in rows)+'</table><p>'+result['recommendation']+'</p><p>LR3 improves complete single-tool tasks fivefold (5 to 25), but clarification, grounding, stopping and language retention regress. Canonical matching is deliberately strict; chat correctness is still pending blind review. Synthetic cases are correlated, so paired counts are descriptive, not independent-sample significance claims.</p><h2>Paired outcomes</h2><pre>'+html.escape(json.dumps(paired,indent=2))+'</pre><h2>Actual outputs</h2><p>First two cases per category, fixed before inspecting the answer; no selection for success.</p>'
for e in examples:body+='<pre>'+html.escape(json.dumps(e,indent=2))+'</pre>'
(OUT/'COMPARISON.html').write_text(body);print(json.dumps(rows))
