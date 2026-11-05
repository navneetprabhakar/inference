"""Opt-in follow-on runtime. The shipped product keeps its original tool head."""
from dataclasses import asdict
import json

import torch

from fallback_head import sha
from followon_head_v2 import PIN, load_accepted_head
from guards import ResourceStop
from local_chat import NO_CALL, encode_frame, tool_view
from product_chat import Chat as ProductChat
from tokenizer import EOT


def accepted_head():
    """Verify the frozen comparison and model blob before enabling the follow-on head."""
    pin=json.loads(PIN.read_text())
    result_path=PIN.parent/"head-v2-result.json"
    protocol_path=PIN.parent/"head-v2-protocol.json"
    result=json.loads(result_path.read_text())
    if (sha(result_path)!=pin["evidence_sha256"] or sha(protocol_path)!=pin["protocol_sha256"]
            or result["candidate_sha256"]!=pin["sha256"] or result["protocol_sha256"]!=pin["protocol_sha256"]
            or not result["accepted"] or not result["checks"] or not all(result["checks"].values())):
        raise ValueError("The v2 head does not have a verified acceptance gate")
    return load_accepted_head()


class Chat(ProductChat):
    """Use a separate learned head, preserving the product's reader and result renderer."""
    def __init__(self,model,tok,guard,reader=None):
        super().__init__(model,tok,guard,head=accepted_head(),reader=reader)
        self.last_request=None

    def decide(self,user,phase=0):
        previous=self.history[-1]["user"] if self.history else None
        return self.head.decide(user,self.session.trace,previous,self.last_request,phase)

    @torch.inference_mode()
    def turn(self,user,permit_calls=True,fixture_for=None,fixture=None):
        permit=permit_calls is True and not bool(NO_CALL.search(user))
        self.session.start_turn(permit_calls=permit,fixture_for=fixture_for,fixture=fixture)
        offset=len(self.session.trace)
        working=self.ids.copy()
        prefix,body=encode_frame(self.tok,"user",user)
        working.extend(prefix+body)
        result=dict(answer=None,frames=[],frame_origins=[],failure=None,trace=[],decision=None,
                    decisions=[],selected_path=None,copy_prompt=None)
        observed=None
        try:
            for phase in range(2):
                self.guard.check()
                if len(working)+96>self.model.positions.num_embeddings:
                    raise ValueError("conversation exceeds model context")
                decision=self.decide(user,phase)
                record=asdict(decision)
                result["decisions"].append(record)
                if phase==0:
                    result["decision"]=record
                if decision.proposal is None or not permit:
                    if phase==0 and decision.action=="recall_number":
                        trace=self.session.trace
                        observed=trace[-1] if trace and trace[-1]["ok"] else None
                    break
                if self.session.session_calls>=4 or self.session.turn_calls>=2:
                    raise ValueError("tool quota exhausted")
                proposal=decision.proposal
                prefix,body=encode_frame(self.tok,"assistant",{"call":proposal})
                working.extend(prefix+body)
                result["frames"].append(self.tok.decode(body[:-1]))
                result["frame_origins"].append("learned-v2-head/typed-serialization")
                if len(working)+96>self.model.positions.num_embeddings:
                    raise ValueError("insufficient context for tool execution")
                event=self.session.propose(json.dumps(proposal),assistant_call_boundary=True)
                self.last_request=proposal
                prefix,body=encode_frame(self.tok,"tool",tool_view(event))
                working.extend(prefix+body)
                observed=event if event["ok"] else None
                if not event["ok"]:
                    break
            if len(working)+96>self.model.positions.num_embeddings:
                raise ValueError("insufficient context for final reply")
            if observed is not None:
                reply,result["copy_prompt"]=self.respond_number(observed)
            else:
                reply=self.respond_ordinary(user,working)
            result["selected_path"]=reply.origin
            result["frame_origins"].append(reply.origin)
            result["frames"].append(reply.raw)
            result["answer"],result["failure"]=reply.answer,reply.failure
            working.extend(reply.suffix)
        except (ValueError,RuntimeError,ResourceStop,RecursionError) as exc:
            result["failure"]=str(exc)
        finally:
            result["trace"]=self.session.trace[offset:]
            if len(working)<=self.model.positions.num_embeddings or result["trace"]:
                if working and working[-1]!=EOT:
                    working.append(EOT)
                self.ids=working
            self.history.append(dict(user=user,permit_calls=permit,**result))
        return result
