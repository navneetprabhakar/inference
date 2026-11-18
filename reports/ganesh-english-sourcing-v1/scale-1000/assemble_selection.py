"""Assemble only reviewed candidates. Never edits legacy/frozen input or training weights."""
import argparse,collections,hashlib,importlib.util,json,pathlib
P=pathlib.Path(__file__).resolve().parent;ROOT=P.parents[2]
s=importlib.util.spec_from_file_location('v',P/'verify_selection.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
def readrows(p):return [json.loads(l) for l in p.read_text().splitlines()]
def pin_receipt(path):
 content=path.read_bytes();key=hashlib.sha256(content).hexdigest();out=P/'receipts'/f'{key}.json';out.parent.mkdir(exist_ok=True)
 if out.exists():assert out.read_bytes()==content
 else:out.write_bytes(content)
 return {'path':str(out.relative_to(ROOT)),'sha256':key}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--a',required=True);ap.add_argument('--b',required=True);ap.add_argument('--a-review',required=True);ap.add_argument('--b-review',required=True);args=ap.parse_args()
 baseline=ROOT/'runs/ganesh-english-sourcing-v1/reviewed-candidates.jsonl';assert v.sha(baseline)==json.loads((P/'baseline-310.json').read_text())['payload_sha256']
 receipt=json.loads((P/'worker-c/selection-receipt.json').read_text());eligible={e['group']:e for e in receipt['entries'] if e['decision']=='accept'};annotations={e['group']:e for e in receipt['annotation_decisions']}
 legacyref=pin_receipt(P/'worker-c/selection-receipt.json');rows=[];sources={};memory_entries=[]
 for row in readrows(baseline):
  if row['group'] not in eligible:continue
  v.verify_legacy(row,receipt);row['fresh_selection_receipt']=legacyref
  original_annotation=row.get('recall_probe');annotation=annotations.get(row['group']);row['recall_probe']=None;row['memory_probe_credit']=bool(annotation and annotation['valid'] and annotation['dialogue_selected'])
  if annotation:
   assert annotation['messages_sha256']==v.digest(row['messages'])
   row['memory_review_receipt']={'path':annotation['review_path'],'sha256':annotation['review_sha256']}
   assert v.sha(ROOT/annotation['review_path'])==annotation['review_sha256']
   if row['memory_probe_credit']:row['recall_probe']={'support_turn':annotation['latest_support_turn'],'probe_turn':annotation['probe_turn'],'focus':annotation['narrow_focus']}
   else:row['memory_qualification_reason']=annotation['decision_rationale']
  memory_entries.append({'group':row['group'],'messages_sha256':v.digest(row['messages']),'credit':row['memory_probe_credit'],'recall_probe':row['recall_probe'],'original_generated_annotation':annotation.get('original_annotation') if annotation else original_annotation,'reason':annotation['decision_rationale'] if annotation else 'No credited delayed-memory annotation','source_receipts':[legacyref]})
  rows.append(row)
 memory_path=P/'legacy-memory-evidence.json';memory_path.write_text(json.dumps({'entries':memory_entries},indent=2)+'\n');memory_ref=pin_receipt(memory_path)
 for row in rows:
  row['memory_evidence_receipt']=memory_ref;v.verify_memory(row,ROOT)
 sources['legacy_retained']=len(rows)
 inputs=[('root',P/'root/final-accepted.jsonl',P/'root/final-content-review.json'),('worker-a',pathlib.Path(args.a),pathlib.Path(args.a_review)),('worker-b',pathlib.Path(args.b),pathlib.Path(args.b_review)),('worker-c',P/'worker-c/replacements/final-selected.jsonl',P/'worker-c/replacements/final-content-review.json')]
 for name,path,manual in inputs:
  ref=pin_receipt(manual);new=readrows(path)
  for row in new:
   row['full_content_review_receipt']=ref;v.verify_new(row);v.verify_full_content(row)
   v.verify_memory(row,ROOT);row.setdefault('source','original_synthetic_codex_cli');row.setdefault('provenance',{'kind':'original_synthetic','generator':'codex exec','requested_model':'gpt-6.1-terra'})
   rows.append(row)
  sources[name]=len(new)
 assert len(rows)>=1000
 assert len({r['group'] for r in rows})==len(rows)
 normalized=set();tok=v.RustBPETokenizer.from_directory(str(ROOT/'runs/ownbase-v2-data/tokenizer'))
 for r in rows:
  r['id']=v.digest(r['messages']);r['partition']='train_candidate';r['training_admitted']=False;r['independent_release_review']=False;r['data_intent']='english_curriculum_candidate';r['reply_budget']=256
  whole=' '.join(v.norm(m['content']) for m in r['messages']);assert whole not in normalized;normalized.add(whole)
  r['encoding']=[]
  for enabled in (False,True):
   policies=[{'permit_calls':enabled,'allowed_names':['calculate','convert'] if enabled else []}]*(len(r['messages'])//2)
   encoded=v.encode_conversation(tok,r['messages'],policies=policies,context=2048)
   r['encoding'].append({'tools_enabled':enabled,'tokens':len(encoded['ids']),'assistant_targets':sum(encoded['mask'])})
  if r['memory_probe_credit']:
   q=r['recall_probe'];assert 1<=q['support_turn']<q['probe_turn']<=len(r['messages'])//2 and q['probe_turn']-q['support_turn']-1>=2
 stats=v.native(rows)
 out=ROOT/'runs/ganesh-english-sourcing-v1/scale-1000/reviewed-1000-v1.jsonl';content=''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows)
 if out.exists():assert out.read_text()==content,'Refusing silent replacement of selected corpus'
 else:out.write_text(content)
 reply_texts=[v.norm(m['content']) for r in rows for m in r['messages'] if m['role']=='assistant']
 stats.update(payload=str(out.relative_to(ROOT)),payload_sha256=v.sha(out),source_counts=sources,family_sessions=dict(collections.Counter(r['family'] for r in rows)),unique_normalized_assistant_texts=len(set(reply_texts)),repeat_assistant_text_occurrences=len(reply_texts)-len(set(reply_texts)),reviewed_memory_probes=sum(r['memory_probe_credit'] for r in rows),memory_family_labels=sum(r['family']=='memory' for r in rows),training_admitted=False,model_quality_evaluated=False,production_ready=False)
 (P/'selection-manifest.json').write_text(json.dumps(stats,indent=2)+'\n');print(json.dumps(stats,indent=2))
if __name__=='__main__':main()
