"""Opt-in local product preview. One explicit display name lives only in this Chat instance."""
import json
import re
import unicodedata

from followon_product_chat import Chat as FollowonChat
from guards import ResourceStop
from local_chat import encode_frame

ORIGIN = "host/session-memory"
# The entire user utterance must be a name operation. A quoted example, additional
# instruction or hypothetical clause never becomes an assignment by substring search.
PREFIX = r"(?:(?:(?:hello|hi|hey)(?: there)?|good morning|good afternoon|good evening)[,.!]? +)?"
CHANGE = r"(?:(?:actually|correction|no)[,:]? +)?"
COURTESY = (r"(?:(?:(?:it is|it['’]s) +)?(?:nice|good|great|lovely) +to +meet +you(?: +too)?|"
            r"(?:a +pleasure|pleased|glad|happy) +to +meet +you|(?:it is|it['’]s) +a +pleasure +to +meet +you|"
            r"thank +you|thanks)")
COURTESY_END = re.compile(r"(.+?)(?:[.!]|,| +[—–]) +"+COURTESY,re.I)
ASSIGN = re.compile(
    PREFIX + "(?:"+COURTESY+r"[.!] +)?" + CHANGE + r"(?:please +)?(?:remember +(?:that +)?)?"
    r"(?:(?P<named>my (?:preferred )?name(?: is|['’]s))|(?P<call>(?:you (?:can|may) +)?call me)|"
    r"(?P<alias>I go by(?: the name(?: of)?)?)) +(?P<value>.+)", re.I)
SOCIAL_INTRO = re.compile(
    r"(?:(?:hello|hi|hey)(?: there)?|good morning|good afternoon|good evening)[,.!]? +"
    r"I(?:['’]m| am) +([^ ]+)", re.I)
CALL_QUALIFIER = re.compile(r",? +(?:instead|from now on)$",re.I)
RECALL = re.compile(
    r"(?:please +)?(?:what(?: is|['’]s) my (?:preferred )?name|what name did I (?:just )?give you|"
    r"what did I (?:just )?say my name (?:is|was)|(?:do|can) you remember my name|"
    r"what should you call me|(?:can you )?tell me my name)(?: (?:now|again|please))?", re.I)
FORGET = re.compile(r"(?:please +)?(?:forget my (?:preferred )?name|clear my saved name|stop remembering my name)", re.I)
PARTICLES = {"de","del","da","dos","du","van","von","bin","al","la"}
NON_NAMES = {
    "a","an","the","am","is","was","are","would","will","could","should","be","been",
    "my","me","your","you","he","she","they","it","it's","i","i'm","not","never","no",
    "if","when","unless","maybe","perhaps","either","or","and","but","instead","suppose",
    "pretend","example","unknown","unspecified","private","redacted","none","nobody",
    "someone","secret","confidential","back","later","tomorrow","tonight","soon","now",
    "please","at","by","on","only","then","next","before","after","hypothetical",
    "his","her","their","our","them","him","hers","mine","monday","tuesday","wednesday",
    "thursday","friday","saturday","sunday","today","yesterday","daily","again",
    "any","anything","anyone","anybody","whatever","whomever","whichever","something",
    "some","sometimes","different","another","many","several","name","names","nickname",
    "nicknames","because","which","until","occasionally","usually","maybe","as","for",
    "that","this","first","middle","last","real","same","old","new","else","elsewhere",
    "anonymous","nothing","everything","whenever","whoever","everyone","every","each",
    "other","others","aliases","pronoun","pronouns","title","titles","role","roles",
    "doctor","dr","nurse","therapist","teacher","professor","prof","engineer","manager",
    "patient","pregnant","diabetic","sick","ill","disabled","mother","father","daughter",
    "son","sister","brother","husband","wife","friend","coworker","someone's","someone’s",
}

TRAVEL_OR_RULE = {"bus","tram","train","car","taxi","plane","boat","bike","bicycle","foot","road",
                  "rail","ferry","instinct","instincts","intuition","rule","rules","book","evidence",
                  "schedule","guesswork","experience","plans"}
# A greeting followed by “I’m X” also describes identities, occupations and states.
# Only accept the narrow single-name reading with a meeting courtesy; decline
# ordinary descriptors and productive role/adjective endings in that form.
AMBIGUOUS_SELF = {
    "mom","mum","dad","parent","child","kid","minor","adult","elderly","teen","student","pupil",
    "officer","police","clergy","rabbi","imam","priest","nun","clerk","coach","chef","pilot",
    "judge","vet","medic","admin","staff","intern","boss","chief","lead","guest","host",
    "bipolar","adhd","hiv","ptsd","cancer","blind","deaf","queer","gay","trans","straight",
    "jewish","hindu","muslim","catholic","christian","sikh","black","white","asian","male",
    "female","woman","man","nonbinary","single","married","divorced","widow","poor","rich",
    "injured","tired","fine","okay","happy","sad","well","here","ready","new","unsure",
}
DESCRIPTOR_ENDINGS=("ist","ism","ician","ian","ese","ing","ed","ive","ous","less","ful","ic","ant","ent","er","or")


def plausible_alias(value):
    if not valid_name(value):
        return False
    first=value[0]
    if (first.lower()!=first.upper() and not first.isupper()) or value.isupper():
        return False
    return all(w.casefold() not in TRAVEL_OR_RULE|AMBIGUOUS_SELF for w in re.split("[-'’ ]",value))


def valid_name(value):
    if not 1 <= len(value) <= 64:
        return False
    words = value.split(" ")
    if not 1 <= len(words) <= 4 or any(not word or word.casefold() in NON_NAMES for word in words):
        return False
    for i,word in enumerate(words):
        if word.casefold().endswith(("'s","’s")):
            return False
        for part in re.split("[-'’]",word):
            if not part or part.casefold() in NON_NAMES or not part[0].isalpha() or any(
                not ch.isalpha() and not unicodedata.category(ch).startswith("M") for ch in part
            ):
                return False
        uncased = word[0].lower() == word[0].upper()
        interior_particle = 0 < i < len(words)-1 and word.casefold() in PARTICLES
        if len(words)>1 and not (uncased or word[0].isupper() or interior_particle):
            return False
    return True


def operation(user):
    if not isinstance(user,str) or len(user)>150 or any(not ch.isprintable() for ch in user):
        return None
    text = user.strip()
    if not text:
        return None
    statement = text[:-1].rstrip() if text[-1] in ".!" else text
    question = text[:-1].rstrip() if text[-1] in ".?!" else text
    if RECALL.fullmatch(question):
        return "recall",None
    if FORGET.fullmatch(statement):
        return "forget",None
    courtesy=COURTESY_END.fullmatch(statement)
    main=courtesy[1] if courtesy else statement
    if courtesy and "meet" in statement[len(main):].casefold():
        intro=SOCIAL_INTRO.fullmatch(main)
        if intro and plausible_alias(intro[1]) and not intro[1].casefold().endswith(DESCRIPTOR_ENDINGS):
            return "set",intro[1]
    match=ASSIGN.fullmatch(main)
    if match:
        value=match["value"]
        if match["call"]:
            value=CALL_QUALIFIER.sub("",value)
        if match["alias"]:
            # “I go by” also describes travel or a decision rule. Bare lowercase
            # terms and acronyms are too ambiguous for this alias construction.
            if not plausible_alias(value):
                return None
        if valid_name(value):
            return "set",value
    return None


def folded(text):
    return unicodedata.normalize("NFKC",text).casefold()


class Chat:
    """Keep an accurate visible history and a separate model-facing context after forgetting."""
    backend_class=None

    def __init__(self,model,tok,guard,reader=None):
        backend=self.backend_class or FollowonChat
        self._chat=backend(model,tok,guard,reader=reader)
        self.tok,self.guard,self.model=tok,guard,model
        self.session=self._chat.session
        self.history=[]
        self._chunks=[]
        self._name=None

    @property
    def ids(self):
        return self._chat.ids

    def _remember_turn(self,start):
        entry=self._chat.history[-1]
        self.history.append(entry)
        self._chunks.append((entry,self.ids[start:]))

    def _forget_context(self, space):
        # Past names are derived only from explicit host assignments in this chat.
        names={folded(op[1]) for entry,_ in self._chunks
               if entry.get("memory_action")=="set" and (op:=operation(entry["user"])) and op[1]}
        kept=[(entry,ids) for entry,ids in self._chunks
              if entry.get("selected_path")!=ORIGIN and
              not any(name in folded(json.dumps(entry,ensure_ascii=False)) for name in names)]
        # A forget operation is always possible within the model's context: evict
        # whole oldest turns if its acknowledgment would otherwise exceed the limit.
        size=sum(len(ids) for _,ids in kept)
        while kept and size>space:
            size-=len(kept.pop(0)[1])
        self._chunks=kept
        self._chat.ids=[token for _,ids in kept for token in ids]
        self._chat.history=[entry for entry,_ in kept]
        self._name=None

    def turn(self,user,permit_calls=True,fixture_for=None,fixture=None):
        op=operation(user)
        if op is None:
            start=len(self.ids)
            result=self._chat.turn(user,permit_calls,fixture_for,fixture)
            self._remember_turn(start)
            return result
        kind,value=op
        result=dict(answer=None,frames=[],frame_origins=[],trace=[],failure=None,decision=None,
                    decisions=[],selected_path=ORIGIN,copy_prompt=None,memory_action=kind)
        self.session.start_turn(permit_calls=False)
        start=len(self.ids)
        try:
            self.guard.check()
            if kind=="set":
                answer=f"Hello, {value}." if self._name is None else f"I’ll call you {value}."
            elif kind=="recall":
                answer=f"Your name is {self._name}." if self._name is not None else "I don’t have a saved name for you in this chat."
            else:
                answer="I’ve cleared the saved name for this chat."
            user_header,user_body=encode_frame(self.tok,"user",user)
            answer_header,answer_body=encode_frame(self.tok,"assistant",{"text":answer})
            tokens=user_header+user_body+answer_header+answer_body
            capacity=self.model.positions.num_embeddings
            if kind=="forget" and len(tokens)<=capacity:
                self._forget_context(capacity-len(tokens))
                start=len(self.ids)
            if start+len(tokens)>capacity:
                raise ValueError("conversation exceeds model context")
            if kind=="set":
                self._name=value
            self._chat.ids.extend(tokens)
            result.update(answer=answer,frames=[self.tok.decode(answer_body[:-1])],frame_origins=[ORIGIN])
        except (ResourceStop,ValueError) as error:
            result["failure"]=str(error)
        self._chat.history.append(dict(user=user,permit_calls=False,**result))
        self._remember_turn(start)
        return result
