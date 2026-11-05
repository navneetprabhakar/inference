"""Explicit /calculate and /convert workflows on top of the ordinary local preview."""
from copy import deepcopy
from dataclasses import dataclass
import json
import re

from assistant_preview import Chat as PreviewChat, PreviewBackend
from explicit_command_chat import command
from fallback_chat import Reply
from fallback_head import Decision
from local_chat import NO_CALL, encode_frame
from memory_chat import operation
from slot_dialogue_chat import Request, TERSE, collect, slots
from slot_dialogue_head import classify
from tools import UNITS, bounded_number


MENU = "Choose add, subtract, multiply, or divide. You can include the numbers."
COMMANDS = {"/calculate": "calculator", "/convert": "converter"}
NAMES = {
    "add": "add", "addition": "add", "sum": "add", "plus": "add",
    "subtract": "subtract", "subtraction": "subtract", "minus": "subtract", "deduct": "subtract",
    "multiply": "multiply", "multiplication": "multiply", "product": "multiply", "times": "multiply",
    "divide": "divide", "division": "divide", "quotient": "divide",
}
LEAD = re.compile(r"^(?:(?:please|let's|lets)\s+)?("+"|".join(NAMES)+r")\b",re.I)
CANCEL = re.compile(r"(?:/cancel|cancel(?: (?:it|that|this|the request|the calculation|the conversion|please))?|never mind|nevermind|stop(?: here| the request)?|forget (?:it|that|this request)|call it off)[.!]?",re.I)
GO = re.compile(r"(?:(?:tools (?:are )?(?:enabled|on)(?: now)?)[,;.! ]+)?(?:please )?(?:go ahead|run (?:it|the calculation|the conversion)(?: now)?|proceed|do it now)[.!]?",re.I)
BLOCK = re.compile(r"\b(?:if|suppose|imagine|pretend|hypothetically|quote|either|approximately|roughly|about|at least|at most|or else)\b",re.I)
REVISE = re.compile(r"\b(?:actually|correction|correct (?:the|my|that)|replace|revise|amend|change (?:the|my|that|it)|switch (?:the|my)|wrong|misread|misspoke|typo|meant|instead|rather than|in place of|should have been|scratch)\b",re.I)
SCOPE_SWITCH = re.compile(r"\b(?:new topic|change (?:the )?(?:topic|subject)|on another (?:topic|subject)|different subject|(?:want to|rather|let.s) (?:discuss|talk about|chat about))\b",re.I)
FORBID = re.compile(r"\b(?:do not|don['’]t|never|without)\s+(?:use|using|call|calling|run|execute)",re.I)
INVALID_NUMBER = re.compile(r"\d\s*[eE]\s*[+-]?\d|\d\s*/\s*\d|\d+\s*%|\b(?:nan|infinity|half|twice|double)\b",re.I)
FIELD_WORDS = TERSE | set("given give take need needed want wanted supplied put enter field amount figure earlier previously previous slot empty missing take off pair factor factors addend addends operators total initial final correction corrected revise amended switch update amending source destination starting target use please sorry for ask asked go ahead it was my mistake".split())


@dataclass
class Guide:
    mode: str
    request: Request | None = None
    learned: bool = False
    suspended: bool = False


def normalized_field(text):
    s=text.casefold().strip().replace("−","-")
    # Canonical directional cues for the shared single-unit collector.
    s=re.sub(r"\b(?:my |the )?(?:destination|target|output|ending)(?: unit)?(?: (?:is|should be|will be))?\s*[:=]?\s*","to ",s)
    s=re.sub(r"\b(?:my |the )?(?:(?:source|input)(?: unit)?|starting unit)(?: (?:is|should be|will be))?\s*[:=]?\s*","from ",s)
    s=re.sub(r"\b(?:in place of|rather than)\b","instead of",s)
    s=re.sub(r"\b(?:replace|change|amend|update|correct|revise) (?:my |the )?(?:earlier|previous|old|filled) (?:number|value|amount)\b","change the previous value",s)
    s=re.sub(r"\b(?:my |the )?second (?:number|value|operand)\b","right operand",s)
    s=re.sub(r"\b(?:my |the )?first (?:number|value|operand)\b","left operand",s)
    return s


def apply_fields(original,text,*,opening,revision):
    """Apply an entire checked user message atomically, or leave the request untouched."""
    text=normalized_field(text)
    if (not re.fullmatch(r"[a-z0-9\s.,:'’!?-]*",text) or INVALID_NUMBER.search(text)
            or re.search(r"\bor\b|[+*/×÷%=]|[<>|]",text)):
        return None
    for run in re.findall(r"\d[\d,.]*\d",text):
        if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?",run):
            return None
    words,numbers,units=slots(text)
    if not (numbers or units) or any(w not in FIELD_WORDS for w in words):
        return None
    if "not" in words and not (revision and (len(numbers)==2 or len(units)==2)):
        return None
    if original.action!="convert" and units:
        return None
    try:
        for n in numbers:
            bounded_number(n.value)
    except ValueError:
        return None
    staged=deepcopy(original)
    # A correction with a single unnamed number and two existing operands
    # cannot identify which old field to replace.
    named=set(words)&{"left","right","first","starting","dividend","divisor","numerator","denominator"}
    if revision and original.action!="convert" and len(numbers)==1 and len(staged.values)==2 and not named:
        return None
    if original.action=="convert" and len(units)==1:
        before=words[:units[0].position]
        source=bool(set(before)&{"from","source","starting"})
        target=bool(set(before)&{"to","into","as","in","target","destination"})
        if source and target:return None
        if source or target:
            if len(numbers)>1:return None
            key="from" if source else "to"
            # Canonicalize the direction even if a number separates it from the
            # unit ("from 2 hours"). Never infer the opposite slot from history.
            fields={key:units[0].value}
            if numbers:fields["value"]=numbers[0].value
            if not revision and any(staged.values.get(k,v)!=v for k,v in fields.items()):return None
            staged.values.update(fields)
            return staged
    if revision and original.action=="convert" and len(units)==2 and not numbers:
        # Unit replacement follows the expressed old/new relation; never fill a
        # vacant destination by guessing which of two units was the correction.
        between=words[units[0].position+1:units[1].position]
        reverse=bool(set(between)&{"instead","rather","not"})
        old,new=(units[1].value,units[0].value) if reverse else (units[0].value,units[1].value)
        keys=[key for key in ("from","to") if staged.values.get(key)==old]
        if len(keys)!=1:return None
        staged.values[keys[0]]=new
        return staged
    if revision and original.action=="convert" and units and not numbers and not set(words)&{"to","from","into","as","in"}:
        if len(units)!=1 or len(set(staged.values)&{"from","to"})!=1:
            return None
    # The shared collector accepts a compact field vocabulary. Verbs and filler
    # already vetted above do not grant authority or create values.
    replacements={"earlier":"previous","initial":"starting","amend":"change","update":"change"}
    compact=" ".join(replacements.get(word,word) for word in text.split())
    compact=re.sub(r"\b(?:given|give|take|need|needed|want|wanted|supplied|put|enter|field|figure|earlier|previously|previous|slot|empty|missing|factor|factors|addend|addends|initial|corrected|revise|amended|switch|update|amending|ask|asked|mistake)\b"," ",compact)
    # Named operands may arrive backwards; avoid assigning by their surface order.
    if original.action!="convert" and len(numbers)==2 and named:
        keys=[]
        for i,n in enumerate(numbers):
            before=words[(numbers[i-1].position+1 if i else 0):n.position]
            markers=set(before)&{"left","right","first","starting","dividend","divisor","numerator","denominator"}
            if len(markers)!=1:return None
            keys.append("b" if markers & {"right","divisor","denominator"} else "a")
        if len(set(keys))!=2:return None
        for key,n in zip(keys,numbers):
            if key in staged.values and not revision and staged.values[key]!=n.value:return None
            staged.values[key]=n.value
        return staged
    if not collect(staged,compact,opening=opening,revise=revision):
        return None
    return staged


def explicit_operation(text):
    stripped=text.strip().casefold().strip(".!? ")
    m=LEAD.match(stripped)
    return (NAMES[m[1]],stripped[m.end():].strip()) if m else (None,None)


class GuidedBackend(PreviewBackend):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.guide=None
        self.notice=None
        self.reply_origin=None
        self.guided_frame=None

    def say(self,text,origin="host/guided-prompt"):
        self.notice=text
        if origin=="host/guided-prompt" and self.guide is not None and self.guide.learned:
            origin="learned-dialogue-act/host-guided-prompt"
        self.reply_origin=origin
        return Decision("guided_reply",None,0.,{},origin)

    def prompt(self):
        state=self.guide
        if state.request is None:
            question=MENU
        elif state.request.missing:
            question=state.request.ask()
        else:
            question="The inputs are ready."
        if state.request is not None and state.request.values:
            names={"a":"starting number" if state.request.action=="subtract" else "dividend" if state.request.action=="divide" else "first number",
                   "b":"amount to subtract" if state.request.action=="subtract" else "divisor" if state.request.action=="divide" else "second number",
                   "value":"amount","from":"starting unit","to":"target unit"}
            known=", ".join(f"{names[k]} {v}" for k,v in state.request.values.items())
            question=f"I have {known}. {question}"
        if state.suspended:
            return question+" When tools are enabled, say “go ahead” to run it."
        return question

    def complete(self,*,go=False):
        state=self.guide
        req=state.request
        if req is not None and {"from","to"}.issubset(req.values):
            source,target=req.values["from"],req.values["to"]
            if UNITS[source][0]!=UNITS[target][0]:
                del req.values["to"]
                return self.say(f"{source} and {target} measure different things. Choose a compatible target unit.")
        if req is None or req.missing or (state.suspended and not (go and self.session.permit_calls)):
            return self.say(self.prompt())
        if not self.session.permit_calls:
            state.suspended=True
            return self.say(self.prompt())
        try:
            proposal=req.proposal()
        except ValueError as error:
            req.values.clear()
            return self.say(f"Those inputs are invalid: {error}. {self.prompt()}")
        self.guided_frame=("learned-dialogue-act/guided-typed-serialization" if state.learned
                           else "host/guided-typed-serialization")
        self.guide=None
        return Decision("guided_call",proposal,0.,{},self.guided_frame)

    def decide(self,user,phase=0):
        if phase:
            if self.guided_frame:return Decision("done",None,0.,{},"host/guided-complete")
            return super().decide(user,phase)
        raw=user.strip()
        if raw in COMMANDS:
            self.guide=Guide(COMMANDS[raw], Request("convert") if raw=="/convert" else None)
            return self.say(self.prompt())
        if re.match(r"^/(?:calculate|convert|cancel)\b",raw,re.I) and not (self.guide and raw=="/cancel"):
            # A command with trailing prose never becomes a guided action.
            self.guide=None
            return self.say("To start a guided request, send /calculate or /convert by itself.")
        if self.guide is None:
            return super().decide(user,phase)
        state=self.guide
        if CANCEL.fullmatch(raw):
            self.guide=None
            return self.say("Cancelled. No tool was run.","host/guided-cancel")
        if SCOPE_SWITCH.search(raw) or operation(user) is not None:
            self.guide=None
            return super().decide(user,phase)
        if len(raw)>240 or any(c in raw for c in ('"','“','”','\n','\r')) or BLOCK.search(raw):
            self.guide=None
            return self.say("That input is ambiguous or outside the guided request. I cleared it without running a tool.")
        if NO_CALL.search(raw) or FORBID.search(raw):
            state.suspended=True
        if GO.fullmatch(raw):
            return self.complete(go=True)
        if NO_CALL.search(raw) or FORBID.search(raw):
            return self.say("The request is paused. "+self.prompt())
        if state.request is None:
            action,remainder=explicit_operation(raw)
            # Exact complete expressions or a natural language request in the explicitly
            # opened menu are eligible. Unrelated conversation still belongs to the preview.
            full=command(raw,[])
            if full and full.proposal and full.proposal["name"]=="calculate":
                action=full.proposal["arguments"]["op"]
                state.request=Request(action,{k:v for k,v in full.proposal["arguments"].items() if k!="op"})
                return self.complete()
            if action is None:
                action=classify(raw)
                if action in ("add","subtract","multiply","divide"):
                    state.learned=True
                    direct=re.sub(r"^(?:(?:i(?:'d| would) like to|i want to|can you|could you|please) +)+","",raw,flags=re.I)
                    named,rest=explicit_operation(direct)
                    remainder=rest if named==action else raw
                else:
                    pending_act=classify(raw,pending=True)
                    if pending_act=="cancel":
                        self.guide=None
                        return self.say("Cancelled. No tool was run.","learned-dialogue-act/host-guided-cancel")
                    if pending_act=="unrelated" and not slots(raw)[1] and not slots(raw)[2]:
                        self.guide=None
                        return super().decide(user,phase)
                    return self.say(MENU)
            if action not in ("add","subtract","multiply","divide"):
                return self.say(MENU)
            state.request=Request(action)
            if remainder:
                staged=apply_fields(state.request,remainder,opening=True,revision=False)
                if staged is not None:state.request=staged
            return self.complete()
        return self.collect_turn(raw,user)

    def collect_turn(self,raw,user):
        state=self.guide
        req=state.request
        cue=bool(REVISE.search(raw)) or bool(re.search(r"\bnot\b",raw,re.I))
        learned=classify(raw,pending=True)
        if learned=="cancel" and not cue:
            self.guide=None
            return self.say("Cancelled. No tool was run.","learned-dialogue-act/host-guided-cancel")
        field_text=raw
        if req.action=="convert":
            field_text=re.sub(r"^(?:please )?(?:convert|measure)\s+","",field_text,flags=re.I)
        # First try the literal field grammar; it cannot call a tool based only on
        # a classifier's confidence. Explicit corrections take precedence over supply.
        # Once all slots are filled, a further field value can only be an edit.
        # If it doesn't identify the previous field, clear values rather than keeping
        # a ready-but-obsolete call for a later go-ahead.
        editing_complete=not req.missing and bool(slots(raw)[1] or slots(raw)[2])
        field_words,values,units=slots(normalized_field(field_text))
        named_unit_edit=False
        if req.action=="convert" and len(units)==1:
            before=set(field_words[:units[0].position])
            key="from" if before & {"from","source","starting"} else "to" if before & {"to","into","as","in","target","destination"} else None
            named_unit_edit=key in req.values and req.values[key]!=units[0].value
        revision=cue or learned=="revise" or editing_complete or named_unit_edit
        staged=apply_fields(req,field_text,opening=False,revision=revision)
        if staged is not None:
            state.request=staged
            if learned=="revise" and not (cue or editing_complete or named_unit_edit):state.learned=True
            return self.complete()
        if revision:
            req.values.clear()
            return self.say("I couldn't resolve the correction, so I cleared the old inputs. "+self.prompt())
        if learned=="unrelated" or ((len(raw.split())>=9 or (not slots(raw)[1] and not slots(raw)[2])) and
                                    re.match(r"^(?:what|why|who|tell|how|write|explain|hello|hi|new topic)\b",raw,re.I)):
            self.guide=None
            return super().decide(user,0)
        return self.say("I couldn't use those inputs. "+self.prompt())

    def respond_ordinary(self,user,history_ids):
        if self.notice is None:return super().respond_ordinary(user,history_ids)
        head,body=encode_frame(self.tok,"assistant",{"text":self.notice})
        return Reply(json.dumps({"text":self.notice}),self.notice,None,head+body,self.reply_origin)

    def turn(self,*args,**kwargs):
        self.notice=self.reply_origin=self.guided_frame=None
        self.command_notice=self.reference_notice=self.readback_answer=None
        self.reference_call=False
        result=super().turn(*args,**kwargs)
        if self.guided_frame and result["trace"] and result["frame_origins"]:
            result["frame_origins"][0]=self.guided_frame
        if result["failure"]:self.guide=None
        return result


class Chat(PreviewChat):
    backend_class=GuidedBackend

    def turn(self,user,*args,**kwargs):
        if operation(user) is not None:self._chat.guide=None
        return super().turn(user,*args,**kwargs)
