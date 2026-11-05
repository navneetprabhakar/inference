"""CPU lexical intent classifier and learned copy ranker for the offline tool schema."""
from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
import json
import math
import re
from pathlib import Path

import torch
from torch import nn
from torch.nn import functional as F

from tools import MAX_NUMBER, UNITS, validate_arguments

ROOT = Path(__file__).resolve().parent
RECEIPT = ROOT / "reports/working-chat/head.json"
ACTIONS = ("text", "recall_number", "recall_unit", "add", "subtract", "multiply", "divide", "convert")
NUMBER_WORDS = dict(zip("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(), range(20)))
TENS = dict(zip("twenty thirty forty fifty sixty seventy eighty ninety".split(), range(20, 100, 10)))
UNIT_WORDS = {
    "mm":"millimeter millimetre", "cm":"centimeter centimetre", "m":"meter metre",
    "km":"kilometer kilometre", "g":"gram gramme", "kg":"kilogram kilogramme",
    "ml":"milliliter millilitre", "l":"liter litre", "s":"second sec",
    "min":"minute", "h":"hour hr", "day":"day",
}
UNIT_ALIASES = {alias: code for code, words in UNIT_WORDS.items()
                for word in words.split() for alias in (word, word+"s")}
UNIT_ALIASES.update({code: code for code in UNITS})
LEX = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+|[a-z]+|[+*/×÷=−-]")
DIGITS = re.compile(r"(?:\d[\d,]*(?:\.\d+)?|\.\d+)$")


@dataclass(frozen=True)
class Span:
    value: object
    kind: str
    position: int
    source: str


def numeral(tokens, i):
    """Parse a contiguous ordinary English cardinal; don't merge 'two and three'."""
    if i >= len(tokens):
        return None
    if tokens[i] in TENS:
        value = TENS[tokens[i]]
        end = i + 1
        if end < len(tokens) and tokens[end] == "-":
            end += 1
        if end < len(tokens) and tokens[end] in NUMBER_WORDS and NUMBER_WORDS[tokens[end]] < 10:
            return value + NUMBER_WORDS[tokens[end]], end + 1
        return value, i + 1
    if tokens[i] in NUMBER_WORDS:
        value = NUMBER_WORDS[tokens[i]]
        end = i + 1
        if end < len(tokens) and tokens[end] == "hundred":
            value *= 100
            end += 1
            next_word = end + 1 if tokens[end:end+1] == ["and"] else end
            tail = numeral(tokens, next_word)
            if tail and tail[0] < 100:
                value += tail[0]
                end = tail[1]
        return value, end
    return None


def parse(user, last):
    pieces = list(LEX.finditer(user.casefold()))
    words = [m.group() for m in pieces]
    sequence, spans = [], []
    i = 0
    while i < len(words):
        word, start = words[i], i
        negative = (word == "negative" or
                    (word in ("-", "−", "minus") and sequence[-1:] != ["#"] and
                     (word == "minus" or (i+1 < len(words) and pieces[i].end() == pieces[i+1].start()))))
        number_at = i + int(negative)
        numeric = None
        if number_at < len(words) and DIGITS.fullmatch(words[number_at]):
            amount = words[number_at].replace(",", "")
            value = float(amount) if "." in amount or len(amount)>30 else int(amount)
            numeric = value, number_at+1
        elif number_at < len(words):
            numeric = numeral(words, number_at)
        if numeric is not None:
            value, end = numeric
            spans.append(Span(-value if negative else value, "number", len(sequence), "user"))
            sequence.append("#")
            i = end
        elif word in UNIT_ALIASES:
            spans.append(Span(UNIT_ALIASES[word], "unit", len(sequence), "user"))
            sequence.append("@")
            i += 1
        else:
            sequence.append(word)
            i = start + 1
    if last and last.get("ok"):
        value = last["data"]["result"]
        if type(value) in (int, float) and math.isfinite(value):
            spans.append(Span(value, "number", -1, "last-result"))
    return sequence, spans


def lexical(words, spans, last):
    features = {"bias", "prior="+(last.get("name", "failed") if last else "none")}
    numbers = sum(s.kind == "number" and s.source == "user" for s in spans)
    units = sum(s.kind == "unit" for s in spans)
    features.update([f"numbers={min(numbers,3)}", f"units={min(units,3)}"])
    for i, word in enumerate(words):
        features.add("w:"+word)
        if len(word) > 3:
            features.update("c:"+word[j:j+3] for j in range(len(word)-2))
        if i:
            features.add("p:"+words[i-1]+" "+word)
    return tuple(sorted(features))


def pointer(words, candidates, rank, action, slot):
    span = candidates[rank]
    role = action+"/"+slot
    position = str(rank) if span.source == "user" else "prior"
    prefix = role+":"+position+":"
    features = {"bias", prefix+"position", role+":"+span.source, prefix+"count="+str(len(candidates))}
    # Condition position on the wording, e.g. "from" reverses some operand orders.
    for word in set(words):
        features.add(prefix+"word="+word)
    if span.position >= 0:
        for delta in (-2,-1,1,2):
            index = span.position+delta
            if 0 <= index < len(words):
                features.add(role+":"+str(delta)+"="+words[index])
    return tuple(sorted(features))


class BagModel:
    """An additive lexical softmax. No pretrained features or parameters."""
    def __init__(self, vocabulary, weights):
        self.vocab = {term:i for i,term in enumerate(vocabulary)}
        self.weights = weights

    def scores(self, features):
        indices = [self.vocab[term] for term in features if term in self.vocab]
        if not indices:
            return torch.zeros(self.weights.shape[1])
        return self.weights[indices].sum(0) / math.sqrt(len(indices))

    @classmethod
    def fit(cls, examples, classes, seed):
        vocabulary = sorted({term for features, _ in examples for term in features})
        index = {term:i for i,term in enumerate(vocabulary)}
        texts, labels, counts = [], [], []
        for (features, label), count in examples.items():
            texts.append(torch.tensor([index[t] for t in features], dtype=torch.long))
            labels.append(label)
            counts.append(math.sqrt(count))
        labels = torch.tensor(labels)
        counts = torch.tensor(counts)
        by_class = torch.zeros(classes).scatter_add_(0, labels, counts)
        weights = counts / by_class[labels].sqrt()
        net = nn.EmbeddingBag(len(vocabulary), classes, mode="sum")
        nn.init.zeros_(net.weight)
        opt = torch.optim.Adam(net.parameters(), lr=.025, weight_decay=.0001)
        rng = torch.Generator().manual_seed(seed)
        for _ in range(22):
            for batch in torch.randperm(len(texts), generator=rng).split(96):
                rows = [texts[i] for i in batch.tolist()]
                sizes = torch.tensor([len(row) for row in rows])
                offsets = torch.cat([torch.tensor([0]),sizes.cumsum(0)[:-1]])
                scores = net(torch.cat(rows), offsets) / sizes.sqrt()[:,None]
                per_row = F.cross_entropy(scores, labels[batch], reduction="none")
                loss = (per_row*weights[batch]).sum()/weights[batch].sum()
                opt.zero_grad(set_to_none=True)
                loss.backward()
                opt.step()
        return cls(vocabulary, net.weight.detach().clone())

    def state(self):
        return dict(vocabulary=list(self.vocab), weights=self.weights)


@dataclass
class Decision:
    action: str
    proposal: dict | None
    margin: float
    slots: dict
    reason: str | None = None


def requested_slots(action):
    return (("value","number"),("from","unit"),("to","unit")) if action == "convert" else (("a","number"),("b","number"))


class Head:
    def __init__(self, routes, ranker):
        self.routes, self.ranker = routes, ranker

    def decide(self, user, trace):
        last = trace[-1] if trace else None
        words, spans = parse(user, last)
        scores = self.routes.scores(lexical(words, spans, last))
        top, runner = torch.argsort(scores, descending=True)[:2].tolist()
        action = ACTIONS[top]
        decision = Decision(action, None, float(scores[top]-scores[runner]), {})
        if action in ("text","recall_number","recall_unit"):
            return decision
        if len(spans)>32 or any(s.kind=="number" and
                                (not math.isfinite(s.value) or abs(s.value)>MAX_NUMBER) for s in spans):
            decision.reason = "quantity count or value outside supported bounds"
            return decision
        chosen = {}
        wanted = requested_slots(action)
        for kind in {kind for _, kind in wanted}:
            names = [name for name, k in wanted if kind == k]
            candidates = [s for s in spans if s.kind == kind]
            if len(candidates) < len(names):
                decision.reason = "insufficient typed spans"
                return decision
            rankings = []
            for name in names:
                values = []
                for rank in range(len(candidates)):
                    logits = self.ranker.scores(pointer(words,candidates,rank,action,name))
                    values.append(float(logits[1]-logits[0]))
                rankings.append(values)
            if len(names)==1:
                picks = (max(range(len(candidates)), key=rankings[0].__getitem__),)
            else:
                # Each slot points to a distinct span. Equal values may appear twice.
                picks = max(((i,j) for i in range(len(candidates)) for j in range(len(candidates)) if i != j),
                            key=lambda ij: rankings[0][ij[0]]+rankings[1][ij[1]])
            for name,i in zip(names,picks):
                chosen[name] = candidates[i].value
                decision.slots[name] = asdict(candidates[i])
        tool = "convert" if action=="convert" else "calculate"
        if tool == "calculate":
            chosen["op"] = action
        try:
            validate_arguments(tool, chosen)
        except ValueError as error:
            decision.reason = str(error)
            return decision
        decision.proposal = dict(name=tool, arguments=chosen)
        return decision


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@lru_cache(maxsize=1)
def load_head():
    receipt = json.loads(RECEIPT.read_text())
    file = ROOT / receipt["weights"]
    if sha(file) != receipt["sha256"]:
        raise ValueError("Fallback head checksum mismatch")
    data = torch.load(file, map_location="cpu", weights_only=True)
    if data["actions"] != list(ACTIONS):
        raise ValueError("Fallback action schema mismatch")
    return Head(BagModel(**data["routes"]), BagModel(**data["ranker"]))
