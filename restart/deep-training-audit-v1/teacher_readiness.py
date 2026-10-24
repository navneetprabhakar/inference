"""Read-only exact-format eligibility count for the existing teacher training split."""
import json,importlib.util
from pathlib import Path
from sentencepiece import SentencePieceProcessor
R=Path(__file__).resolve().parent;P=R.parents[1];path=P/'restart/sol-conversation-data-1000-v1/private/train-candidates.jsonl'
spec=importlib.util.spec_from_file_location('deep_teacher_readiness',P/'restart/sol-conversation-sft-diagnostic-v1/runner.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s);sp=SentencePieceProcessor(model_file=str(s.TOK))
rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()];fit=[];over=[];invalid=[]
for row in rows:
 try:
  ids,m,spans=s.serialize(sp,row['messages'])
  for turn,span in enumerate(spans):assert s.prompt(sp,row['messages'][:2*turn+1])==list(ids[:span['start']])
  record=dict(sequence_tokens=len(ids),assistant_targets=int(m.sum()),assistant_content_tokens=sum(len(sp.encode(x['content'])) for x in row['messages'] if x['role']=='assistant'))
  (fit if len(ids)<=257 else over).append(record)
 except Exception as ex:invalid.append(type(ex).__name__)
result=dict(source_sha256=s.sha(path),screened_train_candidates=len(rows),current_native_serialization_fit=len(fit),over_context=len(over),invalid_structure=len(invalid),fit_assistant_content_tokens=sum(x['assistant_content_tokens'] for x in fit),fit_assistant_eos_targets=sum(x['assistant_targets'] for x in fit),training_admitted=0,records_with_unknown_tokens=sum(any(sp.unk_id() in sp.encode(m['content']) for m in row['messages']) for row in rows),limitation='Serialization/context readiness only. Screened candidates need quality/leakage admission; no current-checkpoint training on this bank. No dev/test payload read or admitted.')
(R/'teacher-bank-readiness.json').write_text(json.dumps(result,indent=2)+'\n')
