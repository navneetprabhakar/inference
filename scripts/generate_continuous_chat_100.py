#!/usr/bin/env python3
"""Generate a single, resumable 100-exchange student-model conversation.

This is host orchestration only.  The prompt plan is authored here; every
assistant reply is emitted once by the frozen local student and then retained
verbatim.  It does not train, update weights, call a network service, or invoke
another CLI.
"""
import argparse
import hashlib
import json
import os
import shutil
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "continuous-chat-100-v1"
RAW = OUT / "raw-records.jsonl"
PLAN = OUT / "prompt-plan.json"
RESULT = OUT / "result.json"
CONVERSATION = OUT / "CONVERSATION.md"
CHECKPOINT = ROOT / "runs" / "sft-v3" / "repair-lr3" / "milestones" / "2000000" / "model.safetensors"
TOKENIZER = ROOT / "data" / "sft-v3" / "tokenizer.json"
EXPECTED_HASH = "93bb235b29c8bdff5efe4e14bac223b92b5bc70fecc3023a22d8ed2d9b6fd781"
MAX_INPUT_TOKENS = 416
MAX_NEW_TOKENS = 96
PENALTY = 1.2
STOP = False

# These are pre-authored user messages.  They intentionally continue the same
# fictional planning thread and do not assert that any prior student response
# was correct, helpful, or adopted.
PROMPTS = [
    "I’m planning a fictional neighborhood book-swap for Sunday afternoon in our community room. About 12 people may join and I have a budget of ₹1,200. Can you help me outline a simple objective?",
    "I want the event to feel welcoming rather than like a formal library sale. What would be a clear one-sentence purpose for the invitation?",
    "The community room is available from 2:00 to 5:30 p.m. on Sunday. How much of that window should be public event time versus setup and cleanup?",
    "For planning purposes, assume all 12 people can bring books, but some may arrive empty-handed. How can the swap still work fairly?",
    "Could you suggest a simple rule for how many books each person may take without making it too strict?",
    "I do not want to buy books or take deposits. What low-cost supplies are actually necessary for this fictional event?",
    "Let’s reserve ₹300 for tea and biscuits. What is left from ₹1,200 for all other supplies?",
    "If name labels cost ₹120 and signs cost ₹180, how much remains after the refreshments, labels, and signs?",
    "I may use the remaining money for basic stationery and a small contingency. Can you split ₹600 between those two in a cautious way?",
    "Please give me a short checklist for the room layout: entry, book tables, browsing space, and exit.",
    "The room has six rectangular tables. How might I assign them by book type without assuming people bring a balanced selection?",
    "I’d rather avoid complex genres. Would fiction, nonfiction, children’s/young readers, and a mixed table be enough?",
    "What wording could explain that books should be clean and reasonably intact, without sounding judgmental?",
    "Please draft a friendly line saying textbooks, magazines, and damaged books may be left at home for this first swap.",
    "I want children to be welcome with an adult, but the event is not supervised childcare. How should that be stated simply?",
    "Could you propose three tiny volunteer roles for participants, without assigning anyone yet?",
    "For a group of 12, is one welcome person, one table helper, and one cleanup helper a sensible minimum?",
    "I’ll be the organizer in the fictional plan. What should I do before the doors open besides arranging tables?",
    "Can you make a compact setup timeline from 2:00 to 2:30 p.m.?",
    "Let’s say browsing starts at 2:30 p.m. What could happen in the first ten minutes so late arrivals do not disrupt things?",
    "I don’t want speeches. Could the welcome be under two minutes, and what should it cover?",
    "What is a calm way to handle someone who wants the same book as another person?",
    "Would a visible ‘please ask before taking from the hold area’ sign be useful, or does that overcomplicate a small swap?",
    "I think we should not have a hold area after all. How can I keep the rules simple with just browsing tables?",
    "Could you write four short table signs: fiction, nonfiction, children’s/young readers, and mixed?",
    "Please draft a short invitation message with Sunday afternoon, the community room, 12-person size, and the idea of bringing a few books.",
    "Make that invitation less formal and add that people can come even if they only want to browse.",
    "I do not want to promise snacks in the invitation yet. Can you revise the wording without mentioning food?",
    "Should the invitation ask people to RSVP, given the room is comfortable for about 12 people?",
    "Write one optional RSVP sentence that does not imply a booking or guarantee a place.",
    "A neighbor says they have a folding chair and can lend it. Since this is fictional planning, how should I note that as a possible backup rather than a confirmed item?",
    "What accessibility details should I check about the room before describing the event to neighbors?",
    "Please suggest a respectful invitation line asking people to tell me privately if they need seating, step-free access, or another accommodation.",
    "The room can get noisy. What simple choices could make it easier for people who prefer a quieter environment?",
    "I’m considering a 15-minute quiet browsing period near the start. Where could it fit in the schedule?",
    "Would 2:35 to 2:50 p.m. work for that quiet browsing period if the doors open at 2:30?",
    "After the quiet period, I want normal conversation and browsing. What time should a casual ‘share one recommendation’ moment happen?",
    "Keep that recommendation moment optional and brief. Can you phrase an announcement for it?",
    "What should happen to books that nobody takes, assuming I do not want to carry an unknown number home?",
    "Please give two low-pressure options for unclaimed books that do not require contacting any outside organization.",
    "I prefer the option where original owners take their books back unless they choose otherwise. How should we communicate that at entry?",
    "Could you draft a small sign for the return-your-books option?",
    "Let’s revisit the budget. If stationery is ₹250 and the contingency is ₹350, does that match the ₹600 remaining we calculated?",
    "If I spend only ₹200 on stationery, how much contingency would remain from that ₹600 allocation?",
    "I want to keep the total cap at ₹1,200 even if costs change. What should the plan say about optional purchases?",
    "Can you list a bare-minimum stationery kit that is likely to stay within ₹200?",
    "Should we use paper name tags or skip them and ask people to introduce themselves?",
    "I think paper name tags are worth it because some neighbors have not met. What information should be on each tag?",
    "How many name tags should I prepare for 12 expected participants plus the organizer and a few extras?",
    "Would 18 name tags be a reasonable number, and why?",
    "Please give a practical check-in flow that does not collect personal data beyond a first name if someone chooses to share it.",
    "I do not want a written attendance list. How can the welcome person still know roughly when the room is getting full?",
    "If more than 12 people arrive, what is a polite fictional contingency that does not make anyone feel rejected?",
    "Could we frame it as a small drop-in gathering rather than a capped event, while still protecting the room’s comfort?",
    "What should the welcome person say if the room feels crowded for a few minutes?",
    "I’d like to include a simple book-label station. What should a label ask for besides the book title?",
    "I do not want people to write prices because everything is a swap. Can you phrase that on the label sign?",
    "Should labels include an owner name, or is that unnecessary if books are on open tables?",
    "Let’s skip owner names on labels. How can people identify a book they brought if they want to take it back later?",
    "Could a removable dot sticker with a first-name initial work, with participation optional?",
    "Please draft an unobtrusive sign explaining the optional dot-sticker idea.",
    "I want to discourage people from bringing very large bags of books. What is a friendly suggested limit?",
    "Would ‘bring up to five books if you can’ be flexible enough for this first event?",
    "Please add a sentence that nobody needs to match the number they bring exactly.",
    "What time should we stop accepting new books so cleanup does not become chaotic?",
    "If public browsing runs until 4:45 p.m., is 4:30 a sensible cutoff for adding books?",
    "Can you outline a 4:30 to 5:30 p.m. closing sequence, including return choices and cleanup?",
    "I want one ten-minute buffer before the room must be empty at 5:30. Please adjust that closing sequence.",
    "Which supplies should be put away first during cleanup so the main room clears quickly?",
    "Could you suggest a two-person cleanup division if only two volunteers stay?",
    "What should I do if no volunteers stay for cleanup, without assuming anyone has agreed in advance?",
    "I need a contingency for a rainy Sunday, even though the event is indoors. What might rain affect?",
    "What is one sentence I can add to the invitation about wet umbrellas and protecting books?",
    "Suppose the community room is unexpectedly unavailable that afternoon. What should the fictional plan say, without making alternate bookings?",
    "Please make that cancellation/update message short, neutral, and clear that this is only a planning example.",
    "What if only four people come? How can the gathering still feel worthwhile?",
    "And what if all 12 arrive with mostly novels? How can the mixed table avoid looking like a failure?",
    "I want the event to be inclusive of different reading levels and languages. What invitation wording could welcome that without promising a curated collection?",
    "Could you add a line encouraging people to bring books they genuinely think another neighbor might enjoy?",
    "I do not want any photography or social-media posting as part of this small event. How can I state that gently?",
    "Please draft a small sign saying photos only with everyone’s clear permission.",
    "Should I ask people to silence phones, or is that too formal for a neighborhood swap?",
    "Give me a softer version that asks people to keep calls outside the browsing area when possible.",
    "What safety or room-care reminders are appropriate without turning the event into a rule sheet?",
    "Could you reduce those to three short reminders suitable for one sign?",
    "I’m thinking of placing a small feedback card near the exit. What two questions would be most useful for a first-time event?",
    "I do not want to collect contact details on that card. Can the questions stay anonymous?",
    "Please phrase the anonymous feedback prompt in a warm, non-corporate way.",
    "How can I estimate whether the ₹300 refreshments allowance is enough for 12 people without choosing specific products?",
    "If refreshments cost ₹25 per person for 12 participants, what is the total and how much of the ₹300 allowance remains?",
    "If three extra drop-ins share refreshments at the same ₹25 estimate, would the ₹300 allowance still cover it?",
    "I may decide to skip refreshments entirely if the budget gets tight. How can the plan keep food optional without affecting the main event?",
    "Please summarize the current budget categories and amounts using the figures we discussed, but label assumptions clearly.",
    "Now give me a concise run-of-show from setup through room close, using the times we settled on where possible.",
    "Could you turn the invitation ideas into a final short message, keeping it fictional and making no real booking or commitment?",
    "Please include the suggested bring-up-to-five-books guidance and the note that browsing is welcome.",
    "Before we wrap, what are the three details I should confirm about the community room in this fictional scenario?",
    "What are the three most important things the welcome person should remember?",
    "What are the three most important things the cleanup helpers should remember?",
    "Please give a final compact recap of the fictional Sunday book-swap plan: objective, people, timing, budget, basic rules, accessibility, and contingencies."
]

HOST_FACT_NOTE = (
    "External context support — not model memory. User-provided facts only: this is fictional planning, "
    "not real bookings or messages; the event is Sunday afternoon in a community room; about 12 participants; "
    "total budget ₹1,200. Do not claim actions were taken."
)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def atomic_json(path, value):
    path = Path(path)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path)

def append_record(record):
    with RAW.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        stream.flush(); os.fsync(stream.fileno())

def on_stop(*_):
    global STOP
    STOP = True

def system_health():
    import subprocess
    swap = subprocess.run(["sysctl", "vm.swapusage"], capture_output=True, text=True, check=False).stdout
    import re
    match = re.search(r"used = ([0-9.]+)M", swap)
    from train_local import thermal
    critical = thermal()
    return {"free_disk_bytes": shutil.disk_usage(ROOT).free, "swap_used_mb": float(match.group(1)) if match else None,
            "thermal_state": critical, "battery_policy": "continue_on_battery"}

def guard(mx, baseline):
    if STOP or (OUT / "STOP").exists():
        raise InterruptedError("stop_requested")
    health = system_health()
    health.update(mlx_active_bytes=int(mx.get_active_memory()), mlx_cache_bytes=int(mx.get_cache_memory()), mlx_peak_bytes=int(mx.get_peak_memory()))
    health["mlx_allocator_bytes"] = health["mlx_active_bytes"] + health["mlx_cache_bytes"]
    if health["thermal_state"] >= 3: raise RuntimeError("guard_critical_thermal")
    if health["free_disk_bytes"] < 15 * 2**30: raise RuntimeError("guard_disk_reserve")
    if health["mlx_peak_bytes"] > 12 * 2**30 or health["mlx_allocator_bytes"] > 12 * 2**30: raise RuntimeError("guard_mlx_memory")
    if baseline["swap_used_mb"] is not None and health["swap_used_mb"] is not None and health["swap_used_mb"] - baseline["swap_used_mb"] > 1024:
        raise RuntimeError("guard_swap_growth")
    return health

def load_records():
    if not RAW.exists(): return []
    records = [json.loads(line) for line in RAW.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [r.get("turn_id") for r in records]
    if ids != list(range(1, len(records) + 1)) or len(set(ids)) != len(ids):
        raise RuntimeError("raw log has missing, unordered, or duplicate turn IDs")
    if any(r.get("user") != PROMPTS[i] for i, r in enumerate(records)):
        raise RuntimeError("raw log does not match pinned prompt plan")
    return records

def build_input(tok, records, current_user):
    from sft_common import render
    base = [{"role": "system", "content": HOST_FACT_NOTE}]
    chosen = []
    dropped = []
    # Retain the newest complete actual pairs that fit; no partial pair is retained.
    for position, rec in enumerate(reversed(records)):
        candidate = [{"role":"user", "content":rec["user"]}, {"role":"assistant", "content":rec["assistant_text"]}] + chosen
        messages = base + candidate + [{"role":"user", "content":current_user}]
        count = len(tok.encode(render(messages, True)).ids)
        if count <= MAX_INPUT_TOKENS:
            chosen = candidate
        else:
            dropped.extend(x["turn_id"] for x in records[:len(records)-position])
            break
    messages = base + chosen + [{"role":"user", "content":current_user}]
    rendered = render(messages, True)
    count = len(tok.encode(rendered).ids)
    if count > MAX_INPUT_TOKENS: raise RuntimeError(f"current prompt exceeds {MAX_INPUT_TOKENS} input tokens: {count}")
    included = [m for m in messages[1:-1]]
    return messages, rendered, count, sorted(dropped), [r["turn_id"] for r in records if any(m["content"] == r["user"] for m in included)]

def fence(text):
    import re
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", text)), default=0)
    ticks = longest + 4
    marker = "`" * ticks
    return f"{marker}text\n{text}\n{marker}"

def write_conversation(records, finished, health, elapsed):
    lines = ["# Continuous fictional book-swap chat (100 exchanges)", "",
             "Metadata: frozen local student checkpoint `runs/sft-v3/repair-lr3/milestones/2000000/model.safetensors`; SHA-256 `" + EXPECTED_HASH + "`; generated " + time.strftime("%Y-%m-%d") + ".",
             "", "The 100 user prompts were pre-authored by the host. Assistant messages below are exact, single-pass local student outputs; no teacher substitution, correction, polishing, retry, or selection was used.",
             "", "Rolling context policy: external context support (not model memory) supplies only the initial user-provided facts. Each generation retains the newest complete actual user/assistant pairs that fit within a 416-token rendered-input cap; older complete pairs are explicitly logged as dropped. The model never receives all 100 exchanges at once.",
             "", "Coherence is the user-thread intent, not a guarantee of model competence. Raw outputs may break coherence or contain errors.", ""]
    for rec in records:
        lines += [f"## Exchange {rec['turn_id']}", "", "User", "", fence(rec["user"]), "", "Assistant", ""]
        if rec["assistant_text"] == "": lines += ["_Empty model reply._", ""]
        else: lines += [fence(rec["assistant_text"]), ""]
        if rec["generation"]["stop"] == "length": lines += ["_Generation stopped at the 96-token length cap; no text was invented beyond the actual output._", ""]
    CONVERSATION.write_text("\n".join(lines), encoding="utf-8")

def verify(records, final_health, elapsed):
    errors = []
    if len(records) != 100: errors.append("record_count_not_100")
    if [r["turn_id"] for r in records] != list(range(1, len(records)+1)): errors.append("turn_ids_not_unique_ordered")
    for r in records:
        if r["prompt_token_count"] > MAX_INPUT_TOKENS: errors.append(f"input_over_budget_turn_{r['turn_id']}")
        if r["assistant_text"] != r["generation"]["output"]: errors.append(f"assistant_raw_mismatch_turn_{r['turn_id']}")
        if r["model_input"][-2:] != [{"role":"user","content":r["user"]},{"role":"assistant","content":""}]: errors.append(f"input_shape_turn_{r['turn_id']}")
    raw_hash = sha(RAW) if RAW.exists() else None
    result = {"status": "complete" if not errors else "verification_failed", "records": len(records), "unique_ordered_turns": not any("turn_ids" in x for x in errors), "assistant_text_matches_raw_generation": not any("assistant_raw" in x for x in errors), "all_model_inputs_within_416_tokens": not any("input_over" in x for x in errors), "raw_jsonl_sha256": raw_hash, "checkpoint_sha256": sha(CHECKPOINT), "expected_checkpoint_sha256": EXPECTED_HASH, "decoder": {"mode":"greedy","repetition_penalty":PENALTY,"max_new_tokens":MAX_NEW_TOKENS,"context_limit":512,"input_cap":MAX_INPUT_TOKENS}, "run_stats": {"elapsed_seconds":elapsed,"length_stops":sum(r["generation"]["stop"]=="length" for r in records),"empty_replies":sum(r["assistant_text"]=="" for r in records),"total_generated_tokens":sum(r["generation"]["generated_tokens"] for r in records),"mean_latency_seconds":sum(r["latency_seconds"] for r in records)/max(1,len(records))}, "final_health":final_health, "limitations": ["The 100 prompts were pre-authored host inputs; only assistant text is generated.", "Rolling support is external context, not model memory; older pairs are absent once they no longer fit.", "No semantic quality correction or coherence repair was performed.", "No network, paid API, teacher generation, confirmation dataset, training, or weight update was used."], "verification_errors":errors}
    atomic_json(RESULT, result)
    return result

def main():
    if len(PROMPTS) != 100 or len(set(PROMPTS)) != 100: raise RuntimeError("prompt plan must contain 100 distinct messages")
    OUT.mkdir(parents=True, exist_ok=True)
    atomic_json(PLAN, {"version":"continuous-chat-100-v1","authorship":"host-preauthored user progression; not based on assistant replies","topic":"fictional neighborhood book-swap","messages":[{"turn_id":i+1,"user":p} for i,p in enumerate(PROMPTS)]})
    if sha(CHECKPOINT) != EXPECTED_HASH: raise RuntimeError("selected baseline checkpoint hash mismatch")
    import mlx.core as mx
    from tokenizers import Tokenizer
    from benchmark_mlx import Model
    from sft_common import configure_memory, generate
    signal.signal(signal.SIGINT, on_stop); signal.signal(signal.SIGTERM, on_stop)
    configure_memory(); baseline = guard(mx, system_health()); started = time.monotonic()
    tok = Tokenizer.from_file(str(TOKENIZER)); model = Model(768, 12, 16384)
    model.load_weights(str(CHECKPOINT)); model.set_dtype(mx.bfloat16); mx.eval(model.parameters()); guard(mx, baseline)
    records = load_records()
    for turn_id in range(len(records)+1, 101):
        guard(mx, baseline)
        user = PROMPTS[turn_id-1]
        messages, rendered, prompt_tokens, dropped, included = build_input(tok, records, user)
        started_turn = time.monotonic()
        generation = generate(model, tok, messages, penalty=PENALTY, mode="greedy", seed=20261102, cap=MAX_NEW_TOKENS, raw_prompt=rendered)
        latency = time.monotonic() - started_turn
        record = {"turn_id":turn_id,"user":user,"external_context_support":HOST_FACT_NOTE,"context_pairs_included":included,"dropped_turn_ids":dropped,"prompt_token_count":prompt_tokens,"model_input":messages + [{"role":"assistant","content":""}],"rendered_model_input":rendered,"generation":generation,"assistant_text":generation["output"],"latency_seconds":latency,"checkpoint_sha256":EXPECTED_HASH,"decode":{"mode":"greedy","repetition_penalty":PENALTY,"max_new_tokens":MAX_NEW_TOKENS}}
        append_record(record); records.append(record)
        print(json.dumps({"turn":turn_id,"input_tokens":prompt_tokens,"pairs":len(included)//2,"dropped":len(dropped),"output_tokens":generation["generated_tokens"],"stop":generation["stop"],"latency_s":round(latency,3)}), flush=True)
    final_health = guard(mx, baseline)
    write_conversation(records, True, final_health, time.monotonic()-started)
    result = verify(records, final_health, time.monotonic()-started)
    if result["status"] != "complete": raise RuntimeError("post-run verification failed")
    print(json.dumps(result, indent=2), flush=True)

if __name__ == "__main__":
    try: main()
    except Exception as exc:
        OUT.mkdir(parents=True, exist_ok=True)
        atomic_json(OUT / "interrupted-or-failed.json", {"error":type(exc).__name__,"detail":str(exc),"timestamp":time.time(),"raw_records":len(load_records()) if RAW.exists() else 0})
        raise
