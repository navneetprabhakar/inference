"""Preview-only closed calculator/converter command grammar and transparent abstention."""
from dataclasses import dataclass
import json
import re

from fallback_chat import Reply
from fallback_head import Decision, UNIT_ALIASES, parse
from followon_head_v2 import normalized_words
from local_chat import encode_frame
from reference_ops_head import REFERENCE
from tools import UNITS, validate_arguments


@dataclass(frozen=True)
class Command:
    proposal: dict | None = None
    notice: str | None = None
    informational: bool = False
    followup: str | None = None


PREFIX = re.compile(r'^(?:(?:could|would|can) you\s+)?(?:please\s+)?(?:now\s+)?',re.I)
SUFFIX = re.compile(r'(?:,?\s+(?:please|(?:using|with) (?:the |a )?(?:offline )?(?:calculator|converter)))$',re.I)
OPS = (
    ('add',False,r'add (.+?) (?:and|to) (.+)'),
    ('subtract',True,r'subtract (.+?) from (.+)'),
    ('multiply',False,r'multiply (.+?) (?:by|and) (.+)'),
    ('divide',False,r'divide (.+?) by (.+)'),
)
SYMBOLS={'+':'add','-':'subtract','*':'multiply','×':'multiply','/':'divide','÷':'divide'}
NUMBER = re.compile(r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)')
WORD_NUMBER = re.compile(r'[a-z]+(?:[- ][a-z]+)*')
CONVERT = re.compile(r'convert (.+?) (?:into|to) ([a-z]+(?: [a-z]+){0,2})')
NONCOMMAND = re.compile(r"^(?:(?:please )?(?:do not|don’t|don't|never|avoid)|if|suppose|imagine|hypothetically|quote|is|was|were)\b",re.I)
TOOL_LEAD=re.compile(r"^(?:(?:use|ask) (?:the |a )?(?:offline |local )?(?:calculator|converter) (?:to |for ))")
AUTH_LEAD=re.compile(r"^(?:tools (?:are|are now)|(?:the )?calculator is(?: now)?) (enabled|disabled|on|off)(?: now)?(?: for (?:this|the current) (?:turn|message))?[.!;] +")
DISPLAY_TAIL=re.compile(r"[.!?] +(?:what remains|what is left|how many (?:remain|are left)|tell me the remainder|give me (?:the|just the) result)$")
SUBTRACT_FORMS=(
    (r"(?:subtract|deduct|remove) (.+?) from (.+)",True),
    (r"take (.+?) (?:(?:away )?from|off) (.+)",True),
    (r"(?:calculate|compute|what is) (.+?) minus (.+)",False),
)
ORDER_NOTICE="Please specify the starting amount and the amount to subtract from it."
LIVE_QUERY=re.compile(r"^(?:can|could|do) (?:your|these|the|our) (?:available |offline |local )?tools (?:look up|fetch|check|retrieve|get|access|report) (?:the |a |any )?(?:next|live|latest|current|online|external|real[- ]time)\b")
LIVE_FOLLOW=re.compile(r"^did (?:a|any|the) live [a-z ]{1,50} (?:come back|arrive) (?:in this chat|from (?:a|your|the) tool)$")
STATUS_TAIL=re.compile(r"[.!;] +tools are (?:disabled|off)(?: for this (?:turn|message))?$")
EXPRESSION=re.compile(r"^(?:(?:keep (?:the |this )?calculation unevaluated|without (?:using|calling) (?:any )?tools?)[:,;.] +)?(?:please +)?(?:write|show|give) (?:only +)?(?:the|an) (?:unevaluated )?(?:subtraction )?expression for (.+)$")
QUANTITY_AMBIGUITY={"or","either","rather","than","about","approximately","approx","up","minimum",
                    "maximum","least","most","before","after","if","unless","not","unknown","smaller",
                    "larger","other","relevant","each","per","half","double","twice","percent","then",
                    "add","divide","multiply","plus","minus","less","subtract","and","versus","between"}
LATEST_MISSING='There is no successful result from the latest call to use.'


def number(text):
    if NUMBER.fullmatch(text):
        return float(text) if '.' in text else int(text)
    if WORD_NUMBER.fullmatch(text):
        words,spans=parse(normalized_words(text),None)
        if words==['#'] and len(spans)==1:
            return spans[0].value
    return None


def operand(text):
    actual=re.fullmatch(r"(?:(?:the|that|its) )?(?:observed|returned|previous|last|latest) (?:amount|sum|quantity|reading)",text)
    return 'latest' if REFERENCE.fullmatch(text) or actual else number(text)


def validated(name,args):
    try:
        validate_arguments(name,args)
    except ValueError as exc:
        return Command(notice=f'The requested {name} arguments are invalid: {exc}.')
    return Command(proposal={'name':name,'arguments':args})


def quantity(text):
    """Return one typed amount and its unit, never select one number out of several."""
    exact=operand(text)
    if exact is not None:
        return exact,None
    if len(text)>80 or not re.fullmatch(r"[a-z0-9 +.,−-]+",text):
        return None,None
    if re.search(r"(?<!\d)\.|\.(?!\d)|(?<!\d),|,(?!\d{3}\b)|\d[a-z]|[a-z]\d",text):
        return None,None
    words,spans=parse(normalized_words(text),None)
    numbers=[s.value for s in spans if s.kind=="number"]
    units=[s.value for s in spans if s.kind=="unit"]
    if len(words)>12 or len(numbers)!=1 or len(units)>1 or QUANTITY_AMBIGUITY.intersection(words):
        return None,None
    return numbers[0],units[0] if units else None


def ordered_subtraction(text,trace):
    for pattern,reverse in SUBTRACT_FORMS:
        match=re.fullmatch(pattern,text)
        if not match:
            continue
        words,spans=parse(normalized_words(text),None)
        if not spans and not REFERENCE.search(text) and not any(w in words for w in ("amount","estimate","operand","quantity")):
            return None
        parsed=[quantity(part.strip()) for part in match.groups()]
        (a,unit_a),(b,unit_b)=reversed(parsed) if reverse else parsed
        if a is None or b is None or a==b=="latest" or unit_a!=unit_b:
            return Command(notice=ORDER_NOTICE)
        if "latest" in (a,b):
            if not trace or not trace[-1]["ok"]:
                return Command(notice=LATEST_MISSING)
            prior=trace[-1]["data"]["result"]
            a=prior if a=="latest" else a
            b=prior if b=="latest" else b
        return validated("calculate",{"op":"subtract","a":a,"b":b})
    if re.match(r"(?:find |take |calculate |compute |what is )?(?:the )?(?:signed )?difference between\b",text):
        return Command(notice=ORDER_NOTICE)
    if re.search(r"(?:^|[.!?;] +)(?:please +)?(?:subtract|deduct)\b",text) and (parse(text,None)[1] or "amount" in text):
        return Command(notice=ORDER_NOTICE)
    return None


def expression_notice(text):
    match=EXPRESSION.fullmatch(STATUS_TAIL.sub("",text))
    if not match:return None
    parts=re.fullmatch(r"(.+?) (minus|less|plus|times|divided by) (.+)",match[1])
    if parts:
        a,b=number(parts[1]),number(parts[3])
        if a is not None and b is not None:
            symbol={"minus":"−","less":"−","plus":"+","times":"×","divided by":"÷"}[parts[2]]
            return Command(notice=f"{a} {symbol} {b}",informational=True)
    return Command(notice="No tool was run. Please give two explicit operands in the requested order.",informational=True)


def command(user,trace):
    if len(user)>240:
        return None
    text=' '.join(user.casefold().replace("−","-").strip().rstrip('.?!').split())
    expression=expression_notice(text)
    if expression:return expression
    if LIVE_QUERY.match(text) or LIVE_FOLLOW.fullmatch(text):
        return Command(notice="Only the offline calculator and unit converter are available. No live lookup was performed.",informational=True)
    auth=AUTH_LEAD.match(text)
    if auth:
        if auth[1] in ("disabled","off"):
            return Command(notice="This turn does not permit a new tool call.",informational=True)
        text=text[auth.end():]
    text=TOOL_LEAD.sub('',PREFIX.sub('',text))
    text=DISPLAY_TAIL.sub('',text)
    # Strip only standalone presentation/courtesy phrases after a complete command.
    text=SUFFIX.sub('',SUFFIX.sub('',text)).strip()
    # Leave multi-step dispatch to the existing planner. Validate a subtraction
    # against its own clause when the planner reaches that phase.
    if re.search(r"\b(?:add|multiply|divide|convert|total|sum)\b.+?\b(?:then|next)\b",text):
        parts=re.split(r"\b(?:then|next)\b[:,]? +",text)
        if len(parts)!=2:return None
        second=ordered_subtraction(DISPLAY_TAIL.sub("",parts[1]),[])
        if second is None:return None
        if second.proposal is None and second.notice!=LATEST_MISSING:return second
        first=re.sub(r"^(?:first +)?","",parts[0].strip(" ,.;"))
        preceding=command(first,trace)
        if preceding is None or preceding.proposal is None:
            return Command(notice="Please specify the first operation and the amounts for the subsequent subtraction.")
        return Command(proposal=preceding.proposal,followup=parts[1])
    sub=ordered_subtraction(text,trace)
    if sub:return sub
    conversion=CONVERT.fullmatch(text)
    if conversion:
        quantity_with_unit,target=conversion.groups()
        words=quantity_with_unit.split()
        for i in range(len(words)-1,0,-1):
            value=operand(' '.join(words[:i]))
            source=' '.join(words[i:])
            if value is not None and re.fullmatch(r'[a-z]+(?: [a-z]+){0,2}',source):
                break
        else:
            return None
        for unit in (source,target):
            if unit not in UNIT_ALIASES:
                return Command(notice=f'Unsupported conversion unit: {unit}.')
        source,target=UNIT_ALIASES[source],UNIT_ALIASES[target]
        if UNITS[source][0]!=UNITS[target][0]:
            return Command(notice=f'{source} and {target} are incompatible units ({UNITS[source][0]} and {UNITS[target][0]}).')
        if value=='latest':
            if not trace or not trace[-1]['ok']:
                return Command(notice=LATEST_MISSING)
            value=trace[-1]['data']['result']
        return validated('convert',{'value':value,'from':source,'to':target})
    def unresolved():
        # A tool-like verb alone does not establish an arithmetic request
        # (e.g. adding a name to a list or converting an image).
        if re.match(r'(?:calculate|compute|add|subtract|multiply|divide|convert)\b',text):
            words,_=parse(text,None)
            if '#' in words or REFERENCE.search(text):
                return Command(notice='Please specify one operation with its operands, or one amount and both conversion units.')
        return None

    for op,reverse,pattern in OPS:
        match=re.fullmatch(pattern,text)
        if match:
            a,b=map(operand,match.groups())
            if reverse:
                a,b=b,a
            break
    else:
        expr=re.fullmatch(r'(?:calculate|compute|what is) (.+?)\s*([+*/×÷-])\s*(.+)',text)
        if not expr:
            return unresolved()
        a,b=operand(expr[1].strip()),operand(expr[3].strip())
        op=SYMBOLS[expr[2]]
    if a is None or b is None or a==b=='latest':
        return unresolved()
    if 'latest' in (a,b):
        if not trace or not trace[-1]['ok']:
            return Command(notice=LATEST_MISSING)
        prior=trace[-1]['data']['result']
        a=prior if a=='latest' else a
        b=prior if b=='latest' else b
    return validated('calculate',{'op':op,'a':a,'b':b})


class ExplicitCommands:
    """Mixin ahead of the accepted preview backend. Its own layer changes no learned state."""
    def _subtraction_notice(self):
        self.reference_call=False
        self.reference_notice=self.readback_answer=None
        self.command_notice=ORDER_NOTICE
        return Decision("command_abstain",None,0.,{},"host/unresolved-subtraction-order")

    def decide(self,user,phase=0):
        if phase:
            if getattr(self,'command_completed',False):
                return Decision('done',None,0.,{},'host/explicit-command-complete')
            decision=super().decide(user,phase)
            parts=re.split(r"\b(?:then|next)\b[:,]? +"," ".join(user.casefold().split()).rstrip(".!?"))
            parsed=ordered_subtraction(DISPLAY_TAIL.sub("",parts[1]),self.session.trace) if len(parts)==2 else None
            if parsed is not None:
                if parsed.proposal is None or not self.session.permit_calls:
                    return self._subtraction_notice()
                if parsed.proposal==decision.proposal:
                    return decision
                self.reference_call=False
                self.reference_notice=self.readback_answer=None
                self.host_command_frames.append(phase)
                return Decision("calculate",parsed.proposal,0.,{},"host/explicit-command")
            if decision.proposal and decision.proposal.get("arguments",{}).get("op")=="subtract":
                return self._subtraction_notice()
            return decision
        self.command_completed=False
        self.command_notice=None
        self.host_command_frames=[]
        parsed=command(user,self.session.trace)
        if parsed is None:
            decision=super().decide(user,phase)
            if decision.proposal and NONCOMMAND.match(user.strip()):
                # A hypothetical, comparison or prohibition cannot authorize the
                # ambiguous tool proposal. Explain why no call was made.
                self.reference_call=False
                self.reference_notice=self.readback_answer=None
                self.command_notice='No tool was run. To request a calculation, give a direct command.'
                return Decision('command_abstain',None,0.,{},'host/non-command-tool-veto')
            if decision.proposal and not self.session.permit_calls:
                self.reference_call=False
                self.reference_notice=self.readback_answer=None
                self.command_notice='This turn does not permit a new tool call.'
                return Decision('command_abstain',None,0.,{},'host/explicit-command-notice')
            directional=re.search(r"\b(?:subtract(?:ion|ing)?|deduct(?:ion|ing)?|minus|difference between)\b",user.casefold())
            if (decision.proposal and not self.reference_call and (
                    decision.proposal.get("arguments",{}).get("op")=="subtract" or
                    (directional and (parse(normalized_words(user),None)[1] or REFERENCE.search(user))))):
                return self._subtraction_notice()
            return decision
        self.reference_call=False
        self.reference_notice=self.readback_answer=None
        if parsed.informational:
            self.command_notice=parsed.notice
        elif not self.session.permit_calls:
            self.command_notice='This turn does not permit a new tool call.'
        elif parsed.notice:
            self.command_notice=parsed.notice
        if self.command_notice:
            return Decision('command_abstain',None,0.,{},'host/explicit-command-notice')
        # Preserve a learned proposal when it agrees on tool and all typed operands.
        decision=super().decide(user,phase)
        self.command_completed=parsed.followup is None
        if decision.proposal==parsed.proposal:
            return decision
        self.reference_call=False
        self.reference_notice=self.readback_answer=None
        self.host_command_frames.append(phase)
        return Decision(parsed.proposal['name'],parsed.proposal,0.,{},'host/explicit-command')

    def _notice_reply(self):
        answer=self.command_notice
        prefix,body=encode_frame(self.tok,'assistant',{'text':answer})
        return Reply(json.dumps({'text':answer}),answer,None,prefix+body,'host/explicit-command-notice')

    def respond_ordinary(self,user,history_ids):
        return self._notice_reply() if self.command_notice else super().respond_ordinary(user,history_ids)

    def respond_number(self,record):
        # A verified first result may exist even when the second requested step
        # needs clarification. Never present the intermediate value as the final answer.
        return (self._notice_reply(),None) if self.command_notice else super().respond_number(record)

    def turn(self,*args,**kwargs):
        self.host_command_frames=[]
        result=super().turn(*args,**kwargs)
        for index in self.host_command_frames:
            if index<len(result['frame_origins']):
                result['frame_origins'][index]='host/explicit-command-serialization'
        return result
