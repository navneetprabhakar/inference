"""Experimental multi-turn argument collection for the local calculator and converter."""
from dataclasses import dataclass, field
import json
import re

from assistant_preview import Chat as PreviewChat, PreviewBackend
from fallback_chat import Reply
from fallback_head import Decision, parse
from followon_head_v2 import normalized_words
from local_chat import NO_CALL, encode_frame
from memory_chat import operation
from reference_ops_head import REFERENCE
from tools import validate_arguments

FIELDS = {"convert": ("value", "from", "to")}
ARITHMETIC_FIELDS = ("a", "b")
NEGATIVE = re.compile(r"\b(?:don't|don’t|do not|never|without using|pretend|suppose|hypothetically|quote|if)\b", re.I)
TERSE = frozenset("""# @ a an the it that this is was are were and by from into to in as out of
    please thanks actually correction sorry instead not make change replace use with should be
    my your original starting first second other next new value number operand amount quantity
    unit units source target destination left right dividend divisor denominator numerator
    i meant mean want would like let's lets go for yes no only now then convert rather than""".split())


@dataclass
class Request:
    action: str
    values: dict = field(default_factory=dict)

    @property
    def missing(self):
        return [key for key in FIELDS.get(self.action, ARITHMETIC_FIELDS) if key not in self.values]

    def ask(self):
        missing = self.missing
        if self.action == "convert":
            prompts = {"value": "What amount should I convert?", "from": "What is the starting unit?",
                       "to": "Which unit should I convert it to?"}
            if len(missing) == 3:
                return "What amount and units should I convert? For example, 3 hours to minutes."
            return " ".join(prompts[key] for key in missing)
        if len(missing) == 2:
            return {"add": "Which two numbers should I add?", "multiply": "Which two numbers should I multiply?",
                    "subtract": "What is the starting number, and how much should I subtract?",
                    "divide": "Which number should I divide, and by what divisor?"}[self.action]
        if self.action == "subtract":
            return (f"What number should I subtract {self.values['b']} from?" if missing == ["a"] else
                    f"How much should I subtract from {self.values['a']}?")
        if self.action == "divide":
            return (f"Which number should I divide by {self.values['b']}?" if missing == ["a"] else
                    f"What should I divide {self.values['a']} by?")
        known = next(iter(self.values.values()))
        return f"What number should I {'add to' if self.action == 'add' else 'multiply by'} {known}?"

    def proposal(self):
        args = dict(self.values)
        name = "convert" if self.action == "convert" else "calculate"
        if name == "calculate":
            args["op"] = self.action
        validate_arguments(name, args)
        return {"name": name, "arguments": args}


def slots(text):
    normalized = normalized_words(text)
    # Counts/quantifiers describe how many slots exist, not their values.
    normalized = re.sub(r"\b(?:two|2|both) (?:numbers|values|operands|figures|quantities)\b", "operands", normalized)
    normalized = re.sub(r"\b(?:one|1) (?:number|value|operand|figure|quantity)\b", "operand", normalized)
    normalized = re.sub(r"\bsecond (?=(?:operand|number|value|figure)\b)", "right ", normalized)
    words, spans = parse(normalized, None)
    numbers = [s for s in spans if s.kind == "number"]
    units = [s for s in spans if s.kind == "unit"]
    return words, numbers, units


def conversion_fields(words, numbers, units, known):
    if len(numbers) > 1 or len(units) > 2:
        return {}
    fields = {"value": numbers[0].value} if numbers else {}
    for index, unit in enumerate(units):
        before = words[unit.position-1] if unit.position else None
        if before in ("into", "to", "in", "as", "target", "destination"):
            key = "to"
        elif before in ("from", "source", "starting"):
            key = "from"
        elif len(units) == 2:
            key = ("from", "to")[index]
        else:
            key = "to" if "from" in known and "to" not in known else "from"
        if key in fields:
            return {}
        fields[key] = unit.value
    return fields


def arithmetic_fields(action, words, numbers, known, opening):
    if not numbers or len(numbers) > 2:
        return {}
    if len(numbers) == 2:
        values = [n.value for n in numbers]
        if action == "subtract" and "from" in words[numbers[0].position+1:numbers[1].position]:
            values.reverse()
        return dict(zip(ARITHMETIC_FIELDS, values))
    n = numbers[0]
    before = words[:n.position]
    after = words[n.position+1:]
    if any(x in before for x in ("second", "divisor", "denominator", "right")):
        key = "b"
    elif any(x in before for x in ("first", "dividend", "numerator", "starting", "left")):
        key = "a"
    elif action == "divide" and "by" in before:
        key = "b"
    elif action == "subtract" and ("from" in before or "minus" in after):
        key = "a"
    elif action == "subtract" and (opening or "from" in after):
        key = "b"
    else:
        key = "b" if "a" in known else "a"
    return {key: n.value}


def collect(request, text, *, opening=False, revise=False):
    words, numbers, units = slots(text)
    if request.action != "convert" and units:
        return False
    if not opening and any(w not in TERSE for w in words):
        return False
    if revise and request.action == "convert" and len(units) == 1 and not numbers:
        directional = {"from", "source", "starting", "to", "into", "as", "target", "destination"}
        if not directional.intersection(words):
            filled = [key for key in ("from", "to") if key in request.values]
            if len(filled) != 1:
                return False
            request.values[filled[0]] = units[0].value
            return True
    if revise and request.action != "convert" and len(numbers) == 1:
        # A bare correction changes the known operand, never silently fills the missing one.
        named = any(w in words for w in ("first", "second", "starting", "dividend", "divisor",
                                         "numerator", "denominator", "left", "right"))
        if len(request.values) == 1 and not named:
            request.values[next(iter(request.values))] = numbers[0].value
            return True
    if revise and len(numbers) == 2:
        old_index = 0
        if any(marker in words[numbers[0].position+1:numbers[1].position] for marker in ("not", "instead", "rather")):
            old_index = 1
        old, new = numbers[old_index].value, numbers[1-old_index].value
        matches = [key for key, val in request.values.items() if val == old]
        if len(matches) != 1 or units:
            return False
        request.values[matches[0]] = new
        return True
    fields = (conversion_fields(words, numbers, units, request.values) if request.action == "convert" else
              arithmetic_fields(request.action, words, numbers, request.values, opening))
    if not fields or (not revise and any(k in request.values and request.values[k] != v for k,v in fields.items())):
        return False
    request.values.update(fields)
    return True


class SlotBackend(PreviewBackend):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from slot_dialogue_head import classify
        self.classify = classify
        self.pending = None
        self.slot_reply = None
        self.slot_call = False

    def handled(self, message=None, proposal=None):
        self.slot_reply = message
        self.slot_call = proposal is not None
        return Decision("collect_arguments", proposal, 0., {}, "learned-dialogue-act/validated-slots")

    def decide(self, user, phase=0):
        if phase:
            return Decision("done", None, 0., {}) if self.slot_call else super().decide(user, phase)
        self.slot_reply, self.slot_call = None, False
        if len(user) > 240 or any(c in user for c in ('"', '“', '”', '\n')):
            self.pending = None
            return super().decide(user, phase)
        opening = self.classify(user)
        request = self.pending
        if request:
            act = self.classify(user, pending=True)
            if act == "cancel":
                self.pending = None
                return self.handled("Cancelled. I haven’t made a tool call.")
            if NEGATIVE.search(user) or NO_CALL.search(user):
                self.pending = None
                return self.handled("I’ve cleared the pending request. No tool was run.")
            if act in ("supply", "revise") and collect(request, user, revise=act == "revise"):
                if request.missing:
                    return self.handled(request.ask())
                self.pending = None
                if not self.session.permit_calls:
                    return self.handled("This turn does not permit a new tool call. The pending request is cleared.")
                try:
                    proposal = request.proposal()
                except ValueError as exc:
                    return self.handled(f"I couldn't run that request: {exc}.")
                return self.handled(proposal=proposal)
            if act in ("supply", "revise") and not opening:
                return self.handled(request.ask())
            self.pending = None  # A new instruction or subject supersedes the old question.
        if not opening or opening not in ("convert","add","subtract","multiply","divide"):
            return super().decide(user, phase)
        if NEGATIVE.search(user) or NO_CALL.search(user) or REFERENCE.search(user):
            return super().decide(user, phase)
        words, numbers, units = slots(user)
        # Complete commands retain the ordinary, separately tested tool path.
        if (opening == "convert" and numbers and len(units) >= 2) or (opening != "convert" and len(numbers) >= 2):
            return super().decide(user, phase)
        request = Request(opening)
        if (numbers or units) and not collect(request, user, opening=True):
            return super().decide(user, phase)
        self.pending = request
        return self.handled(request.ask())

    def respond_ordinary(self, user, history_ids):
        if self.slot_reply is None:
            return super().respond_ordinary(user, history_ids)
        prefix, body = encode_frame(self.tok, "assistant", {"text": self.slot_reply})
        return Reply(json.dumps({"text": self.slot_reply}), self.slot_reply, None, prefix+body,
                     "host/dialogue-clarification")

    def turn(self, *args, **kwargs):
        self.slot_reply, self.slot_call = None, False
        # Slot turns can bypass the parent's phase-zero decision entirely.
        # Reset its per-turn notice before it renders an observed value.
        self.command_notice = None
        self.reference_call = False
        result = super().turn(*args, **kwargs)
        if self.slot_call and result["frames"] and result.get("trace"):
            result["frame_origins"][0] = "learned-dialogue-act/typed-serialization"
        if result["failure"]:
            self.pending = None
        return result


class Chat(PreviewChat):
    backend_class = SlotBackend

    def turn(self, user, *args, **kwargs):
        if operation(user) is not None:
            self._chat.pending = None
        return super().turn(user, *args, **kwargs)
