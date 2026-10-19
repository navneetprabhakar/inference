"""Run a frozen 100-conversation development assessment on the latest trained model."""
# Creator: Navneet Prabhakar
import fcntl
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.eval.fitting_control import ROOT, conversation_binding
from slm.inference.greedy import GreedyModel

OUT = Path('data/current-model-100-conversations-v1')
PLAN = Path('configs/current-model-100-conversations-v1.json')


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + '\n')


def main():
    plan = json.loads(PLAN.read_text())
    cases = plan['conversations']
    if (len(cases) != 100 or len({x['id'] for x in cases}) != 100
            or len({x['turns'][0]['user'] for x in cases}) != 100
            or any(len(x['turns']) != 3 for x in cases)):
        raise ValueError('Exactly 100 distinct three-turn conversations required')
    if OUT.exists():
        raise FileExistsError('Retain existing attempt; no automatic overwrite or replay')
    with (ROOT / 'execution.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        binding = conversation_binding()
        if binding != plan['terminal']:
            raise ValueError('Frozen current checkpoint binding differs')
        OUT.mkdir()
        save(OUT / 'plan.json', plan)
        model = GreedyModel(binding['model_path'], binding['tokenizer_path'], 'mlx', 'default',
            expected_tokenizer_hash=binding['tokenizer_manifest_sha256'],
            embedding_implementation=binding['embedding_implementation'])
        if model.identity['model_manifest_sha256'] != binding['model_manifest_sha256']:
            raise ValueError('Loaded checkpoint differs')
        save(OUT / 'session.json', dict(creator='Navneet Prabhakar',
            created_at_utc=datetime.now(timezone.utc).isoformat(), terminal=binding,
            student=model.identity, runner_sha256=sha(__file__), plan_sha256=sha(PLAN),
            training_approved=False, human_attestation=False, teacher_calls=0))
        try:
            with (OUT / 'turns.jsonl').open('x') as stream:
                for case in cases:
                    history = []
                    for turn, request in enumerate(case['turns'], 1):
                        history.append(dict(role='user', content=request['user']))
                        response = model.generate(history, plan['max_new_tokens'])
                        row = dict(conversation=case['id'], category=case['category'], turn=turn,
                            user=request['user'], context_sha256=digest(history), response=response)
                        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
                        stream.flush()
                        os.fsync(stream.fileno())
                        history.append(dict(role='assistant', content=response['text']))
                    print(json.dumps(dict(completed=case['id'], category=case['category'])), flush=True)
            if binding != conversation_binding() or sha(PLAN) != sha(OUT / 'plan.json'):
                raise ValueError('Checkpoint or protocol changed during execution')
            save(OUT / 'completion.json', dict(creator='Navneet Prabhakar', conversations=100,
                turns=300, complete=True, assessment_pending=True,
                session_sha256=sha(OUT / 'session.json'), turns_sha256=sha(OUT / 'turns.jsonl'),
                model_updates=0, teacher_calls=0, cloud_resources_created=0))
        except BaseException as error:
            save(OUT / 'failure.json', dict(complete=False, error_type=type(error).__name__,
                message=str(error)[:2000], automatic_replay_authorized=False))
            raise


if __name__ == '__main__':
    main()
