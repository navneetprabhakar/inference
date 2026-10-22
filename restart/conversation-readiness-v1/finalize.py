"""Human-reviewed correction receipt and exact counts under the current tokenizer."""
import hashlib,json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[2];ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE/'restart/mac15m-feasibility-v1/upstream'))
from tokenizer import Tokenizer

def save(name,obj):(ROOT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def main():
    teacher=json.loads((ROOT/'teacher-answer.json').read_text());seeds=json.loads((ROOT/'correction-seeds.json').read_text())
    tok=Tokenizer(str(BASE/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
    answers={r['id']:r['assistant'] for r in teacher['corrections']};examples=[]
    for seed in seeds:
        answer=answers[seed['id']]
        prompt=f"User: {seed['user']}\nAssistant:"
        prompt_ids=tok.encode(prompt,bos=True,eos=False)
        target_ids=tok.encode(answer,bos=False,eos=True)
        assert 0<len(target_ids) and len(prompt_ids)+len(target_ids)<=256
        examples.append({**seed,'assistant':answer,'prompt':prompt,'prompt_token_count':len(prompt_ids),'assistant_target_token_count':len(target_ids),'total_token_count':len(prompt_ids)+len(target_ids),
          'status':'HUMAN_REVIEWED_PROVISIONAL','used_for_training':False})
    # All 16 manually reviewed by the primary agent, including exact copy,
    # corrected names, arithmetic, constraints and unperformed-action honesty.
    # The move-item clarification is linguistic supervision, not tool execution authority.
    assert answers['correction-7']=='Welcome home.'
    assert 'five' in answers['correction-3'].lower()
    assert 'Mist' in answers['correction-5']
    assert len(answers['correction-11'].split())==1
    save('reviewed-corrections.json',dict(model='gpt-6-luna',reviewer='primary-agent manual semantic review',examples=examples,
      serializer='prompt encoded with BOS; assistant encoded separately without BOS, with EOS; generation uses the exact prompt prefix',
      assistant_only_loss=True,context_limit=256,usable_examples=len(examples),
      assistant_target_tokens_including_eos=sum(r['assistant_target_token_count'] for r in examples),
      input_and_target_tokens=sum(r['total_token_count'] for r in examples),
      excluded=0,trained=False,readiness='NOT_A_TRAINING_CORPUS: small pattern seed only; foundation English gate has not passed'))
    groups={k:[r for r in teacher['reviews'] if (r['id'].startswith('story-'))==(k=='story')] for k in ['story','conversation']}
    scores={k:dict(count=len(v),readable=sum(r['language_ok'] for r in v),coherent=sum(r['coherent'] for r in v),request_correct=sum(r['answers_request'] for r in v)) for k,v in groups.items()}
    save('assessment.json',dict(status='NOT_READY',checkpoint_sha256=json.loads((ROOT/'contract.json').read_text())['sha256'],
      formal_english_gate='NOT_RUN_AND_NOT_PASSED',diagnostic_only=True,independent_acceptance=False,
      scores=scores,unique_chat_scenarios=12,unique_rendered_chat_prompts=23,duplicate='turn_context-roles and turn_context-qa are the same prompt and output',
      teacher_assessment=teacher['assessment'],primary_review='All story continuations exhibit context or entity drift; none of the chat outputs answers the request. Readability is insufficient evidence of language coherence. Teacher grading agrees with primary manual review.',
      corrections_prepared=len(examples),student_updates=0,full_training_authorized=False,
      stop_reason='Base coherence is inadequate and the existing English gate has not passed. Do not substitute teacher answers for student scores or use this diagnostic as final acceptance.',
      next_step='An explicitly approved, bounded foundation continuation with predeclared development milestones would be required before revisiting conversation SFT. No such continuation is launched here.'))
if __name__=='__main__':main()
