"""Bounded reference curator. Deterministic grouping precedes all split assignment."""
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import re
import unicodedata
from slm.data.schema import digest

EMAIL = re.compile(r'(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b')
PHONE = re.compile(r'(?i)(\b(?:phone|mobile|call|tel)\s*[:=]?\s*)(\+?\d[\d ()-]{7,}\d)')
SECRET = re.compile(r'(?i)\b(?:api[_ -]?key|password|access[_ -]?token)\s*[:=]\s*\S+')


def normalize(text):
    if not isinstance(text, str) or '\ufffd' in text:
        raise ValueError('Invalid text encoding')
    text = unicodedata.normalize('NFC', text).replace('\r\n', '\n').strip()
    if any(unicodedata.category(c) == 'Cc' and c not in '\n\t' for c in text):
        raise ValueError('Control characters')
    if not text:
        raise ValueError('Empty message')
    return text


def clean(example):
    item = deepcopy(example)
    roles = [m['role'] for m in item.messages]
    if not roles:
        raise ValueError('No messages')
    tool_dialogue=item.task=='tool_dialogue'
    if tool_dialogue:
        from slm.tools.protocol import validate_messages
        validate_messages(item.messages)
    elif roles != ['text']:
        if roles and roles[0] == 'system':
            roles = roles[1:]
        if len(roles) < 2 or roles != ['user', 'assistant']*(len(roles)//2):
            raise ValueError('Incomplete or unsupported conversation roles')
    redactions = Counter()
    for m in item.messages:
        text = normalize(m['content'])
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) >= 8 and max(Counter(lines).values())/len(lines) > .5:
            raise ValueError('Repeated-line boilerplate')
        if SECRET.search(text):
            raise ValueError('Credential-like content')
        text, count = EMAIL.subn('[EMAIL]', text); redactions['email'] += count
        text, count = PHONE.subn(r'\1[PHONE]', text); redactions['phone'] += count
        m['content'] = text
    if tool_dialogue:
        if any(redactions.values()):raise ValueError('Structured tool dialogue needs manual privacy rewrite; no JSON field edits')
        validate_messages(item.messages)
    item.validation_results.update(privacy_redactions=dict(redactions),
        privacy_scope='email/contextual-phone/credential-patterns; human review still required',
        content_review='required' if item.content_category == 'unreviewed' else 'supplied_label',
        language_review='required' if item.language != 'en' else 'declared_english')
    return item


def key_text(item):
    return '\n'.join(m['role']+':'+m['content'] for m in item.messages)


def exact_key(item):
    # Message boundaries and internal whitespace (including code indentation) matter.
    return digest([(m['role'],m['content']) for m in item.messages])


def shingles(text):
    words = re.findall(r'\w+|[^\w\s]', text.casefold())
    width = min(5, len(words))
    return {tuple(words[i:i+width]) for i in range(len(words)-width+1)}


def curate(examples, sources, seed='slm-splits-v1', training_release=False, max_examples=10_000,
           frozen_groups=None, frozen_example_ids=None):
    frozen_groups = frozen_groups or {}
    frozen_example_ids = set(frozen_example_ids or ())
    if any(s not in ('test', 'validation') for s in frozen_groups.values()):
        raise ValueError('Only held-out groups may be frozen')
    if len(examples) > max_examples:
        raise ValueError('Reference curator limit exceeded; use a verified scalable implementation')
    if len({e.example_id for e in examples}) != len(examples):
        raise ValueError('Duplicate example IDs')
    accepted, rejected = [], Counter()
    for example in sorted(examples, key=lambda e: e.example_id):
        source = sources[example.source]
        if example.source_revision != source.revision or example.license_record != digest(source.__dict__):
            raise ValueError('Example/source provenance mismatch')
        if source.review_status == 'excluded':
            rejected['excluded_source'] += 1; continue
        if example.language not in ('en', 'unknown'):
            rejected['declared_non_english'] += 1; continue
        if example.official_split not in (None, 'train', 'validation', 'test'):
            raise ValueError('Unknown official split')
        try:
            item = clean(example)
        except ValueError as exc:
            rejected[str(exc)] += 1; continue
        if training_release and (source.review_status != 'training_approved' or item.language != 'en'
                                 or item.content_category == 'unreviewed'):
            raise ValueError('Training release requires approved source, English and content review')
        accepted.append(item)
    parent = list(range(len(accepted)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def union(a, b):
        a, b = find(a), find(b)
        parent[max(a, b)] = min(a, b)
    groups, exact, prompts, index = {}, {}, {}, defaultdict(set)
    near_pairs, signatures = set(), {}
    for i, item in enumerate(accepted):
        if item.parent_group_id in groups: union(i, groups[item.parent_group_id])
        groups[item.parent_group_id] = i
        text = key_text(item)
        fingerprint = exact_key(item)
        if fingerprint in exact:
            j = exact[fingerprint]; union(i, j)
        else: exact[fingerprint] = i
        # Prompt identity groups answer variants without discarding distinct answers.
        prompt = next((m['content'] for m in item.messages if m['role'] == 'user'), None)
        if prompt is not None:
            prompt_key = digest(' '.join(prompt.casefold().split()))
            if prompt_key in prompts: union(i, prompts[prompt_key])
            prompts[prompt_key] = i
        for kind, content in [('full', text), ('prompt', prompt)]:
            if content is None: continue
            signature = shingles(content)
            candidates = set().union(*(index[(kind,s)] for s in signature))
            for j in sorted(candidates):
                previous = signatures[(kind,j)]
                score = len(signature & previous)/len(signature | previous)
                if score >= .85:
                    union(i, j); near_pairs.add((i, j))
            signatures[(kind,i)] = signature
            for s in signature: index[(kind,s)].add(i)
    components = defaultdict(list)
    for i in range(len(accepted)): components[find(i)].append(i)
    split_counts, retained, duplicates = Counter(), [], []
    priority = {'train': 0, 'validation': 1, 'test': 2}
    for members in components.values():
        group = digest(sorted(accepted[i].example_id for i in members))
        # Upstream train may be subdivided locally; official held-out rows never train.
        fixed = [accepted[i].official_split for i in members
                 if accepted[i].official_split in ('validation', 'test')]
        fixed += [frozen_groups[accepted[i].parent_group_id] for i in members
                  if accepted[i].parent_group_id in frozen_groups]
        if fixed:
            split = max(fixed, key=priority.get)
        else:
            bucket = int(hashlib.sha256((seed+group).encode()).hexdigest()[:16],16)%100
            split = 'test' if bucket < 5 else 'validation' if bucket < 10 else 'train'
        seen = {}
        for i in sorted(members, key=lambda i: (
                -int(accepted[i].example_id in frozen_example_ids),
                -priority.get(accepted[i].official_split, -1), accepted[i].example_id)):
            item = accepted[i]
            fingerprint = exact_key(item)
            item.split = split
            item.validation_results['split_group'] = group
            if fingerprint in seen:
                duplicates.append({'example_id':item.example_id, 'kept':seen[fingerprint], 'kind':'exact'})
                continue
            seen[fingerprint] = item.example_id
            retained.append(item); split_counts[split] += 1
    retained.sort(key=lambda e: (e.split, e.example_id))
    sizes = {source: [sum(len(m['content']) for m in e.messages) for e in retained if e.source == source]
             for source in sorted({e.source for e in retained})}
    exposures = Counter((e.source,node) for e in retained for node in e.lineage)
    report = {'version':1, 'release':'training' if training_release else 'sample_only',
        'input_examples':len(examples), 'retained_examples':len(retained), 'rejections':dict(rejected),
        'exact_duplicates_removed':len(duplicates), 'near_pairs_grouped':len(near_pairs),
        'near_duplicate_policy':'group only; semantic changes must not be silently deleted',
        'components':len(components), 'splits':dict(split_counts),
        'sources':dict(Counter(e.source for e in retained)),
        'language_labels':dict(Counter(e.language for e in retained)),
        'content_categories':dict(Counter(e.content_category for e in retained)),
        'styles':dict(Counter(e.style for e in retained)),
        'privacy_redactions':dict(sum((Counter(e.validation_results['privacy_redactions']) for e in retained),Counter())),
        'characters_by_source':{k:{'min':min(v),'mean':sum(v)/len(v),'max':max(v)} for k,v in sizes.items()},
        'max_shared_message_exposure':max(exposures.values(),default=0),
        'characters':sum(len(m['content']) for e in retained for m in e.messages),
        'tokens':None, 'token_note':'Production tokenizer not frozen; character counts are not token estimates',
        'duplicates':duplicates, 'split_seed':seed,
        'heldout_groups':{**frozen_groups, **{e.parent_group_id:e.split for e in accepted if e.split != 'train'}},
        'privacy_note':'Pattern redaction is incomplete; sample-only outputs are not approved training data'}
    return retained, report
