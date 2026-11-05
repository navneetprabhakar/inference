"""Offline checks of the serving boundary with a deterministic test double."""
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from serve_chat import LocalServer, RequestError, Sessions, WatchedPin, load_student, resolve_weights


class MockBroker:
    def __init__(self):
        self.events = []

    @property
    def trace(self):
        return list(self.events)


class MockChat:
    def __init__(self):
        self.session = MockBroker()
        self.messages = []

    def turn(self, user, permit_calls):
        self.messages.append(user)
        if user == "bad frame":
            return dict(frames=["invalid frame"], trace=[], answer=None, failure="protocol failure")
        events = []
        if permit_calls:
            events = [dict(name="mock", ok=True, data={"result": 42}, source="offline fixture")]
            self.session.events.extend(events)
        if user == "fail after execution":
            raise RuntimeError("generation stopped")
        return dict(frames=["mock frame"], answer=f"{len(self.messages)}: {user}", trace=events, failure=None)


def run():
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        weights = root / "weights.pt"
        weights.write_bytes(b"pin verification fixture")
        sha = hashlib.sha256(weights.read_bytes()).hexdigest()
        pin = root / "selected.json"
        pin.write_text(json.dumps(dict(weights="weights.pt", sha256=sha)))
        assert resolve_weights(None, None, pin) == (weights.resolve(), sha)
        with patch("serve_chat.torch.load", side_effect=AssertionError("unverified weights deserialized")):
            try:
                load_student(weights, "0"*64, "cpu")
            except ValueError as error:
                assert "SHA-256 mismatch" in str(error)
            else:
                raise AssertionError("accepted bad checksum")

        loads = []
        def mock_runtime(spec):
            loads.append(spec["sha256"])
            return MockChat, {"sha256":spec["sha256"], "runtime":spec.get("runtime", "raw")}

        rotating = Sessions(None, None, watch=WatchedPin(pin, mock_runtime))
        a = rotating.open()
        old_chat = rotating.lookup(a["session"]).chat
        one = rotating.turn(a["session"], "one", "original chat", False)
        rotating.open()
        assert loads == [sha]
        pin.write_text(json.dumps(dict(weights="next.pt", sha256="b"*64, runtime="product")))
        b = rotating.open()
        assert b["model"] == {"sha256":"b"*64, "runtime":"product"} and not b["turns"]
        assert rotating.open(a["session"]) == dict(a, turns=[one])
        assert rotating.lookup(a["session"]).chat is old_chat
        pin.write_text("{incomplete")
        try:
            rotating.open()
        except RequestError as error:
            assert error.status == 503
        else:
            raise AssertionError("invalid pin opened a new session")
        assert rotating.turn(a["session"], "two", "after rotation", False)["answer"] == "2: after rotation"
        assert rotating.turn(b["session"], "one", "new generation", False)["answer"] == "1: new generation"
        assert loads == [sha, "b"*64]

    info = dict(name="GPT-2 small", parameters=124439808, checkpoint="mock.pt", sha256="a"*64, device="cpu")
    sessions = Sessions(MockChat, info)
    with LocalServer(0, sessions) as server:
        base = f"http://127.0.0.1:{server.server_port}"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def post(path, payload, status=200, headers=None):
            req = Request(base+path, data=json.dumps(payload).encode(),
                          headers={"Content-Type":"application/json", **(headers or {})})
            try:
                with urlopen(req, timeout=5) as response:
                    assert response.status == status
                    return json.load(response)
            except HTTPError as error:
                assert error.code == status, (error.code, status)
                return json.load(error)

        try:
            with urlopen(base, timeout=5) as response:
                html = response.read().decode()
                assert "Allow offline tools this turn" in html and "Content-Security-Policy" in response.headers
            post("/api/session", {}, 403, {"Origin":"https://offsite.invalid"})
            post("/api/session", {}, 403, {"Host":"offsite.invalid"})
            a = post("/api/session", {})["session"]
            b = post("/api/session", {})["session"]
            assert a != b
            turn = dict(session=a, id="one", message="first", permit_calls=True)
            first = post("/api/turn", turn)
            assert first["answer"] == "1: first" and first["trace"][0]["data"]["result"] == 42
            assert post("/api/turn", turn) == first
            post("/api/turn", dict(turn, message="differing replay"), 409)
            second = post("/api/turn", dict(turn, id="two", message="second", permit_calls=False))
            assert second["answer"] == "2: second" and second["trace"] == []
            assert post("/api/session", {"session":a})["turns"] == [first, second]
            assert post("/api/session", {"session":b})["turns"] == []
            failure = post("/api/turn", dict(turn, session=b, message="bad frame"))
            assert failure["answer"] is None and failure["failure"] and failure["frames"] == ["invalid frame"]
            host_failure = post("/api/turn", dict(turn, session=b, id="two", message="fail after execution"))
            assert host_failure["answer"] is None and host_failure["failure"] and len(host_failure["trace"]) == 1
            post("/api/turn", dict(turn, session=b, id="three"), 409)
            post("/api/turn", dict(turn, permit_calls=1), 400)
            post("/api/turn", dict(turn, session="unknown-session"), 404)
        finally:
            server.shutdown()
            thread.join()
    print("Serving checks passed: pin, loopback origin, session history/isolation, replay, permissions and failures.")


if __name__ == "__main__":
    run()
