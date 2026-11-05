"""Versioned GPT-2 dialogue framing shared by SFT and inference.

A host-written role header precedes a compact JSON object. Numeric GPT-2 EOT
terminates each frame. Headers and JSON bodies are tokenized separately so
training and generation see exactly the same assistant prefix.
"""
import json
from dataclasses import dataclass

from tokenizer import EOT
from tools import unique_fields

VERSION = "astra-dialogue-v1"
IGNORE = -100
CONTEXT = 1024
HEADERS = {role: f"[{role}]\n" for role in ("system", "user", "assistant", "tool")}


def _json(value):
    # Escaping angle brackets also makes literal GPT-2 special-token spellings inert.
    result = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
                        allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e")
    try:
        result.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("invalid UTF-8 dialogue content") from error
    return result


def _proposal(value):
    if type(value) is not dict or value.keys() != {"name", "arguments"}:
        raise ValueError("invalid call fields")
    if not isinstance(value["name"], str) or not value["name"] or type(value["arguments"]) is not dict:
        raise ValueError("invalid tool name or arguments")
    _json(value)  # finite numbers and JSON-serializable arguments only


def _assistant_payload(value):
    if type(value) is not dict:
        raise ValueError("expected an assistant JSON object")
    if value.keys() == {"text"} and isinstance(value["text"], str) and value["text"].strip():
        _json(value)
        return
    if value.keys() == {"call"}:
        _proposal(value["call"])
        return
    raise ValueError("expected exactly one assistant text or call")


def parse_assistant(tokenizer, generated_ids):
    """Accept one complete generated frame. Dispatch remains the broker's decision."""
    if not generated_ids or generated_ids[-1] != EOT or EOT in generated_ids[:-1]:
        raise ValueError("incomplete or multiple assistant frames")
    if any(type(token) is not int or token < 0 or token >= EOT for token in generated_ids[:-1]):
        raise ValueError("invalid generated token ID")
    raw = tokenizer.decode(generated_ids[:-1])
    value = json.loads(raw, object_pairs_hook=unique_fields)
    _assistant_payload(value)
    return value


@dataclass(frozen=True)
class TrainingRow:
    inputs: list
    labels: list

    @property
    def target_count(self):
        return sum(label != IGNORE for label in self.labels)


def _frames(tokenizer, history):
    ids, target = [], []
    expected = "user"
    pending = None
    used_ids = set()
    for index, message in enumerate(history):
        role = message.get("role")
        is_call = role == "assistant" and "call" in message
        if role != expected and not (index == 0 and role == "system"):
            raise ValueError(f"unexpected role {role!r}, expected {expected!r}")
        if is_call:
            if message.keys() != {"role", "call", "call_id"}:
                raise ValueError("completed call history requires its host binding")
            _proposal(message["call"])
            call_id = message["call_id"]
            if not isinstance(call_id, str) or not call_id or call_id in used_ids:
                raise ValueError("missing or reused host call ID")
            used_ids.add(call_id)
            pending = (call_id, message["call"])
            value = {"call": message["call"]}
            expected = "tool"
        elif role == "tool":
            record = message.get("record")
            if message.keys() != {"role", "record"} or not isinstance(record, dict):
                raise ValueError("tool frame requires a host record")
            if record.get("call_id") != pending[0] or (
                ("name" in record or record.get("ok") is True) and record.get("name") != pending[1]["name"]
            ):
                raise ValueError("tool result belongs to a different proposal")
            if "arguments" in record and _json(record["arguments"]) != _json(pending[1]["arguments"]):
                raise ValueError("tool record arguments differ from the bound call")
            if type(record.get("ok")) is not bool or (
                record["ok"] and ("data" not in record or "error" in record)
            ) or (not record["ok"] and ("error" not in record or "data" in record)):
                raise ValueError("tool record must carry either data or an error")
            value = record
            pending = None
            expected = "assistant"
        else:
            if message.keys() != {"role", "text"} or not isinstance(message["text"], str):
                raise ValueError("text frame requires exactly role and text")
            value = {"text": message["text"]}
            if role == "assistant":
                _assistant_payload(value)
            expected = "assistant" if role == "user" else "user"
        header = tokenizer.encode(HEADERS[role]).ids
        body = tokenizer.encode(_json(value)).ids
        if EOT in body:
            raise ValueError("untrusted text introduced a frame terminator")
        ids.extend(header + body + [EOT])
        target.extend([False] * len(header) + [role == "assistant"] * (len(body) + 1))
    return ids, target, expected


def training_row(tokenizer, history, *, context=CONTEXT):
    """Build aligned inputs and labels for summed assistant-token cross entropy."""
    ids, target, expected = _frames(tokenizer, history)
    if not any(target):
        raise ValueError("no assistant targets")
    if expected != "user":
        raise ValueError("incomplete training conversation")
    if not 0 < len(ids) - 1 <= min(context, CONTEXT):
        raise ValueError("training conversation exceeds context")
    return TrainingRow(ids[:-1], [token if supervised else IGNORE
                                  for token, supervised in zip(ids[1:], target[1:])])


def assistant_prompt(tokenizer, history, *, reply_budget=96, context=CONTEXT):
    """Build the same prefix for actual generation, preserving complete history."""
    ids, _, expected = _frames(tokenizer, history)
    if expected != "assistant":
        raise ValueError("history is not waiting for an assistant")
    prefix = ids + tokenizer.encode(HEADERS["assistant"]).ids
    if not 0 < reply_budget <= min(context, CONTEXT) - len(prefix):
        raise ValueError("insufficient room for reserved reply")
    return prefix


def pad_row(row, length):
    if not len(row.inputs) <= length <= CONTEXT:
        raise ValueError("invalid padding length")
    count = length - len(row.inputs)
    return TrainingRow(row.inputs + [0] * count, row.labels + [IGNORE] * count)
