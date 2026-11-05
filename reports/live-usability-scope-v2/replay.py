"""One serial, unretried replay of the frozen synthetic local usability sessions."""
import hashlib
import json
import time
from pathlib import Path
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

DIR=Path(__file__).resolve().parent
PROTOCOL_HASH="fc147de1e82cd9f9449b5aed7c67a15ed19fbb8e16402c4a7231b1d70c4ae623"
class LocalOnly(HTTPRedirectHandler):
    def redirect_request(self,*_args):
        raise ValueError("redirect from loopback endpoint")
CLIENT=build_opener(ProxyHandler({}),LocalOnly())


def post(route,payload):
    request=Request("http://127.0.0.1:8767"+route,data=json.dumps(payload).encode(),
                    headers={"Content-Type":"application/json","Origin":"http://127.0.0.1:8767"})
    with CLIENT.open(request,timeout=180) as response:
        return json.load(response)


def run():
    protocol=(DIR/"protocol.json").read_bytes()
    assert hashlib.sha256(protocol).hexdigest()==PROTOCOL_HASH
    spec=json.loads(protocol)
    raw=(DIR/"suite.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest()==spec["suite_sha256"]
    cases=json.loads(raw)
    dest=DIR/"transcripts.json"
    report=dict(protocol_sha256=PROTOCOL_HASH,suite_sha256=spec["suite_sha256"],cases=[],state="running")
    with dest.open("x") as stream:json.dump(report,stream)
    def publish():
        temp=dest.with_suffix(".tmp")
        temp.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
        temp.replace(dest)
    for case in cases:
        opened=post("/api/session",{})
        model=opened["model"]
        if model["sha256"]!=spec["expected_weights_sha256"] or model["runtime"]!=spec["expected_runtime"] or opened["turns"]:
            report.update(state="identity_mismatch",observed=model);publish()
            raise ValueError("service identity or session history mismatch")
        token=opened["session"]
        report["model"]=model
        result=dict(id=case["id"],scope=case["scope"],session_fingerprint=hashlib.sha256(token.encode()).hexdigest(),turns=[])
        report["cases"].append(result)
        for num,turn in enumerate(case["turns"],1):
            start=time.monotonic()
            try:
                answer=post("/api/turn",dict(session=token,id=f"{case['id']}-{num}",message=turn["message"],permit_calls=turn["tools"]))
                assert answer["message"]==turn["message"] and answer["permit_calls"]==turn["tools"]
            except Exception as error:
                answer=dict(message=turn["message"],permit_calls=turn["tools"],answer=None,trace=[],frames=[],
                            failure="transport error: "+str(error),selected_path=None,frame_origins=[])
            result["turns"].append(dict(turn=num,rubric=turn["rubric"],elapsed_seconds=time.monotonic()-start,**answer))
            publish()
        print(case["id"],[(t["selected_path"],t["answer"],t["failure"]) for t in result["turns"]],flush=True)
    report["state"]="complete"
    publish()


if __name__=="__main__":
    run()
