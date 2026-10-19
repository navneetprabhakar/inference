"""Check raw interview evidence before publishing delegated expert scores."""
# Creator: Navneet Prabhakar
import argparse
import fcntl
import json
import math
from pathlib import Path
from slm.common.tokenizer import BPE,STRUCTURAL,OFFSET
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.eval.iteration_two_interview import protocol_checked,terminal_binding
from slm.eval import iteration_two_interview
from slm.inference.greedy import prompt_ids

RESPONSE={'text','token_ids','stop_reason','prompt_tokens','generated_tokens','content_tokens','ttft_seconds','seconds','max_new_tokens'}


def validate_and_score(rows,protocol,bpe,grades,max_context=2048):
    protocol_checked(protocol)
    if len(rows)!=protocol['max_turns']:raise ValueError('Complete eight-turn interview required')
    history=[]
    for i,row in enumerate(rows,1):
        if set(row)!={'turn','user','context_sha256','response'} or type(row['turn']) is not int or row['turn']!=i or not isinstance(row['user'],str) or not row['user'].strip():raise ValueError('Actual complete interview turn required')
        if i==1 and row['user']!=protocol['initial_prompt']:raise ValueError('Interview initial prompt differs')
        history.append(dict(role='user',content=row['user']));wanted=len(prompt_ids(bpe,history));r=row['response']
        if digest(history)!=row['context_sha256'] or not isinstance(r,dict) or set(r)!=RESPONSE:raise ValueError('Raw interview history/response differs')
        raw=r['token_ids'];budget=protocol['max_new_tokens']
        if (not isinstance(raw,list) or not 1<=len(raw)<=budget or any(type(t) is not int or not 0<=t<bpe.vocab_size for t in raw)
            or any(t<OFFSET for t in raw[:-1]) or any(type(r[k]) is not int for k in ('prompt_tokens','generated_tokens','content_tokens','max_new_tokens'))
            or r['generated_tokens']!=len(raw) or r['max_new_tokens']!=budget or r['prompt_tokens']!=wanted or wanted+budget>max_context):raise ValueError('Interview token counts/budget differ')
        last=raw[-1]
        reason='eos' if last==STRUCTURAL['eos'] else 'message_end' if last==STRUCTURAL['message_end'] else 'invalid_structural' if last<OFFSET else 'length'
        content=[t for t in raw if t>=OFFSET]
        if (r['stop_reason']!=reason or (reason=='length' and len(raw)!=budget)
            or r['content_tokens']!=len(content) or r['text']!=bpe.decode(content)):raise ValueError('Published reply differs from raw tokens/stop rule')
        if any(type(r[k]) not in (int,float) or not math.isfinite(r[k]) or r[k]<0 for k in ('ttft_seconds','seconds')) or r['ttft_seconds']>r['seconds']:raise ValueError('Invalid observed generation timing')
        history.append(dict(role='assistant',content=r['text']))
    expected={'creator','review_mode','human_attestation','full_transcript_read','dimensions','turn_judgments','limitations'}
    if (set(grades)!=expected or grades['creator']!='Navneet Prabhakar' or grades['review_mode']!='delegated_expert'
        or grades['human_attestation'] is not False or grades['full_transcript_read'] is not True
        or set(grades['dimensions'])!=set(protocol['assessment_dimensions']) or not isinstance(grades['limitations'],str) or not grades['limitations'].strip()):raise ValueError('Complete direct delegated grading required')
    total=0
    for grade in grades['dimensions'].values():
        if (set(grade)!={'score','evidence_turns','reason'} or type(grade['score']) is not int or not 0<=grade['score']<=4
            or not isinstance(grade['reason'],str) or not grade['reason'].strip() or not isinstance(grade['evidence_turns'],list)
            or not grade['evidence_turns'] or any(type(n) is not int or not 1<=n<=len(rows) for n in grade['evidence_turns'])):raise ValueError('Dimension score/evidence differs')
        total+=grade['score']
    if len(grades['turn_judgments'])!=len(rows):raise ValueError('Every actual turn needs direct judgment')
    for i,judgment in enumerate(grades['turn_judgments'],1):
        if (set(judgment)!={'turn','reason','task_succeeded'} or type(judgment['turn']) is not int or judgment['turn']!=i
            or type(judgment['task_succeeded']) is not bool or not isinstance(judgment['reason'],str) or not judgment['reason'].strip()):raise ValueError('Per-turn direct evidence differs')
    return dict(score_out_of_20=total,normalized_score_out_of_100=total*5,
        successful_tasks=sum(g['task_succeeded'] for g in grades['turn_judgments']),turns=len(rows),grades=grades,
        transcript=rows,human_attestation=False,training_approved=False,
        scope='Direct expert judgments on one adaptive development conversation. Structural/token checks do not certify the judgments; the score is not population accuracy, readiness or tool capability.')


def publish(root,session,protocol_file,score_file,selection_file,freeze_file,grades_file,output):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    binding=terminal_binding(root,score_file,selection_file,freeze_file)
    architecture=json.loads((Path(binding['model_path'])/'config.json').read_text())['architecture']
    session=Path(session);header=json.loads((session/'session.json').read_text());completion=json.loads((session/'completion.json').read_text())
    protocol=json.loads(Path(protocol_file).read_text());rows=[json.loads(line) for line in (session/'turns.jsonl').read_text().splitlines()]
    if (header['terminal']!=binding or header['interviewer_sha256']!=sha(iteration_two_interview.__file__)
        or header['protocol_sha256']!=sha(protocol_file) or header['protocol_digest']!=digest(protocol)
        or header['human_attestation'] is not False or header['training_approved'] is not False
        or header['review_mode']!='delegated_expert' or header['student']['model_manifest_sha256']!=binding['model_manifest_sha256']
        or header['student']['tokenizer_manifest_sha256']!=binding['tokenizer_manifest_sha256']
        or header['student']['architecture']!=architecture or header['student']['embedding_implementation']!=binding['embedding_implementation']
        or header['student']['decoding']!=protocol['decoding'] or completion['turns']!=protocol['max_turns']
        or completion['session_sha256']!=sha(session/'session.json') or completion['turns_sha256']!=sha(session/'turns.jsonl')
        or completion['assessment_pending'] is not True or completion['human_attestation'] is not False):raise ValueError('Bound completed interview required')
    grades=json.loads(Path(grades_file).read_text())
    result=validate_and_score(rows,protocol,BPE.load(binding['tokenizer_path']),grades,architecture['max_seq_len'])
    result.update(creator='Navneet Prabhakar',protocol_sha256=sha(protocol_file),grades_sha256=sha(grades_file),
        session_sha256=sha(session/'session.json'),transcript_sha256=sha(session/'turns.jsonl'),completion_sha256=sha(session/'completion.json'),
        assessment_code_sha256=sha(__file__),student=header['student'],terminal=binding)
    with output.open('x') as out:out.write(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser()
    for name in ('root','session','protocol','score','selection','freeze','grades','output'):parser.add_argument('--'+name,required=True)
    a=parser.parse_args()
    with (Path(a.root)/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        result=publish(a.root,a.session,a.protocol,a.score,a.selection,a.freeze,a.grades,a.output)
        print(json.dumps({k:result[k] for k in ('score_out_of_20','normalized_score_out_of_100','successful_tasks','turns')},indent=2))


if __name__=='__main__':main()
