"""One local neural conversation, with a host-owned offline tool trace."""
import json
import re
import torch

from dialogue import parse_assistant
from guards import ResourceStop
from tokenizer import EOT
from tools import FixtureSession


def encode_frame(tok, role, value):
    prefix = tok.encode(role.capitalize()+":").ids
    raw = json.dumps(value,ensure_ascii=False,separators=(",",":"),allow_nan=False)
    content = tok.encode(raw).ids
    if EOT in content:
        raise ValueError("Unexpected frame delimiter")
    return prefix, content+[EOT]


def tool_view(record):
    return ({"name":record.get("name"),"id":record["call_id"],"result":record["data"]["result"]}
            if record["ok"] else {"id":record["call_id"],"error":record["error"]})


NO_CALL = re.compile(
    r"\b(?:without (?:using |calling )?|(?:do not|don['’]t|never) (?:use|call|run|invoke) )"
    r"(?:any |a |the |external |available |offline |local )*(?:tools?|calculators?|converters?|services?)\b"
    r"|\bno tool(?:s| calls?)?\b", re.IGNORECASE)


class Chat:
    def __init__(self,model,tok,guard):
        self.model,self.tok,self.guard = model,tok,guard
        self.ids=[]
        self.session=FixtureSession()

    @torch.inference_mode()
    def turn(self,user,permit_calls=True,fixture_for=None,fixture=None):
        self.session.start_turn(permit_calls=permit_calls is True and not NO_CALL.search(user),
                                fixture_for=fixture_for,fixture=fixture)
        offset=len(self.session.trace)
        working=self.ids.copy()
        header, body=encode_frame(self.tok,"user",user)
        working.extend(header+body)
        frames=[]
        answer=None
        failure=None
        try:
            while True:
                prefix=self.tok.encode("Assistant:").ids
                working.extend(prefix)
                if len(working)+96>1024:
                    raise ValueError("conversation exceeds context")
                suffix=[]
                for _ in range(96):
                    self.guard.check()
                    device=next(self.model.parameters()).device
                    ids=torch.tensor([working],device=device)
                    scores=self.model.next_logits(ids)[0] if hasattr(self.model,"next_logits") else self.model(ids)[0,-1]
                    token=scores.argmax().item()
                    suffix.append(token)
                    working.append(token)
                    if token==EOT:
                        break
                frames.append(self.tok.decode([n for n in suffix if n!=EOT]))
                payload=parse_assistant(self.tok,suffix)
                if "text" in payload:
                    answer=payload["text"]
                    break
                observed=self.session.propose(json.dumps(payload["call"]),assistant_call_boundary=True)
                header,body=encode_frame(self.tok,"tool",tool_view(observed))
                working.extend(header+body)
        except (ValueError, RecursionError, ResourceStop, RuntimeError) as e:
            failure=str(e)
        finally:
            # Preserve the real turn and any effect already observed. Close a truncated
            # frame for the next host role without changing the raw recorded response.
            if len(working)<=1024 or len(self.session.trace)>offset:
                if working[-1]!=EOT:
                    working.append(EOT)
                self.ids=working
        return dict(answer=answer,frames=frames,trace=self.session.trace[offset:],failure=failure)
