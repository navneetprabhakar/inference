"""Regression checks for collecting arguments across turns without guessed execution."""
from slot_dialogue_chat import Request, collect
from tools import execute


def request_for(action, opening):
    request = Request(action)
    assert collect(request, opening, opening=True) and request.missing
    return request


def finish(request, text, expected):
    assert request.missing and collect(request, text) and not request.missing
    proposed = request.proposal()
    assert execute(proposed["name"], proposed["arguments"]) == expected, proposed


def verify():
    for action, opening, reply, expected in (
        ("subtract", "Subtract 8", "25", 17),
        ("subtract", "Subtract from 8", "25", -17),
        ("divide", "Divide by 8", "32", 4),
        ("divide", "Divide 32", "8", 4),
        ("convert", "Convert 3 kg", "grams", 3000),
        ("convert", "Convert into days", "48 hours", 2),
        ("multiply", "Multiply 1.5", "4", 6),
    ):
        finish(request_for(action, opening), reply, expected)
    request = request_for("subtract", "Subtract 9")
    assert collect(request, "Actually 7 instead", revise=True)
    assert request.values == {"b": 7}
    finish(request, "19", 12)

    request = request_for("add", "Add 8")
    assert collect(request, "17 not 8", revise=True)
    assert request.values == {"a": 17}
    assert not collect(request, "There were 88 people in my class")
    assert not collect(request, "48 days")
    assert request.values == {"a": 17}
    finish(request, "3", 20)

    request = request_for("convert", "Convert 2 hours")
    assert collect(request, "I meant days", revise=True)
    assert request.values == {"value": 2, "from": "day"}
    finish(request, "hours", 48)

    request = request_for("convert", "Convert from hours to minutes")
    assert not collect(request, "I meant seconds", revise=True)
    finish(request, "0.5", 30)
    print("Slot ordering, correction, unrelated input rejection and unit provenance passed.")


def verify_broker_path():
    import sys
    from types import SimpleNamespace
    from unittest.mock import patch
    import torch
    from serve_chat import CPUGuard, PREVIEW_PIN, resolve_weights, load_student
    from slot_dialogue_chat import Chat
    from tokenizer import load

    torch.set_num_threads(1)
    weights, sha = resolve_weights(None, None, PREVIEW_PIN)
    model, tok = load_student(weights, sha, "cpu"), load()
    def diagnostic_classifier(text, pending=False):
        if pending:
            return "cancel" if text == "Cancel" else "revise" if text.startswith("Correction") else "supply"
        return "divide" if text.startswith("Divide") else None

    with patch.dict(sys.modules, {"slot_dialogue_head": SimpleNamespace(classify=diagnostic_classifier)}):
        session = Chat(model, tok, CPUGuard())
        partial = session.turn("Divide by 3", permit_calls=True)
        assert not partial["trace"] and "3" in partial["answer"]
        revised = session.turn("Correction, 7", permit_calls=True)
        assert not revised["trace"] and "7" in revised["answer"]
        call = {"name": "calculate", "arguments": {"a": 14, "b": 7, "op": "divide"}}
        completed = session.turn("14", permit_calls=True, fixture_for=call, fixture={"result": 109})
        assert completed["answer"] == "109" and len(completed["trace"]) == 1
        assert completed["trace"][0]["arguments"] == call["arguments"]
        assert completed["frame_origins"] == ["learned-dialogue-act/typed-serialization", "host/observed-number"]
        session.turn("Divide 16")
        disabled = session.turn("4", permit_calls=False)
        assert not disabled["trace"] and "permit" in disabled["answer"] and session._chat.pending is None
        session.turn("Divide by 4")
        cancelled = session.turn("Cancel")
        assert not cancelled["trace"] and session._chat.pending is None
        session.turn("Divide by 4")
        session.turn("My name is Orla.")
        assert session._chat.pending is None
    print("Fixed-act integration: counterfactual observation, permission, cancellation and name interruption passed.")


if __name__ == "__main__":
    verify()
    verify_broker_path()
