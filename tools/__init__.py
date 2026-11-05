"""Session-scoped, offline calculator and conversion fixtures."""
from copy import deepcopy
from dataclasses import dataclass, field
import json
import math
from operator import add, mul, sub, truediv
import time

OPERATIONS = {"add": add, "subtract": sub, "multiply": mul, "divide": truediv}
UNITS = {
    "mm": ("length", .001), "cm": ("length", .01), "m": ("length", 1), "km": ("length", 1000),
    "g": ("mass", 1), "kg": ("mass", 1000), "ml": ("volume", 1), "l": ("volume", 1000),
    "s": ("time", 1), "min": ("time", 60), "h": ("time", 3600), "day": ("time", 86400),
}
FIELDS = {"calculate": {"op", "a", "b"}, "convert": {"value", "from", "to"}}
MAX_BYTES = 16384
MAX_NUMBER = 10**12


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def bounded_number(value):
    if type(value) not in (int, float) or abs(value) > MAX_NUMBER or not math.isfinite(value):
        raise ValueError("number outside supported range")
    return value


def validate_arguments(name, args):
    if type(name) is not str or name not in FIELDS:
        raise ValueError("tool unavailable")
    if type(args) is not dict or args.keys() != FIELDS[name]:
        raise ValueError("incorrect argument fields")
    if name == "calculate":
        if type(args["op"]) is not str or args["op"] not in OPERATIONS:
            raise ValueError("unsupported operation")
        bounded_number(args["a"])
        bounded_number(args["b"])
    else:
        if any(type(args[k]) is not str or args[k] not in UNITS for k in ("from", "to")):
            raise ValueError("unknown unit")
        if UNITS[args["from"]][0] != UNITS[args["to"]][0]:
            raise ValueError("incompatible units")
        bounded_number(args["value"])


def _dispatch(name, args):
    """Run a pure adapter after its flat argument schema and session policy have passed."""
    if name == "calculate":
        try:
            result = OPERATIONS[args["op"]](args["a"], args["b"])
        except ZeroDivisionError as error:
            raise ValueError("division by zero") from error
    else:
        result = args["value"] * UNITS[args["from"]][1] / UNITS[args["to"]][1]
    return bounded_number(result)


def execute(name, args):
    """Standalone deterministic calculator/converter, validating all inputs."""
    validate_arguments(name, args)
    return _dispatch(name, args)


def decode_proposal(raw):
    if type(raw) is not str or len(raw) > MAX_BYTES or len(raw.encode("utf-8")) > MAX_BYTES:
        raise ValueError("proposal exceeds limit")
    call = json.loads(raw, object_pairs_hook=unique_fields)
    if type(call) is not dict or call.keys() != {"name", "arguments"}:
        raise ValueError("incorrect proposal fields")
    # Re-encoding catches escaped unpaired surrogates and non-standard NaN/Infinity.
    json.dumps(call, ensure_ascii=False, allow_nan=False).encode("utf-8")
    return call


@dataclass
class FixtureSession:
    """The host owns permissions, call IDs and the authoritative observed records."""
    allowed: frozenset = frozenset(FIELDS)
    _trace: list = field(default_factory=list, init=False, repr=False)
    _decisions: list = field(default_factory=list, init=False, repr=False)
    _turn_allowed: frozenset = field(default_factory=frozenset, init=False, repr=False)
    _fixture_for: dict | None = field(default=None, init=False, repr=False)
    _fixture: dict | None = field(default=None, init=False, repr=False)
    turn_calls: int = field(default=0, init=False)
    session_calls: int = field(default=0, init=False)
    permit_calls: bool = field(default=False, init=False)

    def __post_init__(self):
        self.allowed = frozenset(self.allowed)
        if not self.allowed <= FIELDS.keys():
            raise ValueError("unknown authorized tool")

    @property
    def trace(self):
        return deepcopy(self._trace)

    @property
    def decisions(self):
        return deepcopy(self._decisions)

    def revoke(self, name):
        """Apply host revocation immediately, including within an existing turn."""
        self.allowed = self.allowed.difference((name,))

    def start_turn(self, *, permit_calls, allowed_names=None, fixture_for=None, fixture=None):
        # Fail closed if the host supplied an incomplete or invalid policy.
        self.turn_calls = 0
        self.permit_calls = False
        self._fixture_for = self._fixture = None
        if type(permit_calls) is not bool:
            raise ValueError("permit_calls must be a boolean")
        scope = self.allowed if allowed_names is None else frozenset(allowed_names)
        if not scope <= FIELDS.keys():
            raise ValueError("unknown tool in turn policy")
        if fixture is not None or fixture_for is not None:
            if type(fixture_for) is not dict or fixture_for.keys() != {"name", "arguments"}:
                raise ValueError("recorded fixture requires one bound proposal")
            validate_arguments(fixture_for["name"], fixture_for["arguments"])
            if not permit_calls or fixture_for["name"] not in scope & self.allowed:
                raise ValueError("recorded fixture outside host scope")
            if type(fixture) is not dict or len(fixture) != 1:
                raise ValueError("fixture requires one result or error")
            if "result" in fixture:
                bounded_number(fixture["result"])
            elif ("error" not in fixture or type(fixture["error"]) is not str or
                  not fixture["error"] or len(fixture["error"]) > 256):
                raise ValueError("invalid fixture error")
            json.dumps(fixture, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self._fixture_for = deepcopy(fixture_for)
            self._fixture = deepcopy(fixture)
        self._turn_allowed = scope
        self.permit_calls = permit_calls

    def propose(self, raw, *, assistant_call_boundary):
        if assistant_call_boundary is not True:
            raise ValueError("expected structured assistant call boundary")
        if self.turn_calls >= 2 or self.session_calls >= 4:
            raise ValueError("quota exhausted")
        self.turn_calls += 1
        self.session_calls += 1
        call_id = f"c{self.session_calls}"
        record = dict(call_id=call_id, source="offline fixture", schema_version=1, timestamp=time.time())
        decision = dict(call_id=call_id, stage="permission", dispatched=False)
        try:
            if not self.permit_calls:
                raise ValueError("calls prohibited")
            decision["stage"] = "schema"
            call = decode_proposal(raw)
            name = call["name"]
            decision["stage"] = "permission"
            if type(name) is not str or name not in self.allowed or name not in self._turn_allowed:
                raise ValueError("tool unavailable")
            record["name"] = name
            decision["stage"] = "schema"
            args = call["arguments"]
            validate_arguments(name, args)
            decision.update(stage="adapter", dispatched=True, name=name, arguments=deepcopy(args))
            if call == self._fixture_for:
                record["source"] = "synthetic recorded fixture"
                if "error" in self._fixture:
                    raise ValueError(self._fixture["error"])
                result = self._fixture["result"]
            else:
                result = _dispatch(name, args)
            record.update(arguments=args, ok=True, data={"result": result})
        except (ValueError, TypeError, OverflowError, RecursionError) as error:
            record.update(ok=False, error=str(error)[:256])
        self._trace.append(record)
        self._decisions.append(decision)
        return deepcopy(record)
