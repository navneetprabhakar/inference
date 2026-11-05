"""Render existing explicit judgments and raw model outputs; never assigns scores."""
import argparse,hashlib,json
from pathlib import Path

def main(a):
 d=Path(a.evaluation_dir);rawpath=d/'raw-outputs.json';raw=json.loads(rawpath.read_text());report=json.loads((d/'report.json').read_text());review=json.loads((d/'assistant-semantic-review.json').read_text())
 assert review['raw_outputs_sha256']==hashlib.sha256(rawpath.read_bytes()).hexdigest()
 assert review['checkpoint_sha256']==report['checkpoint_sha256']
 assert review['evaluation_sha256']==report['evaluation_sha256']
 assert review['decoding']==report['decoding']
 byid={c['id']:c for c in review['cases']};assert len(byid)==len(raw) and set(byid)=={r['id'] for r in raw}
 whole=sum(c['conversation_pass'] for c in byid.values());turns=sum(sum(c['turn_passes']) for c in byid.values());totalturns=sum(len(r['turns']) for r in raw)
 assert whole==review['fully_correct_conversations'] and turns==review['fully_correct_turns']
 toolrows=[r for r in raw if r['tool_mode']];toolpasses=sum(byid[r['id']]['conversation_pass'] for r in toolrows)
 assert toolpasses==review['tool_full_successes']
 probe='training_corpus_probe' in review.get('kind','')
 text=f"# {'Training-corpus diagnostic — NOT held-out accuracy' if probe else report['split'].title()+' evaluation'} — actual student conversations\n\n"
 if probe:
  text+='These prompts come from a training corpus. Per-checkpoint committed exposure is recorded in training-probe-exposure.json. This result is not a selection metric or evidence of generalization.\n\n'
  text+=f"Verified exposure in this training stage: {review['verified_stage_seen_cases']}/{len(raw)} cases; {review['verified_stage_seen_whole_passes']} complete passes among those cases. Zero stage exposure does not rule out earlier lineage exposure.\n\n"
 text+=f"- Fully correct conversations: **{whole}/{len(raw)} ({100*whole/len(raw):.1f}%)**.\n- Correct turns: **{turns}/{totalturns} ({100*turns/totalturns:.1f}%)**.\n- Complete tool conversations: **{toolpasses}/{len(toolrows)}**.\n- Review: assistant per-case judgments, not independent human review.\n- Checkpoint: `{report['checkpoint']}`.\n- Checkpoint SHA-256: `{report['checkpoint_sha256']}`.\n- Raw-output SHA-256: `{review['raw_outputs_sha256']}`.\n- Decoding: `{json.dumps(report['decoding'])}`.\n"
 if report.get('retrieval'):text+='- This is retrieval-assisted student inference; it is not the unassisted model.\n'
 text+='\nA conversation passes only when all substantive turns meet the frozen criteria. Tool validity alone is insufficient. All replies below are copied verbatim from the saved raw outputs.\n'
 for r in raw:
  c=byid[r['id']];assert len(c['turn_passes'])==len(r['turns'])
  text+=f"\n## {r['id']} — {'PASS' if c['conversation_pass'] else 'FAIL'}\n\nReview evidence: {c['specific_reason']}\n"
  for n,t in enumerate(r['turns']):
   text+=f"\n### Turn {n+1} — {'PASS' if c['turn_passes'][n] else 'FAIL'}\n\n**User**\n\n{t['user']}\n\n**Student**\n\n```text\n{t['student_reply']['output']}\n```\n"
   if t.get('tool_events'):text+='\n**Fixture trace**\n\n```json\n'+json.dumps(t['tool_events'],indent=2,ensure_ascii=False)+'\n```\n'
   if t.get('post_tool_student_reply'):text+='\n**Student after fixture**\n\n```text\n'+t['post_tool_student_reply']['output']+'\n```\n'
   if t['student_reply'].get('retrieved_demonstration'):text+='\nRetrieved example: `'+str(t['student_reply']['retrieved_demonstration'].get('id'))+'`.\n'
 output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(text)
 print(json.dumps({'output':str(output),'conversations':len(raw),'whole_passes':whole,'turn_passes':turns}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--evaluation-dir',required=True);p.add_argument('--output',required=True);main(p.parse_args())
