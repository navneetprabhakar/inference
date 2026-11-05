"""Local product runtime: learned tool decisions, validated results, optional extractive replies.

The response records distinguish host rendering from neural span selection and decoding.
"""
from functools import lru_cache
from pathlib import Path
import json
import torch

from checkpoint import checksum
from fallback_chat import Chat as ToolChat, Reply
from local_chat import encode_frame
from span_reader import RUN, Reader, read



@lru_cache(maxsize=1)
def selected_reader():
    """Freeze one verified reader per process, including across all benchmark cases."""
    from fit_span_reader_v2 import DIR as V2_DIR, RUN as V2_RUN, ExpandedReader

    pin_file = V2_DIR / "accepted-pin.json"
    if pin_file.exists():
        pin = json.loads(pin_file.read_text())
        report_file = V2_DIR / "result.json"
        protocol_file = V2_DIR / "protocol.json"
        if checksum(report_file) != pin["result_sha256"] or checksum(protocol_file) != pin["protocol_sha256"]:
            raise ValueError("extractive reader v2 evidence pin mismatch")
        report = json.loads(report_file.read_text())
        spec = json.loads(protocol_file.read_text())
        internal, fresh = report["internal"], report["paraphrases"]
        qualified = (
            report["state"] == "accepted"
            and report["weights_sha256"] == pin["sha256"]
            and report["threshold"] == pin["threshold"] == spec["threshold"]
            and internal["precision"] >= spec["internal_precision_min"]
            and internal["correct_positive_coverage"] >= spec["internal_correct_positive_coverage_min"]
            and fresh["precision"] >= spec["paraphrase_precision_min"]
            and fresh["correct_positive_coverage"] >= spec["paraphrase_correct_positive_coverage_min"]
        )
        if not qualified:
            raise ValueError("extractive reader v2 does not satisfy frozen promotion gates")
        model, run = ExpandedReader(), V2_RUN
        identity = dict(version=2, sha256=pin["sha256"], threshold=pin["threshold"],
                        parameters=pin["parameters"], protocol_sha256=pin["protocol_sha256"])
    else:
        report = json.loads((RUN / "result.json").read_text())
        model, run = Reader(), RUN
        identity = dict(version=1, sha256=report["weights_sha256"], threshold=report["threshold"],
                        parameters=report["parameters"])
    weights = run / "weights.pt"
    if checksum(weights) != identity["sha256"]:
        raise ValueError("extractive reader weight pin mismatch")
    model.load_state_dict(torch.load(weights, weights_only=True, map_location="cpu"))
    return model.eval(), identity


def reader_identity():
    return dict(selected_reader()[1])


def render_value(value):
    if isinstance(value,float) and value.is_integer():
        return str(int(value))
    return str(value)


class Chat(ToolChat):
    def __init__(self,model,tok,guard,head=None,reader=None):
        super().__init__(model,tok,guard,head=head)
        if reader is None:
            reader, identity = selected_reader()
            self.reader_threshold = identity["threshold"]
        else:
            self.reader_threshold = .85
        self.reader=reader.eval()

    def respond_number(self,record):
        # This is an explicit product feature. The raw GPT-2 score is separate.
        value=render_value(record['data']['result'])
        head,body=encode_frame(self.tok,"assistant",{"text":value})
        return Reply(json.dumps({"text":value}),value,None,head+body,"host/observed-number"),None

    def respond_ordinary(self,user,history_ids):
        previous=[]
        for exchange in self.history:
            previous.append(dict(role="user",text=exchange["user"]))
            if exchange.get("answer"):
                previous.append(dict(role="assistant",text=exchange["answer"]))
        previous.append(dict(role="user",text=user))
        if self.session.trace and self.session.trace[-1].get('ok') is False and self.session.trace[-1]['call_id'] not in {
            x.get('call_id') for exchange in self.history for x in exchange.get('trace',[])
        }:
            # Newly observed failure only. A previous error must not override a new topic.
            event=self.session.trace[-1]
            answer="The tool returned an error: "+event['error']
            prefix,body=encode_frame(self.tok,"assistant",{"text":answer})
            return Reply(json.dumps({"text":answer}),answer,None,prefix+body,"host/observed-error")
        extracted=read(self.reader,previous,threshold=self.reader_threshold)
        if extracted is not None:
            prefix,body=encode_frame(self.tok,"assistant",{"text":extracted})
            return Reply(json.dumps({"text":extracted}),extracted,None,prefix+body,"learned-reader/copied-span")
        return super().respond_ordinary(user,history_ids)
