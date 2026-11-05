"""Bounded current-auth Codex teacher authoring; never admits data or trains."""
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOAL = ROOT / 'runs/eight-hour-improvement-v1'
RUN = ROOT / 'runs/eight-hour-teacher-expansion-v2'
DATA = ROOT / 'data/eight-hour-teacher-expansion-v2'
DEADLINE = 1793672065


def save(state, **extra):
    path = RUN / 'status.json'
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps({'state': state, 'pid': os.getpid(), 'updated_unix': time.time(),
                               'deadline_unix': DEADLINE, 'target_records': 200,
                               'admission': 'QUARANTINED_PENDING_PARENT_REVIEW', **extra}, indent=2) + '\n')
    tmp.replace(path)


def stop_requested():
    return time.time() >= DEADLINE or (GOAL/'STOP').exists() or (RUN/'STOP').exists()


def main():
    RUN.mkdir(exist_ok=True); DATA.mkdir(exist_ok=True)
    with (RUN/'.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        completed = 0
        seen = set()
        for batch in range(1, 9):
            target = DATA / f'batch-{batch:03d}.jsonl'
            if stop_requested():
                save('stopped_before_batch', completed_records=completed); return
            if not target.exists():
                prior_prompts = []
                prior_sources = [ROOT/'data/eight-hour-teacher-reviewed-v2/records.jsonl', ROOT/'data/eight-hour-teacher-expansion-reviewed-v1/records.jsonl'] + sorted(DATA.glob('batch-*.jsonl'))
                for prior_source in prior_sources:
                    for line in prior_source.read_text().splitlines():
                        if line.strip():
                            row = json.loads(line)
                            prior_prompts.append(next(m['content'] for m in row['messages'] if m['role'] == 'user').split(' I would like a direct answer I can use immediately,')[0])
                prior_path = RUN / f'batch-{batch:03d}-prior-prompts.json'
                prior_path.write_text(json.dumps(prior_prompts, ensure_ascii=False) + '\n')
                prompt = f'''You are the authorized current-auth GPT teacher for a local student model. AUTHOR exactly 25 original, diverse English dialogues and save them to {target.relative_to(ROOT)}. This is the only data file you may create. You may read this prompt and the extracted first-user prompts in {prior_path.relative_to(ROOT)} to avoid repeated scenarios. Read no other corpus files; prior source dialogue bodies are unnecessary. Do not read evaluation data, reports, model outputs, checkpoints, private files or old missions. No training, model inference, subagents, network tools, paid API calls or package installation. Do not change any other file or delete STOPs. Check current time and runs/eight-hour-improvement-v1/STOP first; absolute deadline Unix {DEADLINE}.

Each record must have id "expansion2-{batch:03d}-NN" with NN 01..25; family describing its actual content; messages with alternating user/assistant roles; provenance with source_model exactly "gpt-5.6-terra current-auth Codex CLI", authoring_batch "{batch:03d}", substantive_correctness_review containing a specific short self-check, independent_human_review false. This is author self-review, never independent review.

Each dialogue has 2 or 3 user turns and matching assistant turns. Use the length the conversation needs, usually 40–120 words total. There is NO minimum length. NEVER append a generic filler sentence, repeated instruction, or boilerplate to meet a word count. Keep concise substantive answers. Follow-ups must depend naturally on the preceding conversation; include some explicit user corrections or changed constraints and update the answer correctly. Cover varied ordinary conversations. Avoid making most records household chores: include basic language learning, everyday scientific explanations with stable simple facts, social conversation, creative collaboration, hobbies, and interpretation of user-supplied information. Distinguish an example from a fact about the user. Never claim to operate a device or access a record. Specifically cover: interpreting facts supplied in the prompt, clear explanations, practical planning, everyday choices, conversational repair, writing help and asking for genuinely missing details. Most facts needed for a correct answer should be supplied by the user. Avoid medical/legal/financial advice, current facts, invented personal facts, generic refusal filler, decorative metaphors, unsupported promises and external actions. Do not make every record a test question. Vary voice, setting, answer length and conversational structure. Do not manufacture diversity by merely substituting names/numbers into templates. No tool examples: root supplies verified fixture data.

Avoid already overused topics: packing backpacks, bus-departure subtraction, metal-versus-wood spoons, plant watering, rice-and-peas recipes, send-slides deadlines, freezer frost, yellowing book pages, receipt retention, birthday greetings. Read only prior first-user prompts to avoid overlap. Do not reference training, evaluation, rubrics or model capabilities inside dialogues.

Author the 25 literal dialogues, save them with Python stdlib in a single bounded write, then check JSON, count, unique IDs, alternating roles, continuity, factual support and each changed constraint. Correct your new batch if needed before ending. Do not overwrite an existing batch file; report it instead. End the invocation after saving this batch; do not spawn a continuation or plan the whole corpus. Parent will tokenize, replay checks, screen leakage and perform a separate assistant review before any admission. Return only saved path and count.'''
                (RUN/f'batch-{batch:03d}-prompt.txt').write_text(prompt)
                with (RUN/f'batch-{batch:03d}-events.jsonl').open('a') as out, (RUN/f'batch-{batch:03d}-stderr.log').open('a') as err:
                    child = subprocess.Popen(['codex', 'exec', '--model', 'gpt-5.6-terra', '--sandbox', 'danger-full-access', '--json',
                                              '--output-last-message', str(RUN/f'batch-{batch:03d}-final.txt'), '-'],
                                             stdin=subprocess.PIPE, stdout=out, stderr=err, text=True, cwd=ROOT, start_new_session=True)
                    child.stdin.write(prompt); child.stdin.close()
                    started = time.time()
                    save('authoring', batch=batch, cli_pid=child.pid, completed_records=completed)
                    while child.poll() is None:
                        if stop_requested() or time.time() - started >= 600:
                            os.killpg(child.pid, signal.SIGTERM)
                            try:
                                child.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                os.killpg(child.pid, signal.SIGKILL)
                            save('stopped_deadline_STOP_or_batch_time_cap', completed_records=completed, batch=batch)
                            return
                        time.sleep(2)
                    if child.returncode != 0:
                        save('cli_failed_preserved_outputs', batch=batch, completed_records=completed, exit_code=child.returncode)
                        return
            records = [json.loads(s) for s in target.read_text().splitlines() if s.strip()]
            assert len(records) == 25
            for row in records:
                assert row['id'] not in seen
                seen.add(row['id'])
                assert row['provenance']['source_model'] == 'gpt-5.6-terra current-auth Codex CLI'
                assert len(row['messages']) in (4, 6)
                assert [m['role'] for m in row['messages']] == ['user', 'assistant'] * (len(row['messages'])//2)
            receipt = {'records': len(records), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                       'source': 'current-auth Codex CLI gpt-5.6-terra', 'independent_human_review': False,
                       'admission': 'QUARANTINED_PENDING_PARENT_REVIEW'}
            (DATA/f'batch-{batch:03d}.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
            completed += len(records)
            save('batch_saved_quarantined', batch=batch, completed_records=completed)
        save('authoring_complete_quarantined', completed_records=completed)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        RUN.mkdir(exist_ok=True)
        save('infrastructure_failure', error=repr(exc))
        raise
