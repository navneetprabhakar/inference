"""CPU-only supervised exemplar classifier with conservative scope and typed rendering."""
from collections import Counter, defaultdict
from hashlib import sha256
from math import log, sqrt
import json
import re

NUM = re.compile(r'(?<![\w.])[+-]?(?:\d+\.\d+|\d+)(?![\w.])')
TOK = re.compile(r'#|[a-z]+')
STOP = set('the what did was were is it to which in that of we me my you your please tell last again from with an there do a us this can could just for on after time one more thing'.split()) - {'a', 'from', 'to'}
UNSAFE = re.compile(r'\b(if|instead|next|would|should|will|could have|and|or|not|never|than or equal|at least|at most|first result|earlier|before last|plus|times|minus|multiply|divide|double|halve|subtract|add)\b', re.I)
UNSUPPORTED_NUM = re.compile(r'\d[,/%:]|[\d.]\s*[eE][+-]?\d|\.\d|\d\.(?!\d)(?=\w)')


def features(user):
    words = TOK.findall(NUM.sub('#', user.lower()))
    content = [w for w in words if w not in STOP]
    return set(content) | {'~'+a+' '+b for a,b in zip(content,content[1:])}


def fit(rows):
    """Learn inverse document frequencies and labeled exemplars from approved text only."""
    examples = {(row['label'],tuple(sorted(features(row['user'])))) for row in rows}
    counts = Counter(f for _, fs in examples for f in fs)
    return {'idf':{f: 1+log((len(examples)+1)/(count+1)) for f,count in counts.items()},
            'examples': sorted(examples)}


class Head:
    def __init__(self, state):
        self.idf = state['idf']
        self.examples = [(label,set(fs), self.norm(fs)) for label,fs in state['examples']]

    def norm(self, fs):
        return sqrt(sum(self.idf.get(f,3)**2 for f in fs))

    def decide(self, user):
        if len(user)>300 or UNSAFE.search(user):
            return None
        fs = features(user)
        # Abstain on novel subject matter. Allow only neutral courtesy/time words
        # and inflections of training words; this deliberately costs recall.
        neutral = {'remind','now','our','as','use','used','give','read','back','that','returned'}
        for word in fs:
            if word.startswith('~') or word in self.idf or word in neutral:
                continue
            if not any(stem in self.idf for stem in (word.removesuffix('ed'),word.removesuffix('s'),word.removesuffix('ing'))):
                return None
        norm = self.norm(fs)
        if not norm:
            return None
        scores = defaultdict(float)
        for label, ex, den in self.examples:
            if den:
                sim = sum(self.idf[f]**2 for f in fs & ex)/(norm*den)
                scores[label] = max(scores[label],sim)
        order = sorted(scores,key=scores.get,reverse=True)
        if len(order)<2 or scores[order[0]]<0.46 or scores[order[0]]-scores[order[1]]<0.10:
            return None
        label = order[0]
        if label=='defer':
            return None
        numbers = NUM.findall(user)
        if numbers and label not in ('gt','eq','lt'):
            return None
        if label in ('gt','eq','lt') and (len(numbers)!=1 or UNSUPPORTED_NUM.search(user.replace(numbers[0], '',1)) or re.search(r'[,/%:]|\d[eE]',user)):
            return None
        return label


def render(label, event, user):
    if not event or not label:
        return None
    name = event.get('name')
    args = event.get('arguments',{})
    if label=='tool':
        return name
    if label=='status':
        return 'The call succeeded.' if event['ok'] else 'The call failed: '+event['error']
    if not event['ok']:
        if label in ('result','gt','lt','eq','positive','negative','zero'):
            return 'No result. The call failed: '+event['error']
        return None
    result = event['data']['result']
    if label=='result':
        value=result
    elif label in ('a','b','amount','source','target'):
        key={'amount':'value','source':'from','target':'to'}.get(label,label)
        if key not in args:
            return None
        value=args[key]
    else:
        if label in ('positive','negative','zero'):
            threshold=0
        else:
            numbers=NUM.findall(user)
            if len(numbers)!=1:
                return None
            threshold=float(numbers[0])
        verdict={'positive': result>threshold, 'gt': result>threshold,
                 'negative': result<threshold,'lt': result<threshold,
                 'eq': result==threshold,'zero':result==threshold}[label]
        return 'Yes.' if verdict else 'No.'
    return str(int(value)) if isinstance(value,float) and value.is_integer() else str(value)


def digest(path):
    return sha256(path.read_bytes()).hexdigest()
