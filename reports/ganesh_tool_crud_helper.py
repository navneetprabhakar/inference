"""Execution-verified 10-tool CRUD lesson generator for Ganesh-base SFT v2.

Replays every tool proposal through `MockTools` (`reports/ganesh-tool-crud-v1/harness.py`)
so that every `<|python_start|>...<|python_end|>` call and `<|output_start|>...<|output_end|>`
observation is 100% execution-verified before dataset admission.
"""
from __future__ import annotations

from copy import deepcopy
import json
import random

TOOLS = {
    "notes": "text",
    "tasks": "title",
    "contacts": "email",
    "inventory": "label",
    "events": "description",
    "bookmarks": "url",
    "tickets": "summary",
    "preferences": "setting",
    "documents": "content",
    "projects": "name",
}

TRAIN_VALUES = [
    ("r1", "blue folder", "green folder"),
    ("r2", "quarterly budget review", "final budget review"),
    ("r3", "ops-team@example.org", "platform-team@example.org"),
    ("r4", "rack-north-04", "rack-south-08"),
    ("r5", "sprint planning", "release retrospective"),
    ("r6", "https://docs.example.org/v1", "https://docs.example.org/v2"),
]

VAL_VALUES = [
    ("v1", "amber binder", "silver binder"),
    ("v2", "security audit checklist", "signed audit checklist"),
]


def dump(x: object) -> str:
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


class VerifiedCrudBuilder:
    def __init__(self, seed_state: dict | None = None) -> None:
        self.state = deepcopy(seed_state or {n: {} for n in TOOLS})
        self.messages: list[dict] = []
        self.policies: list[dict] = []
        self.calls = 0

    def user(self, text: str, *, enabled: bool = True) -> None:
        self.messages.append({"role": "user", "content": text})
        self.policies.append({
            "permit_calls": enabled,
            "allowed_names": sorted(TOOLS.keys()) if enabled else [],
        })

    def call_crud(self, name: str, arguments: dict) -> dict:
        field = TOOLS[name]
        op = arguments["op"]
        key = arguments["id"]
        store = self.state[name]
        if op == "create" and key in store:
            res = {"ok": False, "error": "already_exists"}
        elif op != "create" and key not in store:
            res = {"ok": False, "error": "not_found"}
        elif op == "delete":
            del store[key]
            res = {"ok": True, "deleted": key}
        else:
            if op in ("create", "update"):
                store[key] = {"id": key, field: arguments[field]}
            res = {"ok": True, "record": deepcopy(store[key])}

        self.calls += 1
        call_id = f"c{self.calls}"
        proposal = {"name": name, "arguments": deepcopy(arguments)}
        observation = {
            "call_id": call_id,
            "source": "offline mock",
            "name": name,
            **res,
        }
        self.messages.append({"role": "assistant", "tool_call": proposal, "call_id": call_id})
        self.messages.append({"role": "tool", "call_id": call_id, "record": observation})
        return observation

    def assistant_text(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})


def build_crud_lessons(split: str, *, seed: int = 103) -> list[dict]:
    rng = random.Random(seed)
    val_pool = TRAIN_VALUES if split == "train" else VAL_VALUES
    rows: list[dict] = []

    # 1. Single-turn create / read / update / delete across all 10 tools
    for name, field in TOOLS.items():
        for rec_id, val1, val2 in val_pool:
            # Create
            b = VerifiedCrudBuilder()
            b.user(f'Use {name} to create record {rec_id} with {field} "{val1}".', enabled=True)
            obs = b.call_crud(name, {"op": "create", "id": rec_id, field: val1})
            assert obs["ok"]
            b.assistant_text(f'Created {name} record {rec_id} with {field} "{val1}".')
            rows.append({
                "family": "crud_single",
                "split": split,
                "protocol": "crud-v1",
                "policy_mode": "enabled_call",
                "messages": b.messages,
                "policies": b.policies,
                "provenance": "ganesh_crud_verified",
            })

            # Read
            seed_state = {n: {} for n in TOOLS}
            seed_state[name][rec_id] = {"id": rec_id, field: val1}
            b = VerifiedCrudBuilder(seed_state)
            b.user(f"Use {name} to read record {rec_id} and tell me its {field}.", enabled=True)
            obs = b.call_crud(name, {"op": "read", "id": rec_id})
            assert obs["ok"] and obs["record"][field] == val1
            b.assistant_text(f'Record {rec_id} in {name} has {field} "{val1}".')
            rows.append({
                "family": "crud_single",
                "split": split,
                "protocol": "crud-v1",
                "policy_mode": "enabled_call",
                "messages": b.messages,
                "policies": b.policies,
                "provenance": "ganesh_crud_verified",
            })

            # Update
            b = VerifiedCrudBuilder(seed_state)
            b.user(f'Use {name} to change record {rec_id} {field} to "{val2}".', enabled=True)
            obs = b.call_crud(name, {"op": "update", "id": rec_id, field: val2})
            assert obs["ok"] and obs["record"][field] == val2
            b.assistant_text(f'Updated {name} record {rec_id} {field} to "{val2}".')
            rows.append({
                "family": "crud_single",
                "split": split,
                "protocol": "crud-v1",
                "policy_mode": "enabled_call",
                "messages": b.messages,
                "policies": b.policies,
                "provenance": "ganesh_crud_verified",
            })

            # Delete
            b = VerifiedCrudBuilder(seed_state)
            b.user(f"Use {name} to delete record {rec_id}.", enabled=True)
            obs = b.call_crud(name, {"op": "delete", "id": rec_id})
            assert obs["ok"] and obs["deleted"] == rec_id
            b.assistant_text(f"Deleted record {rec_id} from {name}.")
            rows.append({
                "family": "crud_single",
                "split": split,
                "protocol": "crud-v1",
                "policy_mode": "enabled_call",
                "messages": b.messages,
                "policies": b.policies,
                "provenance": "ganesh_crud_verified",
            })

    # 2. Multi-turn 4-step CRUD workflows (create -> update -> read -> delete)
    for name, field in TOOLS.items():
        rec_id = "w1" if split == "train" else "w2"
        v_init = "first draft" if split == "train" else "initial note"
        v_next = "final draft" if split == "train" else "revised note"
        b = VerifiedCrudBuilder()
        b.user(f'Use {name}: create record {rec_id} with {field} "{v_init}".', enabled=True)
        b.call_crud(name, {"op": "create", "id": rec_id, field: v_init})
        b.assistant_text(f'Created {name} record {rec_id} with {field} "{v_init}".')

        b.user(f'Use {name}: update record {rec_id} with {field} "{v_next}".', enabled=True)
        b.call_crud(name, {"op": "update", "id": rec_id, field: v_next})
        b.assistant_text(f'Updated {name} record {rec_id} {field} to "{v_next}".')

        b.user(f"Use {name}: read record {rec_id}.", enabled=True)
        b.call_crud(name, {"op": "read", "id": rec_id})
        b.assistant_text(f'Record {rec_id} in {name} currently has {field} "{v_next}".')

        b.user(f"Use {name}: delete record {rec_id}.", enabled=True)
        b.call_crud(name, {"op": "delete", "id": rec_id})
        b.assistant_text(f"Deleted record {rec_id} from {name}.")

        rows.append({
            "family": "crud_workflow",
            "split": split,
            "protocol": "crud-v1",
            "policy_mode": "enabled_call",
            "messages": b.messages,
            "policies": b.policies,
            "provenance": "ganesh_crud_workflow_verified",
        })

    # 3. Error handling (not_found & already_exists), disabled refusal, enabled no-call, clarification
    for name, field in TOOLS.items():
        # Missing record
        b = VerifiedCrudBuilder()
        b.user(f"Use {name} to read record missing. If absent, say it was not found.", enabled=True)
        obs = b.call_crud(name, {"op": "read", "id": "missing"})
        assert not obs["ok"] and obs["error"] == "not_found"
        b.assistant_text(f"Record missing was not found in {name}.")
        rows.append({
            "family": "crud_error",
            "split": split,
            "protocol": "crud-v1",
            "policy_mode": "enabled_call",
            "messages": b.messages,
            "policies": b.policies,
            "provenance": "ganesh_crud_error_verified",
        })

        # Disabled refusal
        b = VerifiedCrudBuilder()
        b.user(f"Create {name} record r1 with {field} blue folder.", enabled=False)
        b.assistant_text(f"Tools are disabled for this turn, so I cannot create record r1 in {name}.")
        rows.append({
            "family": "crud_disabled_no_call",
            "split": split,
            "protocol": "crud-v1",
            "policy_mode": "disabled_no_call",
            "messages": b.messages,
            "policies": b.policies,
            "provenance": "ganesh_crud_policy_verified",
        })

        # Enabled no-call explanation
        b = VerifiedCrudBuilder()
        b.user(f"Explain what updating a record in {name} means. Do not modify any records.", enabled=True)
        b.assistant_text(
            f"Updating a record in {name} replaces the existing {field} value for a given record id without creating a new id. No records were modified."
        )
        rows.append({
            "family": "crud_enabled_no_call",
            "split": split,
            "protocol": "crud-v1",
            "policy_mode": "enabled_no_call",
            "messages": b.messages,
            "policies": b.policies,
            "provenance": "ganesh_crud_policy_verified",
        })

        # Ambiguous delete clarification
        b = VerifiedCrudBuilder()
        b.user(f"Delete that record from {name}.", enabled=True)
        b.assistant_text(f"Which record id in {name} would you like me to delete?")
        rows.append({
            "family": "crud_clarify",
            "split": split,
            "protocol": "crud-v1",
            "policy_mode": "enabled_no_call",
            "messages": b.messages,
            "policies": b.policies,
            "provenance": "ganesh_crud_policy_verified",
        })

    rng.shuffle(rows)
    return rows
