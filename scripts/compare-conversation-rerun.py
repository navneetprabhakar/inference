"""Compare a fresh actual run with the unchanged development baseline."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from slm.data.schema import digest
from slm.data.stream_hash import sha

OLD=Path('data/current-model-100-conversations-v1');NEW=Path('data/current-model-100-conversations-rerun-v1')

def rows(p):return [json.loads(line) for line in (p/'turns.jsonl').read_text().splitlines()]

def main():
    if not (NEW/'rerun-receipt.json').exists():raise ValueError('Fresh actual generation is not terminal')
    old=rows(OLD);new=rows(NEW)
    if len(old)!=len(new) or len(new)!=300:raise ValueError('Complete300-turn comparison required')
    receipt=json.loads((NEW/'rerun-receipt.json').read_text());plan=json.loads(Path('configs/current-model-conversation-rerun-v1.json').read_text())
    if not receipt['complete'] or receipt['wrapper_plan_sha256']!=sha('configs/current-model-conversation-rerun-v1.json'):raise ValueError('Rerun receipt differs')
    for p,h in plan['input_bindings'].items():
        if sha(p)!=h:raise ValueError('Pinned rerun input changed')
    if receipt['completion_sha256']!=sha(NEW/'completion.json'):raise ValueError('Completion receipt changed')
    differences=[]
    for a,b in zip(old,new,strict=True):
        for k in ('conversation','category','turn','user','context_sha256'):
            if a[k]!=b[k]:differences.append((b['conversation'],b['turn'],k))
        for k in ('text','token_ids','stop_reason','prompt_tokens','generated_tokens','content_tokens','max_new_tokens'):
            if a['response'][k]!=b['response'][k]:differences.append((b['conversation'],b['turn'],k))
    if differences:raise ValueError('Fresh outputs differ; prior score transfer refused, direct differential grading required')
    # Reuse the frozen full-history/token-decoding checker, changing only its
    # input directory. Its original readable transcript must match fresh text.
    spec=importlib.util.spec_from_file_location('frozen_conversation_integrity','scripts/check-current-conversations.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.ROOT=NEW
    integrity=module.check();integrity.update(kind='actual-fresh-rerun-history-integrity-v1',
        checker_wrapper_sha256=sha(__file__),readable_transcript_note='Existing readable baseline transcript also exactly matches every fresh rerun reply; no substitute generation used.')
    target=Path('reports/current-model-conversation-rerun-integrity.json');target.write_text(json.dumps(integrity,indent=2,sort_keys=True)+'\n')
    prior=json.loads(Path('reports/current-model-100-conversations-assessment.json').read_text())
    judgments=[]
    for i,old_judgment in enumerate(prior['judgments']):
        j=deepcopy(old_judgment);j['recorded_turns_sha256']=digest(new[i*3:i*3+3]);j['original_judgment_sha256']=digest(old_judgment);judgments.append(j)
    result=dict(creator='Navneet Prabhakar',kind='actual-current-model-rerun-comparison-v1',complete=True,
        conversations=100,turns=300,matching_contexts=300,matching_generated_token_sequences=300,matching_texts=300,
        model_manifest_sha256=prior['terminal']['model_manifest_sha256'],
        successful_conversations=prior['successful_conversations'],successful_turns=prior['successful_turns'],mean_score_out_of_100=prior['mean_score_out_of_100'],
        dimension_means=prior['dimension_means'],categories=prior['categories'],judgments=judgments,
        prior_assessment_sha256=sha('reports/current-model-100-conversations-assessment.json'),integrity_sha256=sha(target),
        prior_turns_sha256=sha(OLD/'turns.jsonl'),fresh_turns_sha256=sha(NEW/'turns.jsonl'),fresh_receipt_sha256=sha(NEW/'rerun-receipt.json'),
        scoring_method='Prior direct judgments mapped to freshly generated rows only after all300 requests/contexts/texts/token sequences/stops/caps match exactly. This is a reproducibility assessment, not a fresh independent blind grading or new unseen benchmark.',
        human_attestation=False,production_accepted=False,training_approved=False,model_updates=0,teacher_calls=0,cloud_spend=0,
        scope='User-requested fresh actual MLX generation with unchanged weights and100conversation protocol. No capability improvement in this repeated development suite. Recent corpus preparation is data work, not new student training. No causal claim about a new training iteration.')
    Path('reports/current-model-conversation-rerun-assessment.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('judgments','categories')},indent=2))

if __name__=='__main__':main()
